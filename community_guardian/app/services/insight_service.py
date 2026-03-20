from app.ai.prompts import build_insight_prompt
from app.fallback.insight_templates import build_insight
from app.models.alert import Alert
from app.models.insight import Insight
from app.utils.logger import get_logger

logger = get_logger(__name__)


class InsightService:
    def __init__(self, use_ai: bool = False, ai_client=None, user_profile=None, fallback_events: list[dict] | None = None) -> None:
        self.use_ai = use_ai
        self.ai_client = ai_client
        self.user_profile = user_profile
        self.fallback_events = fallback_events if fallback_events is not None else []

    def generate(self, alerts: list[Alert], progress_hook=None) -> list[Insight]:
        items: list[Insight] = []
        total = len(alerts)
        for idx, alert in enumerate(alerts, start=1):
            items.append(self._single(alert))
            if progress_hook is not None:
                progress_hook(stage="insight", processed=idx, total=total, alert_id=alert.id)
        return items

    def _single(self, alert: Alert) -> Insight:
        payload = None
        ai_failed = False
        if self.use_ai and self.ai_client is not None:
            try:
                payload = self.ai_client.generate_response(build_insight_prompt(alert, self.user_profile))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("AI insight failed for alert %s: %s", alert.id, exc)
                logger.info("Using fallback insight template for alert %s", alert.id)
                ai_failed = True
                self.fallback_events.append(
                    {"stage": "insight", "alert_id": alert.id, "reason": "ai_error"}
                )
        if not self._is_valid_payload(payload):
            if self.use_ai and self.ai_client is not None and not ai_failed:
                self.fallback_events.append(
                    {"stage": "insight", "alert_id": alert.id, "reason": "invalid_ai_payload"}
                )
            payload = build_insight(alert)
        return Insight(alert_id=alert.id, why=payload["why"], actions=payload["actions"])

    @staticmethod
    def _is_valid_payload(payload: dict | None) -> bool:
        if not isinstance(payload, dict):
            return False
        actions = payload.get("actions")
        return isinstance(payload.get("why"), str) and isinstance(actions, list) and 2 <= len(actions) <= 4
