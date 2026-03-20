import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    gemini_api_key: str
    use_ai: bool
    data_path: Path
    output_dir: Path
    user_persona: str
    user_primary_location: str
    user_watch_locations: list[str]
    user_focus_categories: list[str]


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config(base_dir: Path | None = None) -> Config:
    root = Path(base_dir or Path(__file__).resolve().parents[1])
    load_dotenv(root / ".env")
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    use_ai = _to_bool(os.getenv("USE_AI", "false"), default=False)
    data_path = root / "data" / "alerts.json"
    output_dir = root / "output"
    user_persona = os.getenv("USER_PERSONA", "general").strip().lower() or "general"
    user_primary_location = os.getenv("USER_PRIMARY_LOCATION", "").strip()
    user_watch_locations = _to_list(os.getenv("USER_WATCH_LOCATIONS", ""))
    user_focus_categories = _to_list(os.getenv("USER_FOCUS_CATEGORIES", ""))
    return Config(
        gemini_api_key=gemini_api_key,
        use_ai=use_ai,
        data_path=data_path,
        output_dir=output_dir,
        user_persona=user_persona,
        user_primary_location=user_primary_location,
        user_watch_locations=user_watch_locations,
        user_focus_categories=user_focus_categories,
    )
