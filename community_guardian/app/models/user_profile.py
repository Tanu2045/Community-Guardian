from dataclasses import dataclass, field


@dataclass(frozen=True)
class UserProfile:
    persona: str = "general"
    primary_location: str = ""
    watch_locations: list[str] = field(default_factory=list)
    focus_categories: list[str] = field(default_factory=list)
