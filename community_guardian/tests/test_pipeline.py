from pathlib import Path

from app.services.digest_service import DigestService
from app.services.filter_service import FilterService
from app.services.framing_service import FramingService
from app.services.insight_service import InsightService
from app.services.loader import load_alerts


def test_full_pipeline_happy_path() -> None:
    base = Path(__file__).resolve().parents[1]
    alerts = load_alerts(base / "data" / "alerts.json")
    relevant, results = FilterService(use_ai=False).filter_alerts(alerts)
    framed = FramingService(use_ai=False).frame_alerts(relevant)
    insights = InsightService(use_ai=False).generate(relevant)
    digest = DigestService.build_digest(framed, insights)

    assert len(alerts) > 0
    assert len(results) == len(alerts)
    assert len(relevant) == len(framed) == len(insights) == len(digest)
    assert len(relevant) >= 6
    assert all(item["actions"] for item in digest)
    assert all(2 <= len(item["actions"]) <= 4 for item in digest)
