import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from .config import load
from .history import History
from .monitor import run
from .providers.mock import MockProvider
from .schedule import scheduled_slot


def main() -> None:
    parser = argparse.ArgumentParser(description="FlightHunter v0.1 (mock data)")
    parser.add_argument("--config", type=Path, default=Path("config/searches.toml"))
    parser.add_argument("--history", type=Path, default=Path("data/prices.jsonl"))
    parser.add_argument("--scheduled-cron", help="GitHub event.schedule, nominal UTC cron")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    run_id = None
    if args.scheduled_cron:
        run_id = scheduled_slot(args.scheduled_cron, now)
        if run_id is None:
            print("Inactive CET/CEST candidate: skipped")
            return
    rows = run(load(args.config), MockProvider(), History(args.history), now, run_id)
    for row in rows:
        print(json.dumps(row))
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(f"## FlightHunter (MOCK)\n{len(rows)} observations; "
                         f"{sum(bool(row['alerts']) for row in rows)} with alerts.\n")


if __name__ == "__main__":
    main()
