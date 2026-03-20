from typing import Any

from app.models.alert import Alert

REQUIRED_FIELDS = {"id", "source", "content", "location", "timestamp"}


def validate_raw_alert(raw: dict[str, Any]) -> tuple[bool, str]:
    missing = REQUIRED_FIELDS - raw.keys()
    if missing:
        return False, f"missing fields: {', '.join(sorted(missing))}"
    if not isinstance(raw["id"], int):
        return False, "id must be int"
    if not isinstance(raw["source"], str):
        return False, "source must be str"
    if not isinstance(raw["content"], str):
        return False, "content must be str"
    if not isinstance(raw["location"], str):
        return False, "location must be str"
    if not isinstance(raw["timestamp"], str):
        return False, "timestamp must be str"
    if "category" in raw and not isinstance(raw["category"], str):
        return False, "category must be str when provided"
    return True, "ok"


def to_alert(raw: dict[str, Any]) -> Alert:
    category = raw.get("category", "")
    category = category.strip() if isinstance(category, str) else ""
    return Alert(
        id=raw["id"],
        source=raw["source"],
        content=raw["content"],
        location=raw["location"],
        timestamp=raw["timestamp"],
        category=category,
    )
