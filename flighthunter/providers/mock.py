from datetime import date, timedelta
from .base import FlightProvider
from ..models import Offer, Search, normalize


class MockProvider(FlightProvider):
    name = "mock"

    def search(self, search: Search, today: date) -> list[Offer]:
        destinations = ["BCN", "LIS", "CDG"] if search.destination == "ANYWHERE" else [search.destination]
        return [normalize(dict(origin=search.origin, destination=destination,
                               departure_date=(today + timedelta(days=search.departure_after_days)).isoformat(),
                               price=str(49 + index * 25), currency=search.currency,
                               carrier="MOCK"), self.name)
                for index, destination in enumerate(destinations) if destination != search.origin]
