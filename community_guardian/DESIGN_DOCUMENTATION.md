# Design Documentation

## Problem Definition
Users are overwhelmed by fragmented and unreliable safety information, leading to alert fatigue and anxiety. This system filters noise and provides calm, actionable insights tailored to the user’s context.

## 1. System Overview
Community Guardian is a Python application that converts noisy, mixed-quality community alerts into a concise, actionable safety digest. The system supports both deterministic fallback rules and optional AI-assisted decisions. It is currently delivered as a Streamlit dashboard and is structured as a modular processing pipeline.



Primary outcomes:
- Classify alerts into safety categories.
- Filter low-signal and duplicate alerts.
- Personalize relevance with user profile context.
- Frame remaining alerts in calm, digestible language.
- Generate "why this matters" and recommended actions.
- Provide a Safe Circle status-sharing utility.

## 2. Tech Stack
- Language: Python
- UI: Streamlit
- Config: python-dotenv (`.env`)
- Testing: pytest
- Optional AI provider: Gemini API via `urllib` HTTP client
- Data format: JSON files for input/output

Dependencies currently listed:
- `python-dotenv==1.0.1`
- `pytest==8.3.5`
- `streamlit==1.38.0`

## 3. Repository Structure
- `app/main.py`: Streamlit entrypoint and pipeline orchestration
- `app/config.py`: environment/config loading
- `app/models/`: dataclasses (`Alert`, `FramedAlert`, `Insight`, `SafeCircle`, `UserProfile`)
- `app/services/`: core pipeline services
- `app/fallback/`: deterministic non-AI rules/templates
- `app/ai/`: prompt builders and Gemini client
- `app/utils/`: validation and logger utilities
- `data/`: alert datasets
- `output/`: generated classified alerts, digest, checkpoints
- `tests/`: happy-path and edge-case tests

## 4. Runtime Pipeline Design
### 4.1 Inputs
Pipeline inputs are supplied from Streamlit controls and config defaults:
- Dataset path
- AI on/off toggle
- Persona
- Primary location
- Focus category override

`run_pipeline(...)` composes these inputs into a `UserProfile` and processes alerts in sequence.

### 4.2 Stages
1. Load + Validate (`LoaderService` behavior in `loader.py`)
- Reads JSON array.
- Validates required fields and types.
- Skips malformed rows with warnings.

2. Category Classification (`CategoryService`)
- AI path: `build_category_prompt` + Gemini response normalization.
- Fallback path: keyword scoring by category.
- Categories: `phishing`, `scam`, `breach`, `outage`, `general`.

3. Relevance + Dedup (`FilterService` + `fallback/filter_rules.py`)
- Removes low-signal alerts (`empty_content`, `too_short`, `vague_message`).
- Dedup logic:
  - Not duplicate when locations are clearly different.
  - Not duplicate when timestamp gap exceeds configured window.
  - Otherwise classify as `duplicate_exact`, `duplicate_near`, or `duplicate_event` based on similarity and overlap rules.
- Applies profile relevance filtering after dedup/relevance decision.

4. Profile Relevance (`ProfileRelevanceService`)
- Uses persona, primary/watch locations, and focus categories.
- Supports inferred category affinity from persona hints.
- Supports fuzzy location matching and strict-location personas.

5. Alert Framing (`FramingService`)
- AI or fallback generation of:
  - `framed_text`
  - `confidence`
  - `relevance`
  - `guidance`
- Current tone guidance is calm/reassuring.

6. Insight Generation (`InsightService`)
- AI or fallback generation of:
  - `why`
  - `actions` (2-4 items)
- Fallback templates are category-driven with flood-specific outage handling.

7. Digest Build (`DigestService`)
- Merges framed alerts and insights.
- Adds verification metadata derived from duplicate clusters:
  - `report_count`
  - `verification_signal` (`low`/`medium`/`high`)

8. Output Write
- `output/alerts_classified.json`
- `output/digest.json`
- `output/checkpoints/pipeline_checkpoint.json`

## 5. AI + Fallback Strategy
The system is fallback-first and resilient:
- Every AI-supported stage has deterministic fallback behavior.
- Invalid/missing AI payloads automatically revert to local logic.
- Fallback events are tracked by stage (`category`, `filter`, `framing`, `insight`) and surfaced in UI.
- AI usage can be toggled on/off from the Streamlit dashboard (`Use AI`). When toggled off, the full pipeline runs on deterministic local fallback rules/templates only.

Behavior modes:
- `USE_AI=false`: fully local rule/template pipeline.
- `USE_AI=true`: AI-first attempt with guarded fallback.

## 6. Streamlit UI Design
`app/main.py` provides a single-page dashboard with these sections:
- Header and product message
- Controls:
  - dataset selection (`alerts.json`, `alerts_70.json`, `alerts_25_demo.json`)
  - AI toggle
  - persona and location inputs
  - focus category input
- Process Alerts button to execute full pipeline
- Pipeline summary (processed/relevant/filtered)
- Fallback Usage section (stage-level fallback visibility)
- Digest filters:
  - category (dynamic from result)
  - location (dynamic from result)
  - query text search
- Alert cards with confidence, verification signal, guidance, source, reason/actions
- Safe Circles:
  - create circles
  - send status (`SAFE`, `NEED_HELP`, `AVOID_AREA`)
  - list updates

## 7. Verification Signal Design
To provide a trust cue without claiming external fact-checking:
- Duplicate-linked reports are clustered per incident root.
- Each retained digest alert receives the cluster count as `report_count`.
- `verification_signal` derives from count thresholds:
  - `low`: 1 report
  - `medium`: 2-3 reports
  - `high`: 4+ reports

This indicates corroboration density within the ingested dataset.

## 8. Data Contracts
### 8.1 Input Alert Schema
Required fields:
- `id: int`
- `source: str`
- `content: str`
- `location: str`
- `timestamp: str`
Optional:
- `category: str`

### 8.2 Digest Item Shape
Each digest item contains:
- identity/context (`id`, `source`, `category`, `location`, `timestamp`)
- framing (`framed_text`, `confidence`, `relevance_reason`, `attention_guidance`)
- insight (`why_this_matters`, `actions`)
- verification metadata (`report_count`, `verification_signal`)

## 9. Safety Circle Design
Safe Circle is an in-memory collaboration utility:
- Create circles with member lists
- Post structured status updates with timestamp
- Read updates by circle

Note: current implementation is session memory only (no persistence or auth).

## 10. Test Design
Test suite covers:
- Happy path full pipeline behavior
- Loader validation and malformed data handling
- Dedup and reworded duplicate cases
- AI failure fallback behavior
- Profile relevance behavior including fuzzy location matching

Current baseline run (latest local):
- `test_pipeline.py`: pass
- `test_edge_cases.py`: pass

## 11. Key Design Decisions
- Deterministic fallback is always available for reliability.
- Personalization is integrated at relevance stage, not UI-only filtering.
- UI transparency is emphasized via fallback visibility and verification signals.
- Outputs remain JSON-first for portability and auditability.

## 12. Current Limitations
- No persistent datastore or auth layer.
- No external verification API for source truth validation.
- Privacy controls are basic; profile/location can be included in output files and AI prompts when enabled.
- Safe Circle is not multi-user persistent.

## 13. Extension Directions
- Persist users, circles, and incidents in a database.
- Add source trust weighting to verification signal.
- Add explicit privacy modes (redaction, no-location retention, consent gates).
- Add role/access control and encrypted storage.
- Add background ingestion connectors for live feeds.

## 14. Tradeoffs & Decisions
- Chose rule-based fallback over complex ML models for reliability within time constraints.
- Did not integrate real-time APIs to avoid data privacy risks and complexity.
- Limited categories to keep classification interpretable.

## 15. Responsible AI & Privacy
- AI outputs may be inaccurate → fallback ensures deterministic behavior.
- User location is used for relevance but is not encrypted or access-controlled (limitation).
- No real personal data is used (synthetic dataset only).
- Future improvements:
  - user consent before sending data to AI
  - encryption for stored outputs
  - role-based access control
