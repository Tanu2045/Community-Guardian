from dataclasses import dataclass

from app.models.alert import Alert


@dataclass(frozen=True)
class FramedAlert:
    alert: Alert
    framed_text: str
    confidence: str
    relevance: str
    guidance: str
