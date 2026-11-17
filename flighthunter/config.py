from decimal import Decimal
from pathlib import Path
import re
import tomllib
from .models import Search, airport, money


def load(path: Path) -> list[Search]:
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    if config.get("provider", "mock") != "mock":
        raise ValueError("Only mock is implemented in v0.1")
    searches = []
    ids = set()
    for item in config.get("searches", []):
        identifier = item["id"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", identifier) or identifier in ids:
            raise ValueError("Search IDs must be unique and alphanumeric")
        ids.add(identifier)
        destination = item.get("destination", "ANYWHERE").upper()
        if destination != "ANYWHERE":
            destination = airport(destination)
        currency = item.get("currency", "EUR").upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("Invalid currency")
        start, end = item.get("departure_after_days", 7), item.get("departure_before_days", 30)
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= 365:
            raise ValueError("Departure offsets must satisfy 0 <= start <= end <= 365")
        drop = Decimal(str(item.get("drop_percent", 10)))
        if not drop.is_finite() or not 0 < drop <= 100:
            raise ValueError("drop_percent must be in (0, 100]")
        searches.append(Search(identifier, airport(item["origin"]), destination,
                               currency, start, end, drop,
                               money(item["threshold"]) if "threshold" in item else None))
    if not searches:
        raise ValueError("Configure at least one search")
    return searches
