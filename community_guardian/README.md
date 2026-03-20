# Community Guardian

## Candidate Name:

Tanupriya

## Scenario Chosen:

Community Safety & Digital Wellness (Scenario 3)

## Estimated Time Spent:

~5–6 hours

---
## 🎥 Video Demo
 Link : https://youtu.be/d3Cy1yw-nO8


Note: We only fast-forwarded the part of the video where processing was taking place.

## 🚀 Quick Start

### Prerequisites:

* Python 3.9+
* pip or conda
* (Optional) Gemini API key

### Setup:

```bash
git clone <your-repo-url>
cd <repo-name>

# Option A (recommended): use conda
conda activate c:\Users\TANU\Desktop\pa_new\pa\.conda\community_guardian

# Option B: create a fresh conda env
# conda create -n community_guardian python=3.11 -y
# conda activate community_guardian

pip install -r requirements.txt
cd community_guardian
```

### Environment Variables:

Create a `.env` file:

```env
USE_AI=false
GEMINI_API_KEY=your_key_here
```

### Run Application:

```bash
python -m streamlit run app/main.py
```

### Run Tests:

```bash
python -m pytest tests -q
```

---

## 🧠 Problem Definition

Users receive fragmented and often unreliable safety information from multiple sources, leading to alert fatigue and difficulty identifying actionable threats.

This project addresses the problem by filtering noise and presenting **calm, relevant, and actionable safety insights** tailored to the user.

---

## 💡 Solution Overview

Community Guardian processes community alerts through a structured pipeline to:

* Classify incidents into safety categories
* Remove low-signal and duplicate alerts
* Personalize results based on user profile (location, persona, interests)
* Generate clear explanations and recommended actions
* Present a concise safety digest via a Streamlit dashboard

---

## 🔄 Core Flow

Load Alerts → Classify → Filter & Deduplicate → Personalize → Generate Insights → Display Digest

---

## 🤖 AI Integration + Fallback

### AI Usage:

* Alert classification
* Alert relevance/duplicate filtering
* Insight generation (why it matters + actions)
* Natural language framing

### Fallback:

* Keyword-based classification
* Rule-based filtering and templates

The system is **fallback-first**, ensuring it works reliably even when AI is unavailable or incorrect.

---

## 🧪 Testing

Implemented using `pytest`:

* Happy path: full pipeline execution
* Edge case: malformed input and duplicate alerts

---

## 📊 Data

* Uses synthetic JSON datasets only
* No real user or sensitive data included

---

## 🔐 Security

* API keys are stored in `.env` (not committed)
* `.env.example` provided

---

## ⚖️ Tradeoffs & Prioritization

* Prioritized backend pipeline and reliability over UI polish
* Used rule-based fallback instead of training custom ML models
* Limited categories for interpretability
* Avoided real-time data ingestion to reduce complexity and privacy risks

---

## 🔒 Responsible AI & Privacy

* AI outputs may be incorrect → deterministic fallback ensures reliability
* Uses only synthetic data (no real personal data)
* User profile data may be sent to AI when enabled (limitation)
* No encryption or access control implemented (future work)

### Future Improvements:

* User consent before AI usage
* Encryption for stored outputs
* Role-based access control
* Privacy-first mode (no location retention)

---

## ⚠️ Known Limitations

* No persistent database or authentication
* Safe Circle is session-based only
* No external verification APIs
* Limited category coverage

---

## 🚧 Future Enhancements

* Real-time data ingestion from trusted sources
* Source credibility scoring
* Persistent Safe Circle with multi-user support
* Improved personalization and UI

---

## 🤖 AI Disclosure

**Did you use an AI assistant?**
Yes

**How did you verify suggestions?**

* Validated outputs against expected behavior
* Tested edge cases using pytest
* Ensured fallback logic works independently

**Example of a rejected suggestion:**
A fully AI-dependent classification approach was rejected in favor of a hybrid system with deterministic fallback to ensure reliability.

---
