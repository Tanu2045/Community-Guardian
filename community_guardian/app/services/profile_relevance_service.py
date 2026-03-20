import re

from app.models.alert import Alert
from app.models.user_profile import UserProfile

ALL_CATEGORIES = {"phishing", "scam", "breach", "outage", "general"}

PERSONA_CATEGORY_HINTS: dict[str, set[str]] = {
    "phishing": {"student", "teacher", "parent", "family", "shop", "small", "business", "home"},
    "scam": {"elderly", "senior", "retired", "housewife", "homemaker", "family", "govt", "government"},
    "breach": {"remote", "worker", "it", "tech", "developer", "office", "employee", "government", "govt", "student"},
    "outage": {"house", "home", "resident", "neighborhood", "shop", "business", "student", "worker", "elderly"},
}

STRICT_LOCATION_HINTS = {
    "housewife", "homemaker", "elderly", "senior", "retired", "resident", "neighborhood", "family", "parent"
}


class ProfileRelevanceService:
    def __init__(self, profile: UserProfile) -> None:
        self.profile = profile

    def is_relevant_for_user(self, alert: Alert) -> tuple[bool, str]:
        focus = self._resolved_focus_categories()

        watched_locations = {
            self._norm(loc)
            for loc in ([self.profile.primary_location] + list(self.profile.watch_locations or []))
            if loc and loc.strip()
        }

        alert_category = alert.category.strip().lower()
        alert_location = self._norm(alert.location)
        location_match = (
            not watched_locations
            or self._location_match(alert_location, watched_locations)
            or alert_location == "citywide"
        )
        category_match = not focus or alert_category in focus

        if category_match and location_match:
            return True, "profile_match"

        if self._is_strict_location_profile() and not location_match:
            return False, "profile_location_mismatch"
        if not category_match:
            return False, "profile_category_mismatch"
        return False, "profile_mismatch"

    def _resolved_focus_categories(self) -> set[str]:
        explicit = {
            c.strip().lower()
            for c in (self.profile.focus_categories or [])
            if c and c.strip()
        }
        explicit = explicit & ALL_CATEGORIES
        if explicit:
            return explicit

        # Adaptive fallback: infer likely interests from free-form persona text.
        persona_text = (self.profile.persona or "").strip().lower()
        tokens = set(re.findall(r"[a-z0-9_]+", persona_text))
        if not tokens:
            return set()

        scores = {c: 0 for c in ALL_CATEGORIES if c != "general"}
        for category, hints in PERSONA_CATEGORY_HINTS.items():
            overlap = len(tokens & hints)
            if overlap:
                scores[category] += overlap

        top_score = max(scores.values(), default=0)
        if top_score == 0:
            return set()
        # Keep categories with near-top affinity to avoid overfitting one label.
        inferred = {cat for cat, score in scores.items() if score >= max(1, top_score - 1)}
        return inferred

    def _is_strict_location_profile(self) -> bool:
        if self.profile.primary_location.strip() or any(loc.strip() for loc in self.profile.watch_locations):
            return True
        tokens = set(re.findall(r"[a-z0-9_]+", (self.profile.persona or "").strip().lower()))
        return bool(tokens & STRICT_LOCATION_HINTS)

    @staticmethod
    def _norm(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", value.lower())).strip()

    def _location_match(self, alert_location: str, watched_locations: set[str]) -> bool:
        for watched in watched_locations:
            if not watched:
                continue
            if alert_location == watched:
                return True
            # Free-form resilience: partial phrase match either direction.
            if watched in alert_location or alert_location in watched:
                return True
            # Token overlap fallback for mildly different phrasings.
            alert_tokens = set(alert_location.split())
            watched_tokens = set(watched.split())
            if alert_tokens and watched_tokens and len(alert_tokens & watched_tokens) >= 1:
                return True
        return False
