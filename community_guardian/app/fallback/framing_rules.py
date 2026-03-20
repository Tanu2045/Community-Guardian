from app.models.alert import Alert

ATTENTION_BY_CATEGORY = {
    "phishing": "act_now",
    "scam": "act_now",
    "breach": "act_soon",
    "outage": "monitor",
    "general": "monitor",
}


def _confidence(alert: Alert) -> str:
    base = 0
    if alert.source == "security_feed":
        base += 2
    elif alert.source == "news":
        base += 1
    if len(alert.content.split()) >= 12:
        base += 1
    if alert.category in {"phishing", "scam", "breach", "outage"}:
        base += 1
    if base >= 4:
        return "high"
    if base >= 2:
        return "medium"
    return "low"


def frame_alert(alert: Alert) -> dict:
    category = alert.category.lower()
    attention = ATTENTION_BY_CATEGORY.get(category, "monitor")
    framing_text = (
        f"Stay calm and take practical steps. {category.title()} alert reported in {alert.location}. "
        f"{alert.content.strip()}"
    )
    return {
        "framed_text": framing_text,
        "confidence": _confidence(alert),
        "relevance": f"Matched {category} signal from {alert.source}",
        "guidance": attention,
    }
