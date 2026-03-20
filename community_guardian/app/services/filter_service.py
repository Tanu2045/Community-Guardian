from dataclasses import dataclass

from app.ai.prompts import build_filter_prompt
from app.fallback.filter_rules import evaluate_alert
from app.models.alert import Alert
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FilteredResult:
    alert: Alert
    is_relevant: bool
    reason: str
    duplicate_of: int | None = None


class FilterService:
    def __init__(self, use_ai: bool = False, ai_client=None, profile_relevance=None, fallback_events: list[dict] | None = None) -> None:
        self.use_ai = use_ai
        self.ai_client = ai_client
        self.profile_relevance = profile_relevance
        self.fallback_events = fallback_events if fallback_events is not None else []

    def filter_alerts(self, alerts: list[Alert], progress_hook=None) -> tuple[list[Alert], list[FilteredResult]]:
        seen_relevant: list[Alert] = []
        seen_for_duplicates: list[Alert] = []
        results: list[FilteredResult] = []
        total = len(alerts)

        for idx, alert in enumerate(alerts, start=1):
            decision = evaluate_alert(alert, seen_for_duplicates)

            if self.use_ai and self.ai_client is not None:
                decision = self._try_ai_classification(
                    alert=alert,
                    seen_alerts=seen_for_duplicates,
                    fallback_decision=decision,
                )

            if (
                decision["is_relevant"]
                and self.profile_relevance is not None
            ):
                is_user_relevant, profile_reason = self.profile_relevance.is_relevant_for_user(alert)
                if not is_user_relevant:
                    decision = {
                        "is_relevant": False,
                        "reason": profile_reason,
                        "duplicate_of": None,
                    }

            result = FilteredResult(
                alert=alert,
                is_relevant=decision["is_relevant"],
                reason=decision["reason"],
                duplicate_of=decision["duplicate_of"],
            )
            results.append(result)
            # Track processed alerts for duplicate detection independent of relevance/profile outcome.
            if alert.content.strip():
                seen_for_duplicates.append(alert)
            if result.is_relevant:
                seen_relevant.append(alert)
            if progress_hook is not None:
                progress_hook(stage="filter", processed=idx, total=total, alert_id=alert.id)
        return seen_relevant, results

    def _try_ai_classification(self, alert: Alert, seen_alerts: list[Alert], fallback_decision: dict) -> dict:
        try:
            user_profile = self.profile_relevance.profile if self.profile_relevance is not None else None
            payload = self.ai_client.generate_response(build_filter_prompt(alert, seen_alerts, user_profile))
            is_relevant = bool(payload.get("is_relevant", False))
            reason = str(payload.get("reason", "ai_decision")).strip() or "ai_decision"
            is_duplicate = bool(payload.get("is_duplicate", False))
            duplicate_of_raw = payload.get("duplicate_of")
            valid_candidate_ids = {item.id for item in seen_alerts}
            duplicate_of = duplicate_of_raw if isinstance(duplicate_of_raw, int) else None

            if is_duplicate and duplicate_of in valid_candidate_ids:
                return {
                    "is_relevant": False,
                    "reason": reason or "ai_duplicate",
                    "duplicate_of": duplicate_of,
                }
            if is_duplicate and duplicate_of not in valid_candidate_ids:
                # Invalid AI pointer -> rely on fallback duplicate verdict for safety.
                self.fallback_events.append(
                    {"stage": "filter", "alert_id": alert.id, "reason": "invalid_ai_duplicate_pointer"}
                )
                return fallback_decision

            return {"is_relevant": is_relevant, "reason": reason, "duplicate_of": None}
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("AI filtering failed for alert %s: %s", alert.id, exc)
            logger.info("Using fallback filter result for alert %s", alert.id)
            self.fallback_events.append(
                {"stage": "filter", "alert_id": alert.id, "reason": "ai_error"}
            )
            return fallback_decision
