import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.trading_monitor.backtest import (
    run_daily_ohlc_backtest,
    run_intraday_backtest,
    synthesize_intraday_sessions_from_daily_bars,
)
from backend.trading_monitor.config import AppConfig
from backend.trading_monitor.demo import DemoMarketDataProvider
from backend.trading_monitor.models import Bar, NewsContext, NotificationRecord, PriceUpdate
from backend.trading_monitor.monitoring import MonitoringService
from backend.trading_monitor.storage import Storage


PACIFIC = ZoneInfo("America/Los_Angeles")


def make_bar(close, minute, symbol="VOO", day=1, volume=1000):
    return Bar(
        symbol=symbol,
        timestamp=datetime(2026, 5, day, 9, minute, tzinfo=PACIFIC),
        open=close,
        high=104,
        low=99,
        close=close,
        volume=volume,
        source="test",
    )


class FakeProvider:
    def __init__(self, bars, daily_closes, stale=False):
        self.bars = bars
        self.daily = daily_closes
        self.stale = stale

    def latest_price(self, symbol, now):
        received = now - timedelta(minutes=5) if self.stale else now
        return PriceUpdate(
            symbol=symbol,
            price=self.bars[-1].close,
            source_ts=received,
            received_ts=received,
            source="fake",
        )

    def intraday_bars(self, symbol, now):
        return self.bars

    def daily_closes(self, symbol, lookback_days):
        return self.daily[-lookback_days:]


class FakeNotifier:
    def __init__(self):
        self.records = []

    def send_signal(self, signal, now):
        record = NotificationRecord(
            symbol=signal.symbol,
            status="sent",
            confidence=signal.confidence,
            message="sent",
            created_at=now,
        )
        self.records.append(record)
        return record


class MonitoringServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.tempdir.name) / "monitor.sqlite")
        self.storage.initialize(("VOO",))
        self.config = AppConfig(symbols=("VOO",), db_path=Path(self.tempdir.name) / "monitor.sqlite")
        self.bars = [
            make_bar(103, 0, volume=900),
            make_bar(101, 1, volume=1000),
            make_bar(99.2, 2, volume=1300),
            make_bar(99.6, 3, volume=1500),
            make_bar(100.0, 4, volume=1800),
        ]
        self.daily = [103, 102, 101, 100.8, 100.5, 100.4, 100.3, 100.2, 100.1, 100] * 3

    def tearDown(self):
        self.storage.close()
        self.tempdir.cleanup()

    def test_market_closed_cycle_does_not_evaluate_symbols(self):
        service = MonitoringService(
            self.storage,
            self.config,
            FakeProvider(self.bars, self.daily),
            FakeNotifier(),
        )
        result = service.run_once(datetime(2026, 5, 2, 9, 0, tzinfo=PACIFIC))

        self.assertFalse(result.market_open)
        self.assertEqual(result.evaluated_symbols, 0)
        self.assertEqual(result.generated_signals, 0)

    def test_strong_cycle_sends_and_logs_notification(self):
        notifier = FakeNotifier()
        service = MonitoringService(
            self.storage,
            self.config,
            FakeProvider(self.bars, self.daily),
            notifier,
        )
        result = service.run_once(datetime(2026, 5, 1, 9, 0, tzinfo=PACIFIC))

        self.assertTrue(result.market_open)
        self.assertEqual(result.evaluated_symbols, 1)
        self.assertEqual(result.generated_signals, 1)
        self.assertEqual(result.sent_notifications, 1)
        self.assertEqual(len(notifier.records), 1)
        self.assertEqual(self.storage.list_notifications()[0]["status"], "sent")

    def test_stale_data_blocks_notification_and_logs_block(self):
        service = MonitoringService(
            self.storage,
            self.config,
            FakeProvider(self.bars, self.daily, stale=True),
            FakeNotifier(),
            stale_after_seconds=120,
        )
        result = service.run_once(datetime(2026, 5, 1, 9, 0, tzinfo=PACIFIC))

        self.assertEqual(result.sent_notifications, 0)
        self.assertEqual(result.blocked_notifications, 1)
        self.assertEqual(self.storage.list_notifications()[0]["status"], "blocked")

    def test_cooldown_blocks_second_alert(self):
        notifier = FakeNotifier()
        service = MonitoringService(
            self.storage,
            self.config,
            FakeProvider(self.bars, self.daily),
            notifier,
        )
        first = service.run_once(datetime(2026, 5, 1, 9, 0, tzinfo=PACIFIC))
        second = service.run_once(datetime(2026, 5, 1, 9, 10, tzinfo=PACIFIC))

        self.assertEqual(first.sent_notifications, 1)
        self.assertEqual(second.sent_notifications, 0)
        self.assertEqual(second.blocked_notifications, 1)

    def test_demo_provider_generates_usable_market_data(self):
        provider = DemoMarketDataProvider()
        now = datetime(2026, 5, 1, 9, 0, tzinfo=PACIFIC)

        price = provider.latest_price("VOO", now)
        bars = provider.intraday_bars("VOO", now)
        daily = provider.daily_closes("VOO", 20)

        self.assertEqual(price.source, "demo")
        self.assertGreater(len(bars), 3)
        self.assertEqual(len(daily), 20)


class BacktestTests(unittest.TestCase):
    def test_backtest_generates_signal_and_baseline_deltas(self):
        sessions = {
            date(2026, 5, 1): [
                make_bar(103, 0),
                make_bar(102, 1),
                make_bar(101, 2),
                make_bar(100, 3),
                make_bar(99.5, 4),
            ]
        }
        result = run_intraday_backtest(
            "VOO",
            sessions,
            historical_daily_closes=[101] * 30,
            threshold=75,
            news_context=NewsContext(summary="News context is neutral."),
            random_seed=1,
        )

        self.assertEqual(result.days_tested, 1)
        self.assertEqual(result.signal_days, 1)
        self.assertIsNotNone(result.average_signal_price)
        self.assertIn("open", result.baseline_deltas())

    def test_backtest_is_reproducible_with_same_random_seed(self):
        sessions = {
            date(2026, 5, 1): [make_bar(103, 0), make_bar(102, 1), make_bar(101, 2)],
            date(2026, 5, 4): [make_bar(104, 0, day=4), make_bar(103, 1, day=4), make_bar(102, 2, day=4)],
        }

        first = run_intraday_backtest("VOO", sessions, [101] * 30, random_seed=11)
        second = run_intraday_backtest("VOO", sessions, [101] * 30, random_seed=11)

        self.assertEqual(
            [day.random_price for day in first.day_results],
            [day.random_price for day in second.day_results],
        )

    def test_backtest_handles_no_signal_days(self):
        sessions = {
            date(2026, 5, 1): [
                make_bar(100, 0),
                make_bar(101, 1),
                make_bar(102, 2),
                make_bar(103, 3),
            ]
        }
        result = run_intraday_backtest("VOO", sessions, [100] * 30, threshold=90)

        self.assertEqual(result.signal_days, 0)
        self.assertIsNone(result.average_signal_price)
        self.assertEqual(result.baseline_deltas()["open"], None)

    def test_synthesizes_intraday_sessions_from_daily_bars(self):
        daily_bar = Bar(
            symbol="VOO",
            timestamp=datetime(2026, 5, 1, 6, 30, tzinfo=PACIFIC),
            open=100,
            high=104,
            low=98,
            close=101,
            volume=8000,
            kind="daily",
            source="test",
        )

        sessions = synthesize_intraday_sessions_from_daily_bars([daily_bar])

        self.assertEqual(len(sessions[daily_bar.timestamp.date()]), 8)
        self.assertEqual(sessions[daily_bar.timestamp.date()][0].symbol, "VOO")

    def test_daily_ohlc_backtest_returns_baselines(self):
        bars = []
        for index in range(35):
            close = 100 + (index % 5)
            bars.append(
                Bar(
                    symbol="VOO",
                    timestamp=datetime(2026, 4, 1, 6, 30, tzinfo=PACIFIC) + timedelta(days=index),
                    open=close + 1,
                    high=close + 2,
                    low=close - 2,
                    close=close,
                    volume=1000,
                    kind="daily",
                    source="test",
                )
            )

        result = run_daily_ohlc_backtest("VOO", bars, threshold=75)

        self.assertEqual(result.days_tested, 15)
        self.assertIn("open", result.baseline_deltas())


if __name__ == "__main__":
    unittest.main()
