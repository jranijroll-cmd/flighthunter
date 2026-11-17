from abc import ABC, abstractmethod
from datetime import date
from ..models import Offer, Search


class FlightProvider(ABC):
    """Adapters own authentication, discovery and normalization of external data.

    Return total one-way fares for one adult in the requested currency, without
    currency conversion. Unsupported capabilities must raise explicitly.
    ANYWHERE adapters may discover destinations then fan out route requests.
    """
    name: str

    @abstractmethod
    def search(self, search: Search, today: date) -> list[Offer]:
        raise NotImplementedError
