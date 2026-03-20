import json
from pathlib import Path

from app.models.alert import Alert
from app.utils.logger import get_logger
from app.utils.validator import to_alert, validate_raw_alert

logger = get_logger(__name__)


def load_alerts(data_path: str | Path) -> list[Alert]:
    path = Path(data_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("alerts dataset must be a JSON array")

    alerts: list[Alert] = []
    for row in payload:
        if not isinstance(row, dict):
            logger.warning("Skipping non-object alert row: %s", row)
            continue
        ok, reason = validate_raw_alert(row)
        if not ok:
            logger.warning("Skipping malformed alert id=%s: %s", row.get("id"), reason)
            continue
        alerts.append(to_alert(row))
    return alerts
