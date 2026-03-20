from dataclasses import replace

from app.ai.prompts import build_category_prompt
from app.models.alert import Alert
from app.utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_CATEGORIES = {"phishing", "scam", "breach", "outage", "general"}

KEYWORDS_BY_CATEGORY = {
    "phishing": {
        "phishing",
        "sms",
        "fake",
        "otp",
        "link",
        "donation",
        "impersonat",
        "spoof",
        "credential",
        "verify account",
        "urgent message",
    },
    "scam": {
        "scam",
        "gift card",
        "caller",
        "payment",
        "police",
        "fraud",
        "extortion",
        "lottery",
        "prize",
        "refund",
        "upi",
    },
    "breach": {
        "breach",
        "login",
        "password",
        "ransomware",
        "compromised",
        "data leak",
        "account takeover",
        "unauthorized access",
        "credential stuffing",
        "malware",
    },
    "outage": {
        "outage",
        "power",
        "internet",
        "fiber",
        "service down",
        "flood",
        "flooding",
        "flood warning",
        "heavy rain",
        "rainfall",
        "storm",
        "cyclone",
        "weather alert",
        "landslide",
        "road blocked",
        "waterlogging",
    },
}

AI_CATEGORY_NORMALIZATION = {
    "phishing": "phishing",
    "sms_fraud": "phishing",
    "impersonation": "phishing",
    "social_engineering": "phishing",
    "scam": "scam",
    "fraud": "scam",
    "breach": "breach",
    "cyber_breach": "breach",
    "ransomware": "breach",
    "data_breach": "breach",
    "outage": "outage",
    "service_disruption": "outage",
    "flood": "outage",
    "weather": "outage",
    "hazard": "outage",
    "natural_disaster": "outage",
    "general": "general",
}


class CategoryService:
    def __init__(self, use_ai: bool = False, ai_client=None, user_profile=None, fallback_events: list[dict] | None = None) -> None:
        self.use_ai = use_ai
        self.ai_client = ai_client
        self.user_profile = user_profile
        self.fallback_events = fallback_events if fallback_events is not None else []

    def classify_alerts(self, alerts: list[Alert], progress_hook=None) -> list[Alert]:
        items: list[Alert] = []
        total = len(alerts)
        for idx, alert in enumerate(alerts, start=1):
            items.append(self._classify_one(alert))
            if progress_hook is not None:
                progress_hook(stage="category", processed=idx, total=total, alert_id=alert.id)
        return items

    def _classify_one(self, alert: Alert) -> Alert:
        category = None
        if self.use_ai and self.ai_client is not None:
            category = self._try_ai_category(alert)
        if category not in ALLOWED_CATEGORIES:
            if self.use_ai and self.ai_client is not None:
                self.fallback_events.append(
                    {"stage": "category", "alert_id": alert.id, "reason": "fallback_category_rules"}
                )
            category = self._fallback_category(alert)
        return replace(alert, category=category)

    def _try_ai_category(self, alert: Alert) -> str | None:
        try:
            payload = self.ai_client.generate_response(build_category_prompt(alert, self.user_profile))
            category = self._normalize_ai_category(str(payload.get("category", "")))
            return category if category in ALLOWED_CATEGORIES else None
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("AI category classification failed for alert %s: %s", alert.id, exc)
            logger.info("Using fallback category classification for alert %s", alert.id)
            self.fallback_events.append(
                {"stage": "category", "alert_id": alert.id, "reason": "ai_error"}
            )
            return None

    @staticmethod
    def _fallback_category(alert: Alert) -> str:
        text = alert.content.lower()
        scores = {k: 0 for k in KEYWORDS_BY_CATEGORY}
        for category, words in KEYWORDS_BY_CATEGORY.items():
            for keyword in words:
                if keyword in text:
                    scores[category] += 1
        best_category = max(scores, key=scores.get)
        return best_category if scores[best_category] > 0 else "general"

    @staticmethod
    def _normalize_ai_category(raw: str) -> str:
        cleaned = raw.strip().lower().replace("-", "_").replace(" ", "_")
        if cleaned in AI_CATEGORY_NORMALIZATION:
            return AI_CATEGORY_NORMALIZATION[cleaned]
        # Loose fallback mappings for descriptive AI outputs.
        if any(k in cleaned for k in {"flood", "storm", "weather", "hazard", "disaster"}):
            return "outage"
        if any(k in cleaned for k in {"ransomware", "breach", "compromise", "leak"}):
            return "breach"
        if any(k in cleaned for k in {"phish", "spoof", "impersonat"}):
            return "phishing"
        if any(k in cleaned for k in {"scam", "fraud", "extortion"}):
            return "scam"
        return cleaned
