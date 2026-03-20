from app.models.alert import Alert

TEMPLATES = {
    "phishing": {
        "why": "Residents may lose money or account access if they follow fake links.",
        "actions": [
            "Do not click unknown links or attachments.",
            "Verify requests through official channels only.",
            "Report suspicious messages to local cyber support.",
        ],
    },
    "scam": {
        "why": "Impersonation scams pressure people into urgent payments.",
        "actions": [
            "Do not transfer money or buy gift cards for unknown callers.",
            "End the call and verify with official numbers.",
            "Share a warning with family members who may be targeted.",
        ],
    },
    "outage": {
        "why": "Service disruption can affect communication, payments, and daily routines.",
        "actions": [
            "Plan alternatives for internet/power dependent tasks.",
            "Use verified provider updates to track restoration.",
            "Keep essential devices charged when possible.",
        ],
    },
    "breach": {
        "why": "Compromised accounts can expose personal data and spread abuse.",
        "actions": [
            "Reset passwords immediately and enable multi-factor authentication.",
            "Review recent account activity for unknown logins.",
            "Warn other users to secure their accounts.",
        ],
    },
    "general": {
        "why": "The signal may matter if more verified evidence appears.",
        "actions": [
            "Monitor official updates.",
            "Avoid sharing unverified claims.",
        ],
    },
}

FLOOD_TERMS = {"flood", "flooding", "rain", "rainfall", "river", "evacuation", "warning"}
FLOOD_OUTAGE_TEMPLATE = {
    "why": "Flood warnings indicate immediate safety risks to people, transport, and property.",
    "actions": [
        "Monitor official weather and emergency alerts continuously.",
        "Avoid low-lying roads and do not move through floodwater.",
        "Prepare an emergency kit and charge essential devices.",
        "Follow evacuation instructions from local authorities immediately when issued.",
    ],
}


def build_insight(alert: Alert) -> dict:
    category = alert.category.lower()
    template = TEMPLATES.get(category, TEMPLATES["general"])
    content_lower = alert.content.lower()
    if category == "outage" and any(term in content_lower for term in FLOOD_TERMS):
        template = FLOOD_OUTAGE_TEMPLATE
    why = f"Stay calm. {template['why']} Reported near {alert.location}."
    actions = template["actions"][:4]
    return {"why": why, "actions": actions}
