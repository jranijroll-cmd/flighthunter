from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from flighthunter.config import load
from flighthunter.history import History
from flighthunter.models import normalize
from flighthunter.monitor import alerts, run
from flighthunter.providers.mock import MockProvider
from flighthunter.schedule import CRONS, scheduled_slot

ROOT = Path(__file__).resolve().parents[1]


class FlightHunterTests(unittest.TestCase):
    def setUp(self):
        self.search = load(ROOT / 'config/searches.toml')[0]
        self.now = datetime(2026, 1, 5, 10, tzinfo=timezone.utc)
        self.offer = MockProvider().search(self.search, self.now.date())[0]

    def test_anywhere_and_normalization(self):
        offers = MockProvider().search(self.search, date(2026, 1, 5))
        self.assertEqual({o.destination for o in offers}, {'BCN', 'LIS', 'CDG'})
        raw = dict(origin=' fco ', destination='bcn', departure_date='2026-01-12',
                   price='49.123', currency='eur', carrier='mock')
        self.assertEqual(normalize(raw, 'mock').price, Decimal('49.12'))
        for price in ('NaN', 'Infinity', '-1', '0', '0.001'):
            with self.subTest(price=price), self.assertRaises(ValueError):
                normalize(dict(raw, price=price), 'mock')

    def test_history_alerts_and_idempotency(self):
        with TemporaryDirectory() as directory:
            history = History(Path(directory) / 'data' / 'prices.jsonl')
            first = run([self.search], MockProvider(), history, self.now, 'slot-1')
            self.assertEqual(first[0]['alerts'], ['below_threshold'])
            self.assertEqual(len(history.read()), 3)
            self.assertEqual(run([self.search], MockProvider(), history, self.now, 'slot-1'), [])
            self.assertEqual(len(history.read()), 3)
            old = dict(first[0], price='100.00')
            self.assertEqual(alerts(self.offer, [old], self.search),
                             ['percentage_drop', 'new_all_time_low', 'below_threshold'])
            old['comparison_key'][1] = 'JFK'
            self.assertEqual(alerts(self.offer, [old], self.search), ['below_threshold'])

    def test_drop_uses_latest_and_low_uses_all_history(self):
        base = dict(search_id=self.search.id, comparison_key=list(self.offer.key))
        previous = [dict(base, price='40'), dict(base, price='100')]
        self.assertEqual(alerts(self.offer, previous, self.search),
                         ['percentage_drop', 'below_threshold'])
        previous = [dict(base, price='49')]
        self.assertEqual(alerts(self.offer, previous, self.search), ['below_threshold'])

    def test_alert_boundaries(self):
        offer = replace(self.offer, price=Decimal('90.00'))
        search = replace(self.search, threshold=Decimal('90.00'))
        previous = [dict(search_id=search.id, comparison_key=list(offer.key), price='100.00')]
        self.assertEqual(alerts(offer, previous, search),
                         ['percentage_drop', 'new_all_time_low'])
        offer = replace(offer, price=Decimal('90.01'))
        self.assertEqual(alerts(offer, previous, search), ['new_all_time_low'])

    def test_invalid_provider_offer_is_rejected(self):
        offer = replace(self.offer, origin='JFK')

        class Invalid(MockProvider):
            def search(self, search, today):
                return [offer]

        with TemporaryDirectory() as directory:
            path = Path(directory) / 'history.jsonl'
            with self.assertRaises(ValueError):
                run([self.search], Invalid(), History(path), self.now)
            self.assertFalse(path.exists())

    def test_config_validation(self):
        original = (ROOT / 'config/searches.toml').read_text()
        for bad in (original.replace('drop_percent = 10', 'drop_percent = 0'),
                    original.replace('origin = "FCO"', 'origin = "Rome"'),
                    original.replace('departure_before_days = 30', 'departure_before_days = 2'),
                    original.replace('provider = "mock"', 'provider = "duffel"'),
                    original + original.split('provider = "mock"')[1]):
            with TemporaryDirectory() as directory:
                path = Path(directory) / 'bad.toml'
                path.write_text(bad)
                with self.assertRaises(ValueError):
                    load(path)

    def test_history_corruption_is_not_overwritten(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'history.jsonl'
            path.write_text('{broken\n')
            with self.assertRaises(ValueError):
                run([self.search], MockProvider(), History(path), self.now)
            self.assertEqual(path.read_text(), '{broken\n')

    def test_provider_failure_does_not_partially_append(self):
        class Broken(MockProvider):
            def search(self, search, today):
                raise RuntimeError('provider unavailable')
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'history.jsonl'
            with self.assertRaises(RuntimeError):
                run([self.search], Broken(), History(path), self.now)
            self.assertFalse(path.exists())

    def test_every_day_including_dst_has_three_rome_slots(self):
        # Include adjacent UTC dates so Rome's midnight can fall on the previous day.
        slots = []
        day = datetime(2025, 12, 31, tzinfo=timezone.utc)
        while day < datetime(2027, 1, 1, tzinfo=timezone.utc):
            for cron, (hour, minute) in CRONS.items():
                now = day.replace(hour=hour, minute=minute)
                slot = scheduled_slot(cron, now)
                if slot:
                    slots.append(slot)
                self.assertEqual(scheduled_slot(cron, now + timedelta(minutes=45)), slot)
            day += timedelta(days=1)
        for n in range(365):
            day_string = (date(2026, 1, 1) + timedelta(days=n)).isoformat()
            self.assertEqual(sorted(s for s in slots if s.startswith(day_string)),
                             [day_string + 'T' + t for t in ('00:10', '06:00', '11:00')])

    def test_scheduled_midnight_and_delayed_execution(self):
        self.assertEqual(scheduled_slot('10 23 * * *', datetime(2026, 1, 5, 23, 50, tzinfo=timezone.utc)),
                         '2026-01-06T00:10')
        self.assertIsNone(scheduled_slot('10 22 * * *', datetime(2026, 1, 5, 22, 10, tzinfo=timezone.utc)))
        self.assertEqual(scheduled_slot('10 22 * * *', datetime(2026, 7, 5, 23, 45, tzinfo=timezone.utc)),
                         '2026-07-06T00:10')
        with self.assertRaises(ValueError):
            scheduled_slot('0 4 * * *', datetime(2026, 1, 5, 20, tzinfo=timezone.utc))


if __name__ == '__main__':
    unittest.main()
