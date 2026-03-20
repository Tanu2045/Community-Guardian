from dataclasses import dataclass


@dataclass(frozen=True)
class Insight:
    alert_id: int
    why: str
    actions: list[str]
