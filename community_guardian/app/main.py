import json
import math
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from app.ai.gemini_client import GeminiClient
from app.config import load_config
from app.models.alert import Alert
from app.models.user_profile import UserProfile
from app.services.category_service import CategoryService
from app.services.digest_service import DigestService
from app.services.filter_service import FilterService, FilteredResult
from app.services.framing_service import FramingService
from app.services.insight_service import InsightService
from app.services.loader import load_alerts
from app.services.profile_relevance_service import ProfileRelevanceService
from app.services.safe_circle_service import SafeCircleService


def _build_incident_groups(filter_results: list[FilteredResult]) -> list[dict]:
    if not filter_results:
        return []

    result_by_id = {item.alert.id: item for item in filter_results}

    def root_alert_id(alert_id: int) -> int:
        visited: set[int] = set()
        current = alert_id
        while current in result_by_id:
            item = result_by_id[current]
            parent = item.duplicate_of
            if parent is None or parent in visited or parent not in result_by_id:
                return current
            visited.add(current)
            current = parent
        return alert_id

    groups: dict[int, list[int]] = {}
    for item in filter_results:
        alert_id = item.alert.id
        root_id = root_alert_id(alert_id)
        groups.setdefault(root_id, []).append(alert_id)

    return [
        {"root_id": root_id, "count": len(member_ids), "member_ids": sorted(member_ids)}
        for root_id, member_ids in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0]))
        if len(member_ids) >= 2
    ]


def run_pipeline(
    persona: str | None = None,
    primary_location: str | None = None,
    watch_locations: list[str] | None = None,
    focus_categories: list[str] | None = None,
    data_path: str | None = None,
    checkpoint_every: int = 10,
    use_ai_override: bool | None = None,
) -> dict:
    config = load_config()
    use_ai = config.use_ai if use_ai_override is None else use_ai_override
    ai_client = GeminiClient(config.gemini_api_key) if use_ai else None
    fallback_events: list[dict] = []
    user_profile = UserProfile(
        persona=(persona or config.user_persona),
        primary_location=(primary_location or config.user_primary_location),
        watch_locations=(config.user_watch_locations if watch_locations is None else watch_locations),
        focus_categories=(config.user_focus_categories if focus_categories is None else focus_categories),
    )

    checkpoint_dir = config.output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = checkpoint_dir / "pipeline_checkpoint.json"

    def checkpoint(stage: str, processed: int, total: int, alert_id: int | None = None) -> None:
        if processed % max(1, checkpoint_every) != 0 and processed != total:
            return
        payload = {
            "stage": stage,
            "processed": processed,
            "total": total,
            "last_alert_id": alert_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        checkpoint_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    alerts = load_alerts(data_path or config.data_path)
    categorized_alerts = CategoryService(
        use_ai=use_ai, ai_client=ai_client, user_profile=user_profile, fallback_events=fallback_events
    ).classify_alerts(alerts, progress_hook=checkpoint)

    relevant_alerts, filter_results = FilterService(
        use_ai=use_ai,
        ai_client=ai_client,
        profile_relevance=ProfileRelevanceService(user_profile),
        fallback_events=fallback_events,
    ).filter_alerts(categorized_alerts, progress_hook=checkpoint)
    framed = FramingService(
        use_ai=use_ai, ai_client=ai_client, user_profile=user_profile, fallback_events=fallback_events
    ).frame_alerts(
        relevant_alerts, progress_hook=checkpoint
    )
    insights = InsightService(
        use_ai=use_ai, ai_client=ai_client, user_profile=user_profile, fallback_events=fallback_events
    ).generate(
        relevant_alerts, progress_hook=checkpoint
    )
    digest = DigestService.build_digest(framed, insights, filter_results=filter_results)
    incident_groups = _build_incident_groups(filter_results)

    dropped = [r for r in filter_results if not r.is_relevant]
    checkpoint_file.write_text(
        json.dumps(
            {
                "stage": "completed",
                "processed": len(alerts),
                "total": len(alerts),
                "loaded": len(alerts),
                "relevant": len(relevant_alerts),
                "filtered_out": len(dropped),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if not use_ai:
        fallback_events.extend(
            {"stage": "category", "alert_id": alert.id, "reason": "ai_disabled"}
            for alert in categorized_alerts
        )
        fallback_events.extend(
            {"stage": "filter", "alert_id": alert.id, "reason": "ai_disabled"}
            for alert in categorized_alerts
        )
        fallback_events.extend(
            {"stage": "framing", "alert_id": alert.id, "reason": "ai_disabled"}
            for alert in relevant_alerts
        )
        fallback_events.extend(
            {"stage": "insight", "alert_id": alert.id, "reason": "ai_disabled"}
            for alert in relevant_alerts
        )
    return {
        "digest": digest,
        "categorized_alerts": categorized_alerts,
        "filter_results": filter_results,
        "output_dir": config.output_dir,
        "loaded_count": len(alerts),
        "relevant_count": len(relevant_alerts),
        "filtered_count": len(dropped),
        "profile": user_profile,
        "checkpoint_file": checkpoint_file,
        "use_ai": use_ai,
        "fallback_events": fallback_events,
        "incident_groups": incident_groups,
    }


def _alert_to_dict(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "source": alert.source,
        "content": alert.content,
        "location": alert.location,
        "timestamp": alert.timestamp,
        "category": alert.category,
    }


def _write_output_files(
    output_dir: Path,
    categorized_alerts: list[Alert],
    filter_results: list[FilteredResult],
    digest: list[dict],
    summary: dict,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    result_by_id = {item.alert.id: item for item in filter_results}
    classified_payload = {
        "summary": summary,
        "alerts": [
            {
                **_alert_to_dict(alert),
                "is_relevant": result_by_id[alert.id].is_relevant,
                "relevance_reason": result_by_id[alert.id].reason,
                "duplicate_of": result_by_id[alert.id].duplicate_of,
            }
            for alert in categorized_alerts
        ],
    }
    digest_payload = {"summary": summary, "digest": digest}

    (output_dir / "alerts_classified.json").write_text(
        json.dumps(classified_payload, indent=2),
        encoding="utf-8",
    )
    (output_dir / "digest.json").write_text(
        json.dumps(digest_payload, indent=2),
        encoding="utf-8",
    )


def _normalize_confidence(confidence: object) -> str:
    if isinstance(confidence, str):
        normalized = confidence.strip().lower()
        return normalized if normalized else "low"
    if isinstance(confidence, (int, float)):
        if isinstance(confidence, float) and math.isnan(confidence):
            return "low"
        if confidence >= 0.8:
            return "high"
        if confidence >= 0.5:
            return "medium"
        return "low"
    return "low"


def _confidence_badge(confidence: object) -> str:
    normalized = _normalize_confidence(confidence)
    if normalized == "high":
        return "red"
    if normalized == "medium":
        return "orange"
    return "green"


def _init_state() -> None:
    if "pipeline" not in st.session_state:
        st.session_state["pipeline"] = None
    if "safe_circles" not in st.session_state:
        st.session_state["safe_circles"] = SafeCircleService()


def main() -> None:
    st.set_page_config(page_title="Community Guardian Dashboard", layout="wide")
    _init_state()

    config = load_config()

    st.title("Community Guardian")
    st.caption("Filter noise. Understand risks. Take action.")

    st.subheader("Controls")
    control_col1, control_col2, control_col3 = st.columns(3)

    with control_col1:
        dataset = st.selectbox(
            "Dataset",
            ["data/alerts.json", "data/alerts_70.json", "data/alerts_25_demo.json"],
            index=0,
        )
        use_ai = st.toggle("Use AI", value=config.use_ai)

    with control_col2:
        persona = st.text_input("Persona", value=config.user_persona)
        primary_location = st.text_input("Your Location", value=config.user_primary_location)

    with control_col3:
        focus_options = ["All", "phishing", "scam", "breach", "outage", "general"]
        default_focus = "All"
        if config.user_focus_categories:
            first_focus = config.user_focus_categories[0].strip().lower()
            if first_focus in focus_options:
                default_focus = first_focus
        focus_category = st.selectbox("Focus Category", focus_options, index=focus_options.index(default_focus))

    if st.button("Process Alerts", type="primary"):
        with st.spinner("Running full alert pipeline..."):
            pipeline = run_pipeline(
                persona=persona,
                primary_location=primary_location,
                watch_locations=[],
                focus_categories=None if focus_category == "All" else [focus_category],
                data_path=str((Path(__file__).resolve().parents[1] / dataset).resolve()),
                use_ai_override=use_ai,
            )
            summary = {
                "loaded": pipeline["loaded_count"],
                "relevant": pipeline["relevant_count"],
                "filtered_out": pipeline["filtered_count"],
                "persona": pipeline["profile"].persona,
                "primary_location": pipeline["profile"].primary_location,
                "watch_locations": pipeline["profile"].watch_locations,
                "focus_categories": pipeline["profile"].focus_categories,
                "category_filter": None,
                "query_filter": None,
                "displayed_items": len(pipeline["digest"]),
                "ui_location_filter": None,
                "use_ai": pipeline["use_ai"],
            }
            _write_output_files(
                output_dir=pipeline["output_dir"],
                categorized_alerts=pipeline["categorized_alerts"],
                filter_results=pipeline["filter_results"],
                digest=pipeline["digest"],
                summary=summary,
            )
            st.session_state["pipeline"] = pipeline

    pipeline = st.session_state.get("pipeline")

    if pipeline is None:
        st.info("Run Process Alerts to generate a digest.")
    else:
        st.success(
            f"Processed {pipeline['loaded_count']} alerts | Relevant {pipeline['relevant_count']} | "
            f"Filtered out {pipeline['filtered_count']}"
        )
        st.subheader("Fallback Usage")
        fallback_events = list(pipeline.get("fallback_events", []))
        if not fallback_events:
            st.caption("No fallback paths were used.")
        else:
            stage_order = ["category", "filter", "framing", "insight"]
            events_by_stage: dict[str, list[dict]] = {stage: [] for stage in stage_order}
            for event in fallback_events:
                stage = str(event.get("stage", "unknown"))
                events_by_stage.setdefault(stage, []).append(event)

            for stage in stage_order:
                stage_events = events_by_stage.get(stage, [])
                if not stage_events:
                    continue
                ids = sorted({int(event["alert_id"]) for event in stage_events if isinstance(event.get("alert_id"), int)})
                reason_counts: dict[str, int] = {}
                for event in stage_events:
                    reason = str(event.get("reason", "unknown"))
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                reason_text = ", ".join(f"{name}={count}" for name, count in sorted(reason_counts.items()))
                id_text = ", ".join(str(alert_id) for alert_id in ids[:40])
                if len(ids) > 40:
                    id_text += ", ..."
                st.write(
                    f"- **{stage.title()}**: {len(stage_events)} fallback events "
                    f"({reason_text}) | Alert IDs: {id_text or 'none'}"
                )

        st.subheader("Filters")
        digest = list(pipeline["digest"])
        categories = sorted({item["category"] for item in digest})
        locations = sorted({item["location"] for item in digest})

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            selected_category = st.selectbox("Category", ["All", *categories])
            query = st.text_input("Search alerts")
        with filter_col2:
            selected_location = st.selectbox("Location", ["All", *locations])

        filtered = digest
        if selected_category != "All":
            filtered = [item for item in filtered if item["category"] == selected_category]
        if selected_location != "All":
            filtered = [item for item in filtered if item["location"] == selected_location]
        if query.strip():
            needle = query.strip().lower()
            filtered = [
                item
                for item in filtered
                if needle in item["framed_text"].lower()
                or needle in item["why_this_matters"].lower()
                or needle in item["location"].lower()
            ]

        st.subheader("Alerts Digest")
        st.info(f"Showing {len(filtered)} alerts | Filtered {pipeline['filtered_count']} noisy alerts")

        if not filtered:
            st.warning("No alerts match the current filters.")
        for item in filtered:
            with st.container(border=True):
                left, right = st.columns([3, 2])
                with left:
                    st.markdown(f"**#{item['id']} {item['category'].title()} Alert - {item['location']}**")
                    st.write(item["framed_text"])
                with right:
                    confidence_value = _normalize_confidence(item.get("confidence"))
                    badge = _confidence_badge(confidence_value)
                    st.markdown(f"**Confidence:** :{badge}[{confidence_value.upper()}]")
                    st.markdown(
                        f"**Verification signal:** `{str(item.get('verification_signal', 'low')).upper()}` "
                        f"from `{int(item.get('report_count', 1))}` report(s)"
                    )
                    st.markdown(f"**Guidance:** `{item['attention_guidance']}`")
                    st.markdown(f"**Source:** `{item['source']}`")
                st.markdown("**Why this matters**")
                st.write(item["why_this_matters"])
                st.markdown("**What to do**")
                for step in item["actions"]:
                    st.write(f"- {step}")

    st.subheader("Safe Circles")
    circles: SafeCircleService = st.session_state["safe_circles"]

    create_col1, create_col2 = st.columns(2)
    with create_col1:
        circle_name = st.text_input("Circle Name")
    with create_col2:
        members_text = st.text_input("Members (comma separated)")

    if st.button("Create Circle"):
        members = [m.strip() for m in members_text.split(",") if m.strip()]
        if not circle_name.strip():
            st.error("Circle name is required.")
        else:
            circles.create_circle(circle_name.strip(), members)
            st.success(f"Created circle '{circle_name.strip()}'")

    circle_names = circles.list_circles()
    if circle_names:
        update_col1, update_col2 = st.columns(2)
        with update_col1:
            selected_circle = st.selectbox("Select Circle", circle_names)
            member_name = st.text_input("Member Name")
        with update_col2:
            status = st.selectbox("Status", ["SAFE", "NEED_HELP", "AVOID_AREA"])
            note = st.text_area("Optional Note")

        if st.button("Send Update"):
            try:
                if not member_name.strip():
                    raise ValueError("Member Name is required.")
                if member_name.strip() not in circles.get_members(selected_circle):
                    circles.add_member(selected_circle, member_name.strip())
                update = circles.send_status(selected_circle, member_name.strip(), status, note)
                st.success(f"Shared status: {update['status']}")
            except ValueError as exc:
                st.error(str(exc))

        st.markdown("**Updates**")
        updates = circles.get_updates(selected_circle)
        if not updates:
            st.write("No updates yet.")
        for update in updates:
            note_suffix = f" - {update['note']}" if update["note"] else ""
            st.write(f"- {update['member']}: {update['status']}{note_suffix}")
    else:
        st.caption("Create a circle to start sharing status updates.")


if __name__ == "__main__":
    main()
