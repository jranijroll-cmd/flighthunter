from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re


def money(value: object) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite() or result <= 0:
        raise ValueError("Price must be finite and positive")
    result = result.quantize(Decimal("0.01"))
    if result <= 0:
        raise ValueError("Price rounds to zero")
    return result


def airport(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError(f"Invalid IATA code: {value}")
    return value


@dataclass(frozen=True)
class Search:
    id: str
    origin: str
    destination: str
    currency: str
    departure_after_days: int
    departure_before_days: int
    drop_percent: Decimal
    threshold: Decimal | None


@dataclass(frozen=True)
class Offer:
    origin: str
    destination: str
    departure_date: date
    price: Decimal
    currency: str
    provider: str
    carrier: str
    booking_url: str | None = None

    @property
    def key(self) -> tuple[str, ...]:
        # Compare like-for-like one-way, one-adult quotes, including carrier.
        return (self.origin, self.destination, self.departure_date.isoformat(),
                self.currency, self.provider, self.carrier)

    def record(self) -> dict:
        return dict(origin=self.origin, destination=self.destination,
                    departure_date=self.departure_date.isoformat(), price=str(self.price),
                    currency=self.currency, provider=self.provider, carrier=self.carrier,
                    booking_url=self.booking_url)


def normalize(raw: dict, provider: str) -> Offer:
    currency = str(raw["currency"]).strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("Invalid currency")
    carrier = str(raw["carrier"]).strip().upper()
    if not carrier:
        raise ValueError("Missing carrier")
    return Offer(airport(raw["origin"]), airport(raw["destination"]),
                 date.fromisoformat(raw["departure_date"]), money(raw["price"]),
                 currency, provider, carrier, raw.get("booking_url"))
