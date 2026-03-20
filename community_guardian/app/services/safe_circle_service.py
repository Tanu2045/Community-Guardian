from datetime import datetime, timezone

from app.models.safe_circle import SafeCircle

ALLOWED_STATUS = {"SAFE", "NEED_HELP", "AVOID_AREA"}


class SafeCircleService:
    def __init__(self) -> None:
        self._circles: dict[str, SafeCircle] = {}

    def create_circle(self, name: str, members: list[str] | None = None) -> SafeCircle:
        circle = SafeCircle(name=name, members=list(members or []))
        self._circles[name] = circle
        return circle

    def add_member(self, circle_name: str, member: str) -> None:
        circle = self._get_circle(circle_name)
        if member not in circle.members:
            circle.members.append(member)

    def send_status(self, circle_name: str, member: str, status: str, note: str = "") -> dict:
        if status not in ALLOWED_STATUS:
            raise ValueError(f"status must be one of: {sorted(ALLOWED_STATUS)}")
        circle = self._get_circle(circle_name)
        if member not in circle.members:
            raise ValueError(f"{member} is not a member of {circle_name}")
        update = {
            "member": member,
            "status": status,
            "note": note.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        circle.updates.append(update)
        return update

    def get_updates(self, circle_name: str) -> list[dict]:
        return list(self._get_circle(circle_name).updates)

    def list_circles(self) -> list[str]:
        return sorted(self._circles.keys())

    def get_members(self, circle_name: str) -> list[str]:
        return list(self._get_circle(circle_name).members)

    def _get_circle(self, name: str) -> SafeCircle:
        circle = self._circles.get(name)
        if not circle:
            raise ValueError(f"Circle '{name}' does not exist")
        return circle
