from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    id: int
    source: str
    content: str
    location: str
    timestamp: str
    category: str = ""
