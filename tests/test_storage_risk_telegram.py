import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.trading_monitor.config import AlertConfig
from backend.trading_monitor.models import (
    DISCLAIMER,
    Bar,
    NewsContext,
    NotificationRecord,
    PriceUpdate,
    ScoreBreakdown,
    SignalDecision,
)
from backend.trading_monitor.risk import AlertGate
from backend.trading_monitor.signal_engine import SignalInput, evaluate_buy_window
from backend.trading_monitor.storage import Storage
from backend.trading_monitor.telegram import TelegramClient, format_signal_message, redact_secret


def make_signal(now, should_alert=True, confidence=80):
    return SignalDecision(
        symbol="VOO",
        current_price=100,
        suggested_buy_price=99,
        confidence=confidence,
        band="Strong opportunity",
        should_alert=should_alert,
        reasons=["Price is below VWAP.", "News context is neutral."],
        market_context_summary="News context is neutral.",
        score_breakdown=ScoreBreakdown(20, 15, 15, 10, 10, 10),
        created_at=now,
    )


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.tempdir.name) / "test.sqlite")
        self.storage.initialize()

    def tearDown(self):
        self.storage.close()
        self.tempdir.cleanup()

    def test_watchlist_defaults_add_remove_and_normalize(self):
        self.assertEqual(self.storage.get_watchlist(), ["IAU", "VOO"])

        self.storage.add_symbol("spy")
        self.assertEqual(self.storage.get_watchlist(), ["IAU", "SPY", "VOO"])
        self.assertTrue(self.storage.remove_symbol("SPY"))
        self.assertFalse(self.storage.remove_symbol("SPY"))

    def test_persists_latest_price_signal_and_notification(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        self.storage.save_price(
            PriceUpdate(symbol="VOO", price=100, source_ts=now, received_ts=now, source="test")
        )
        self.assertEqual(self.storage.latest_prices()["VOO"]["price"], 100)

        signal = make_signal(now)
        self.storage.save_signal(signal)
        signals = self.storage.list_signals()
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["symbol"], "VOO")
        self.assertEqual(signals[0]["reasons"], signal.reasons)

        self.storage.save_notification(
            NotificationRecord(
                symbol="VOO",
                status="sent",
                confidence=80,
                message="message",
                created_at=now,
            )
        )
        notifications = self.storage.list_notifications()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(self.storage.count_notifications_for_day("VOO", "2026-05-01"), 1)

    def test_bar_upsert_is_idempotent(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        bar = Bar("VOO", now, open=100, high=101, low=99, close=100.5, volume=1000)

        self.storage.save_bar(bar)
        self.storage.save_bar(bar)

        row = self.storage._conn.execute("SELECT COUNT(*) AS count FROM bars").fetchone()
        self.assertEqual(row["count"], 1)

    def test_lists_saved_bars_by_symbol_kind_and_limit(self):
        first = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        second = first + timedelta(minutes=1)

        saved = self.storage.save_bars(
            [
                Bar("VOO", first, open=100, high=101, low=99, close=100.5, volume=1000),
                Bar("VOO", second, open=101, high=102, low=100, close=101.5, volume=1100),
                Bar("IAU", first, open=50, high=51, low=49, close=50.5, volume=900),
            ]
        )

        self.assertEqual(saved, 3)
        bars = self.storage.list_bars("voo", limit=1)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["symbol"], "VOO")
        self.assertEqual(bars[0]["timestamp"], second.isoformat())


class RiskGateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.tempdir.name) / "risk.sqlite")
        self.storage.initialize()
        self.gate = AlertGate(
            self.storage,
            AlertConfig(min_confidence=75, cooldown_minutes=30, max_alerts_per_symbol_per_day=3),
        )

    def tearDown(self):
        self.storage.close()
        self.tempdir.cleanup()

    def test_blocks_signal_below_threshold(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        result = self.gate.evaluate(make_signal(now, should_alert=False, confidence=40), now)

        self.assertFalse(result.allowed)

    def test_allows_first_valid_alert(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        result = self.gate.evaluate(make_signal(now), now)

        self.assertTrue(result.allowed)

    def test_blocks_inside_cooldown(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        self.storage.save_notification(
            NotificationRecord("VOO", "sent", "message", now, confidence=80)
        )

        result = self.gate.evaluate(make_signal(now + timedelta(minutes=10)), now + timedelta(minutes=10))

        self.assertFalse(result.allowed)
        self.assertIn("cooldown", result.reason.lower())

    def test_allows_after_cooldown(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        self.storage.save_notification(
            NotificationRecord("VOO", "sent", "message", now, confidence=80)
        )

        result = self.gate.evaluate(make_signal(now + timedelta(minutes=31)), now + timedelta(minutes=31))

        self.assertTrue(result.allowed)

    def test_blocks_daily_cap_per_symbol(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        for index in range(3):
            self.storage.save_notification(
                NotificationRecord(
                    "VOO",
                    "sent",
                    f"message {index}",
                    now + timedelta(hours=index),
                    confidence=80,
                )
            )

        result = self.gate.evaluate(make_signal(now + timedelta(hours=4)), now + timedelta(hours=4))

        self.assertFalse(result.allowed)
        self.assertIn("cap", result.reason.lower())


class TelegramTests(unittest.TestCase):
    def test_message_contains_required_fields_and_disclaimer(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        message = format_signal_message(make_signal(now))

        self.assertIn("BUY WINDOW SUGGESTION", message)
        self.assertIn("Ticker: VOO", message)
        self.assertIn("Confidence: 80 / 100", message)
        self.assertIn(DISCLAIMER, message)
        self.assertNotIn("tranche", message.lower())

    def test_send_signal_success_with_fake_opener(self):
        calls = []

        class Response:
            status = 200

        def opener(request, *, timeout):
            calls.append((request, timeout))
            return Response()

        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        client = TelegramClient("token1234", "chat", opener=opener)
        record = client.send_signal(make_signal(now), now)

        self.assertEqual(record.status, "sent")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], 10)
        self.assertIn(b"BUY WINDOW SUGGESTION", calls[0][0].data)

    def test_send_signal_failure_does_not_leak_token(self):
        token = "1234567890:secret-token"

        def opener(request, timeout):
            raise urllib.error.URLError(f"bad token {token}")

        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        client = TelegramClient(token, "chat", opener=opener)
        record = client.send_signal(make_signal(now), now)

        self.assertEqual(record.status, "failed")
        self.assertNotIn(token, record.error)
        self.assertIn(redact_secret(token), record.error)

    def test_missing_credentials_return_failed_record(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        client = TelegramClient("", "")
        record = client.send_signal(make_signal(now), now)

        self.assertEqual(record.status, "failed")
        self.assertIn("token", record.error.lower())


class EndToEndCoreFlowTests(unittest.TestCase):
    def test_signal_can_be_generated_gated_sent_and_logged_without_live_services(self):
        with tempfile.TemporaryDirectory() as tempdir:
            storage = Storage(Path(tempdir) / "flow.sqlite")
            storage.initialize()
            try:
                bars = [
                    Bar("VOO", datetime(2026, 5, 1, 16, i, tzinfo=timezone.utc), 103, 104, 99, close, 1000 + i)
                    for i, close in enumerate([103, 102, 101, 100, 99.5])
                ]
                signal = evaluate_buy_window(
                    SignalInput(
                        symbol="VOO",
                        current_price=99.5,
                        intraday_bars=bars,
                        daily_closes=[101] * 30,
                        news_context=NewsContext(summary="News context is neutral."),
                        created_at=datetime(2026, 5, 1, 16, 10, tzinfo=timezone.utc),
                    )
                )
                storage.save_signal(signal)
                gate = AlertGate(storage, AlertConfig())
                self.assertTrue(gate.evaluate(signal).allowed)

                client = TelegramClient(
                    "token1234",
                    "chat",
                    opener=lambda request, timeout: type("Response", (), {"status": 200})(),
                )
                record = client.send_signal(signal, signal.created_at)
                storage.save_notification(record)

                self.assertEqual(storage.list_notifications()[0]["status"], "sent")
                self.assertEqual(storage.list_signals()[0]["symbol"], "VOO")
            finally:
                storage.close()


if __name__ == "__main__":
    unittest.main()
