"""Resolve the nominal UTC cron occurrence, even when Actions starts late."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SLOTS = {"00:10", "06:00", "11:00"}
CRONS = {"10 22 * * *": (22, 10), "10 23 * * *": (23, 10),
         "0 4 * * *": (4, 0), "0 5 * * *": (5, 0),
         "0 9 * * *": (9, 0), "0 10 * * *": (10, 0)}


def scheduled_slot(cron: str, now: datetime) -> str | None:
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    hour, minute = CRONS[cron]
    now = now.astimezone(timezone.utc)
    nominal = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if nominal > now:
        nominal -= timedelta(days=1)
    if now - nominal > timedelta(hours=12):
        raise ValueError("Scheduled event is too old or clock is inconsistent")
    local = nominal.astimezone(ZoneInfo("Europe/Rome"))
    return local.strftime("%Y-%m-%dT%H:%M") if local.strftime("%H:%M") in SLOTS else None
