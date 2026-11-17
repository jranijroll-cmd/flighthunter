from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from .history import History
from .models import Offer, Search
from .providers.base import FlightProvider


def alerts(offer: Offer, previous: list[dict], search: Search) -> list[str]:
    prices = [Decimal(row["price"]) for row in previous
              if row["search_id"] == search.id and tuple(row["comparison_key"]) == offer.key]
    found = []
    if prices:
        if (prices[-1] - offer.price) / prices[-1] * 100 >= search.drop_percent:
            found.append("percentage_drop")
        if offer.price < min(prices):
            found.append("new_all_time_low")
    if search.threshold is not None and offer.price < search.threshold:
        found.append("below_threshold")
    return found


def run(searches: list[Search], provider: FlightProvider, history: History,
        now: datetime | None = None, run_id: str | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    previous = history.read()
    if run_id and any(row.get("run_id") == run_id for row in previous):
        return []
    rows = []
    for search in searches:
        # Keep the cheapest duplicate quote per comparable itinerary.
        offers = {}
        today = now.astimezone(ZoneInfo("Europe/Rome")).date()
        for offer in provider.search(search, today):
            if (offer.origin != search.origin or offer.currency != search.currency
                    or offer.destination == search.origin
                    or search.destination not in ("ANYWHERE", offer.destination)
                    or not today + timedelta(days=search.departure_after_days) <= offer.departure_date
                    <= today + timedelta(days=search.departure_before_days)):
                raise ValueError("Provider returned an offer outside the search constraints")
            if offer.key not in offers or offer.price < offers[offer.key].price:
                offers[offer.key] = offer
        for offer in offers.values():
            rows.append(dict(schema_version=1, search_id=search.id, run_id=run_id,
                             observed_at=now.astimezone(timezone.utc).isoformat(),
                             comparison_key=list(offer.key), alerts=alerts(offer, previous, search),
                             **offer.record()))
    history.append(rows)
    return rows
