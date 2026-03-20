from app.ai.prompts import build_framing_prompt
from app.fallback.framing_rules import frame_alert
from app.models.alert import Alert
from app.models.framed_alert import FramedAlert
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FramingService:
    def __init__(self, use_ai: bool = False, ai_client=None, user_profile=None, fallback_events: list[dict] | None = None) -> None:
        self.use_ai = use_ai
        self.ai_client = ai_client
        self.user_profile = user_profile
        self.fallback_events = fallback_events if fallback_events is not None else []

    def frame_alerts(self, alerts: list[Alert], progress_hook=None) -> list[FramedAlert]:
        items: list[FramedAlert] = []
        total = len(alerts)
        for idx, alert in enumerate(alerts, start=1):
            items.append(self._frame_single(alert))
            if progress_hook is not None:
                progress_hook(stage="framing", processed=idx, total=total, alert_id=alert.id)
        return items

    def _frame_single(self, alert: Alert) -> FramedAlert:
        payload = None
        ai_failed = False
        if self.use_ai and self.ai_client is not None:
            try:
                payload = self.ai_client.generate_response(build_framing_prompt(alert, self.user_profile))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("AI framing failed for alert %s: %s", alert.id, exc)
                logger.info("Using fallback framing for alert %s", alert.id)
                ai_failed = True
                self.fallback_events.append(
                    {"stage": "framing", "alert_id": alert.id, "reason": "ai_error"}
                )
        if not self._is_valid_payload(payload):
            if self.use_ai and self.ai_client is not None and not ai_failed:
                self.fallback_events.append(
                    {"stage": "framing", "alert_id": alert.id, "reason": "invalid_ai_payload"}
                )
            payload = frame_alert(alert)
        return FramedAlert(
            alert=alert,
            framed_text=payload["framed_text"],
            confidence=payload["confidence"],
            relevance=payload["relevance"],
            guidance=payload["guidance"],
        )

    @staticmethod
    def _is_valid_payload(payload: dict | None) -> bool:
        if not isinstance(payload, dict):
            return False
        keys = {"framed_text", "confidence", "relevance", "guidance"}
        return keys.issubset(payload.keys())
