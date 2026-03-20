from app.models.framed_alert import FramedAlert
from app.models.insight import Insight


class DigestService:
    @staticmethod
    def build_digest(
        framed_alerts: list[FramedAlert],
        insights: list[Insight],
        filter_results: list | None = None,
    ) -> list[dict]:
        insight_map = {item.alert_id: item for item in insights}
        report_count_by_alert = DigestService._build_report_counts(filter_results or [])
        digest: list[dict] = []
        for framed in framed_alerts:
            insight = insight_map.get(framed.alert.id)
            report_count = report_count_by_alert.get(framed.alert.id, 1)
            digest.append(
                {
                    "id": framed.alert.id,
                    "source": framed.alert.source,
                    "category": framed.alert.category,
                    "location": framed.alert.location,
                    "timestamp": framed.alert.timestamp,
                    "framed_text": framed.framed_text,
                    "confidence": framed.confidence,
                    "relevance_reason": framed.relevance,
                    "attention_guidance": framed.guidance,
                    "why_this_matters": insight.why if insight else "",
                    "actions": insight.actions if insight else [],
                    "report_count": report_count,
                    "verification_signal": DigestService._verification_signal(report_count),
                }
            )
        return digest

    @staticmethod
    def _verification_signal(report_count: int) -> str:
        if report_count >= 4:
            return "high"
        if report_count >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _build_report_counts(filter_results: list) -> dict[int, int]:
        if not filter_results:
            return {}

        result_by_id = {item.alert.id: item for item in filter_results}

        def root_alert_id(alert_id: int) -> int:
            visited: set[int] = set()
            current = alert_id
            while current in result_by_id:
                item = result_by_id[current]
                parent = item.duplicate_of
                if parent is None or parent in visited or parent not in result_by_id:
                    return current
                visited.add(current)
                current = parent
            return alert_id

        cluster_sizes: dict[int, int] = {}
        root_by_alert: dict[int, int] = {}
        for item in filter_results:
            alert_id = item.alert.id
            root_id = root_alert_id(alert_id)
            root_by_alert[alert_id] = root_id
            cluster_sizes[root_id] = cluster_sizes.get(root_id, 0) + 1

        return {alert_id: cluster_sizes.get(root_id, 1) for alert_id, root_id in root_by_alert.items()}

    @staticmethod
    def filter_digest(
        digest: list[dict],
        category: str | None = None,
        query: str | None = None,
    ) -> list[dict]:
        items = digest
        if category:
            items = [d for d in items if d["category"].lower() == category.lower()]
        if query:
            needle = query.lower()
            items = [
                d
                for d in items
                if needle in d["framed_text"].lower()
                or needle in d["why_this_matters"].lower()
                or needle in d["location"].lower()
            ]
        return items
