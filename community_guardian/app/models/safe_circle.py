from dataclasses import dataclass, field


@dataclass
class SafeCircle:
    name: str
    members: list[str]
    updates: list[dict] = field(default_factory=list)
