from app.models.alert import Alert


def _profile_context(user_profile=None) -> str:
    if user_profile is None:
        return "User profile context: not provided."
    persona = getattr(user_profile, "persona", "") or "general"
    primary_location = getattr(user_profile, "primary_location", "") or "any"
    watch_locations = getattr(user_profile, "watch_locations", []) or []
    focus_categories = getattr(user_profile, "focus_categories", []) or []
    watch_text = ", ".join(watch_locations) if watch_locations else "none"
    focus_text = ", ".join(focus_categories) if focus_categories else "none"
    return (
        "User profile context:\n"
        f"- persona: {persona}\n"
        f"- primary_location: {primary_location}\n"
        f"- watch_locations: {watch_text}\n"
        f"- focus_categories: {focus_text}"
    )


def build_filter_prompt(alert: Alert, seen_alerts: list[Alert], user_profile=None) -> str:
    candidates = seen_alerts[-25:]
    candidate_lines = [
        f"- id={item.id}, source={item.source}, category={item.category}, "
        f"location={item.location}, content={item.content}"
        for item in candidates
    ]
    candidate_block = "\n".join(candidate_lines) if candidate_lines else "- none"
    return (
        "You are classifying one community alert.\n"
        "Tasks:\n"
        "1) Decide if current alert is relevant.\n"
        "2) Decide if it is a duplicate of a previous alert from the candidate list.\n"
        "Duplicate means same incident/update even if wording is different.\n"
        "Return strict JSON: "
        "{\"is_relevant\": bool, \"reason\": str, \"is_duplicate\": bool, \"duplicate_of\": int|null}.\n"
        "If duplicate, duplicate_of must be one candidate id. If not duplicate, duplicate_of must be null.\n"
        f"{_profile_context(user_profile)}\n"
        f"Candidate previous alerts:\n{candidate_block}\n"
        f"Alert: source={alert.source}, category={alert.category}, "
        f"location={alert.location}, content={alert.content}"
    )


def build_framing_prompt(alert: Alert, user_profile=None) -> str:
    return (
        "Create neutral framing without adding facts. "
        "Use calm, reassuring, non-alarmist language. "
        "A brief grounding line is allowed if it helps reduce anxiety. "
        "Return JSON with keys: framed_text, confidence, relevance, guidance.\n"
        f"{_profile_context(user_profile)}\n"
        f"Alert: source={alert.source}, category={alert.category}, "
        f"location={alert.location}, content={alert.content}"
    )


def build_insight_prompt(alert: Alert, user_profile=None) -> str:
    return (
        "Generate concise safety insight. Return JSON with keys: why, actions "
        "(array of 2 to 4 clear steps). "
        "Tone must be calm and practical: reduce anxiety, avoid panic language, "
        "and focus on what people can do next.\n"
        f"{_profile_context(user_profile)}\n"
        f"Alert: source={alert.source}, category={alert.category}, "
        f"location={alert.location}, content={alert.content}"
    )


def build_category_prompt(alert: Alert, user_profile=None) -> str:
    return (
        "Classify the alert into exactly one category. "
        "Allowed categories: phishing, scam, breach, outage, general. "
        "Map weather/flood/disaster/public-hazard disruptions to outage. "
        "Return JSON: {\"category\": str}.\n"
        f"{_profile_context(user_profile)}\n"
        f"Alert: source={alert.source}, location={alert.location}, content={alert.content}"
    )
