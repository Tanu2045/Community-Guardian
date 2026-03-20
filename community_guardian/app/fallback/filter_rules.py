import re
from datetime import datetime
from difflib import SequenceMatcher

from app.models.alert import Alert

RELEVANT_CATEGORIES = {"phishing", "outage", "scam", "breach"}
RELEVANT_KEYWORDS = {
    "phishing",
    "scam",
    "fraud",
    "breach",
    "outage",
    "password",
    "fake",
    "urgent",
    "login",
    "flood",
    "flooding",
    "rain",
    "warning",
    "evacuation",
    "ransomware",
    "malware",
    "compromised",
    "internet",
    "power",
    "storm",
    "cyclone",
    "waterlogging",
    "police",
    "gift",
    "card",
}
VAGUE_MESSAGES = {
    "wow",
    "help??",
    "idk",
    "whatever",
    "everything is broken in this city, nobody cares anymore.",
}

TOKEN_NORMALIZATION = {
    "sms": "message",
    "msg": "message",
    "texts": "text",
    "textsmsg": "text",
    "jam": "traffic",
    "gridlock": "traffic",
    "congestion": "traffic",
    "down": "outage",
    "offline": "outage",
    "blackout": "outage",
    "fraudulent": "fraud",
    "scammed": "scam",
    "phished": "phishing",
    "compromise": "compromised",
    "breached": "breach",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "is",
    "it",
    "its",
    "no",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "there",
    "this",
    "to",
    "was",
    "were",
    "with",
}

DUPLICATE_TIME_WINDOW_HOURS = 24
HIGH_TEXT_SIMILARITY_RATIO = 0.90
HIGH_TEXT_SIMILARITY_JACCARD = 0.60
STRONG_TOKEN_OVERLAP_MIN = 3
STRONG_BIGRAM_OVERLAP_MIN = 1
STRONG_OVERLAP_JACCARD_MIN = 0.40
AMBIGUOUS_LOCATIONS = {"unknown", "citywide", "city wide", ""}


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def canonical_tokens(content: str, location: str) -> set[str]:
    combined = f"{content} {location}"
    tokens = set(normalize_text(combined).split())
    normalized: set[str] = set()
    for token in tokens:
        mapped = TOKEN_NORMALIZATION.get(token, token)
        if mapped and mapped not in STOPWORDS and len(mapped) >= 3:
            normalized.add(mapped)
    return normalized


def canonical_bigrams(content: str, location: str) -> set[str]:
    combined = f"{content} {location}"
    words = [w for w in normalize_text(combined).split() if w not in STOPWORDS and len(w) >= 3]
    mapped = [TOKEN_NORMALIZATION.get(w, w) for w in words]
    return {f"{mapped[i]} {mapped[i + 1]}" for i in range(len(mapped) - 1)}


def _parse_iso_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_large_time_gap(current_timestamp: str, previous_timestamp: str) -> bool:
    current_dt = _parse_iso_timestamp(current_timestamp)
    previous_dt = _parse_iso_timestamp(previous_timestamp)
    if current_dt is None or previous_dt is None:
        return False
    diff_seconds = abs((current_dt - previous_dt).total_seconds())
    return diff_seconds > (DUPLICATE_TIME_WINDOW_HOURS * 3600)


def _locations_clearly_different(current_location: str, previous_location: str) -> bool:
    current = normalize_text(current_location)
    previous = normalize_text(previous_location)
    if current == previous:
        return False
    if current in AMBIGUOUS_LOCATIONS or previous in AMBIGUOUS_LOCATIONS:
        return False
    current_tokens = set(current.split())
    previous_tokens = set(previous.split())
    if current_tokens & previous_tokens:
        return False
    return True


def evaluate_alert(alert: Alert, seen_relevant: list[Alert]) -> dict:
    content = alert.content.strip()
    if not content:
        return {"is_relevant": False, "reason": "empty_content", "duplicate_of": None}

    if len(content) < 12:
        return {"is_relevant": False, "reason": "too_short", "duplicate_of": None}

    norm = normalize_text(content)
    if norm in VAGUE_MESSAGES:
        return {"is_relevant": False, "reason": "vague_message", "duplicate_of": None}

    alert_location = normalize_text(alert.location)
    alert_tokens = canonical_tokens(alert.content, alert.location)
    alert_bigrams = canonical_bigrams(alert.content, alert.location)

    for existing in seen_relevant:
        if _locations_clearly_different(alert.location, existing.location):
            continue

        if _is_large_time_gap(alert.timestamp, existing.timestamp):
            continue

        existing_norm = normalize_text(existing.content)
        existing_tokens = canonical_tokens(existing.content, existing.location)
        existing_bigrams = canonical_bigrams(existing.content, existing.location)
        if norm == existing_norm:
            return {
                "is_relevant": False,
                "reason": "duplicate_exact",
                "duplicate_of": existing.id,
            }
        ratio = SequenceMatcher(None, norm, existing_norm).ratio()
        union = alert_tokens | existing_tokens
        jaccard = (len(alert_tokens & existing_tokens) / len(union)) if union else 0.0
        token_overlap = len(alert_tokens & existing_tokens)
        bigram_overlap = len(alert_bigrams & existing_bigrams)

        if ratio >= HIGH_TEXT_SIMILARITY_RATIO or jaccard >= HIGH_TEXT_SIMILARITY_JACCARD:
            return {
                "is_relevant": False,
                "reason": "duplicate_near",
                "duplicate_of": existing.id,
            }
        if (
            (token_overlap >= STRONG_TOKEN_OVERLAP_MIN and jaccard >= STRONG_OVERLAP_JACCARD_MIN)
            or (bigram_overlap >= STRONG_BIGRAM_OVERLAP_MIN and token_overlap >= STRONG_TOKEN_OVERLAP_MIN)
        ):
            return {
                "is_relevant": False,
                "reason": "duplicate_event",
                "duplicate_of": existing.id,
            }

    if alert.category.lower() in RELEVANT_CATEGORIES:
        return {"is_relevant": True, "reason": "category_match", "duplicate_of": None}

    words = set(norm.split())
    if words & RELEVANT_KEYWORDS:
        return {"is_relevant": True, "reason": "keyword_match", "duplicate_of": None}

    return {"is_relevant": False, "reason": "low_signal", "duplicate_of": None}
