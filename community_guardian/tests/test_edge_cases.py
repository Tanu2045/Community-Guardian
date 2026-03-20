import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.models.user_profile import UserProfile
from app.services.category_service import CategoryService
from app.services.filter_service import FilterService
from app.services.framing_service import FramingService
from app.services.insight_service import InsightService
from app.services.loader import load_alerts
from app.services.profile_relevance_service import ProfileRelevanceService


class FailingAIClient:
    def generate_response(self, prompt: str) -> dict:  # pragma: no cover
        raise RuntimeError("simulated ai failure")


def _local_tmp_file() -> Path:
    root = Path(__file__).resolve().parents[1] / ".tmp_tests"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{uuid4().hex}.json"


def test_loader_skips_malformed_alerts() -> None:
    bad_data = [
        {"id": 1, "source": "news", "content": "ok", "location": "X", "timestamp": "2026-03-18"},
        {"id": 2, "source": "news", "location": "X", "timestamp": "2026-03-18"},  # missing content
    ]
    file_path = _local_tmp_file()
    file_path.write_text(json.dumps(bad_data), encoding="utf-8")

    alerts = load_alerts(file_path)
    assert len(alerts) == 1
    assert alerts[0].id == 1


def test_filter_handles_empty_and_duplicate_content() -> None:
    base = Path(__file__).resolve().parents[1]
    alerts = load_alerts(base / "data" / "alerts.json")
    _, results = FilterService(use_ai=False).filter_alerts(alerts)

    by_id = {item.alert.id: item for item in results}
    assert by_id[6].is_relevant is False
    assert by_id[6].reason == "empty_content"
    assert by_id[5].is_relevant is False
    assert by_id[5].reason.startswith("duplicate")


def test_filter_detects_reworded_event_duplicates() -> None:
    base = Path(__file__).resolve().parents[1]
    alerts = load_alerts(base / "data" / "alerts.json")
    categorized = CategoryService(use_ai=False).classify_alerts(alerts)
    _, results = FilterService(use_ai=False).filter_alerts(categorized)

    by_id = {item.alert.id: item for item in results}
    assert by_id[17].is_relevant is False
    assert by_id[17].reason.startswith("duplicate")
    assert by_id[17].duplicate_of == 16


def test_filter_detects_cross_category_duplicate_when_one_is_general() -> None:
    sample = [
        {
            "id": 201,
            "source": "news",
            "content": "Local hospital reported a ransomware attack, all systems temporarily offline.",
            "location": "Downtown",
            "timestamp": "2026-03-18T12:30:00+05:30",
            "category": "",
        },
        {
            "id": 202,
            "source": "news",
            "content": "All systems at local hospital are temporarily offline.",
            "location": "Downtown",
            "timestamp": "2026-03-18T13:00:00+05:30",
            "category": "",
        },
    ]
    file_path = _local_tmp_file()
    file_path.write_text(json.dumps(sample), encoding="utf-8")
    alerts = load_alerts(file_path)
    categorized = CategoryService(use_ai=False).classify_alerts(alerts)
    _, results = FilterService(use_ai=False).filter_alerts(categorized)
    by_id = {item.alert.id: item for item in results}

    assert by_id[202].is_relevant is False
    assert by_id[202].reason.startswith("duplicate")
    assert by_id[202].duplicate_of == 201


def test_ai_failure_falls_back_for_framing_and_insight() -> None:
    base = Path(__file__).resolve().parents[1]
    alerts = load_alerts(base / "data" / "alerts.json")
    relevant, _ = FilterService(use_ai=False).filter_alerts(alerts)

    framing = FramingService(use_ai=True, ai_client=FailingAIClient()).frame_alerts(relevant)
    insight = InsightService(use_ai=True, ai_client=FailingAIClient()).generate(relevant)

    assert len(framing) == len(relevant)
    assert len(insight) == len(relevant)
    assert all(item.framed_text for item in framing)
    assert all(2 <= len(item.actions) <= 4 for item in insight)


def test_loader_raises_on_non_array_payload() -> None:
    file_path = _local_tmp_file()
    file_path.write_text(json.dumps({"not": "array"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_alerts(file_path)


def test_profile_relevance_filters_by_persona_and_location() -> None:
    base = Path(__file__).resolve().parents[1]
    alerts = load_alerts(base / "data" / "alerts.json")
    categorized = CategoryService(use_ai=False).classify_alerts(alerts)
    profile = UserProfile(persona="housewife", primary_location="Old Town")

    relevant, _ = FilterService(
        use_ai=False,
        profile_relevance=ProfileRelevanceService(profile),
    ).filter_alerts(categorized)

    assert relevant
    assert all(a.location in {"Old Town", "Citywide"} for a in relevant)


def test_profile_relevance_accepts_arbitrary_persona_text() -> None:
    sample = [
        {
            "id": 101,
            "source": "security_feed",
            "content": "Suspicious login attempts detected on municipal employee accounts.",
            "location": "City Hall",
            "timestamp": "2026-03-18T13:00:00+05:30",
            "category": "",
        },
        {
            "id": 102,
            "source": "news",
            "content": "Flood warning issued for Riverside Ward due to heavy rainfall.",
            "location": "Riverside Ward",
            "timestamp": "2026-03-18T14:00:00+05:30",
            "category": "",
        },
    ]
    file_path = _local_tmp_file()
    file_path.write_text(json.dumps(sample), encoding="utf-8")
    alerts = load_alerts(file_path)
    categorized = CategoryService(use_ai=False).classify_alerts(alerts)
    profile = UserProfile(persona="govt employee", primary_location="City Hall")

    relevant, _ = FilterService(
        use_ai=False,
        profile_relevance=ProfileRelevanceService(profile),
    ).filter_alerts(categorized)

    # Arbitrary persona should still produce profile-aware results.
    assert relevant
    assert any(a.location == "City Hall" for a in relevant)


def test_profile_relevance_supports_fuzzy_location_input() -> None:
    base = Path(__file__).resolve().parents[1]
    alerts = load_alerts(base / "data" / "alerts.json")
    categorized = CategoryService(use_ai=False).classify_alerts(alerts)
    profile = UserProfile(persona="student", primary_location="Lake")

    relevant, _ = FilterService(
        use_ai=False,
        profile_relevance=ProfileRelevanceService(profile),
    ).filter_alerts(categorized)

    assert relevant
    assert any(a.location == "Lakeside" for a in relevant)
