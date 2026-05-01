import unittest
from datetime import datetime, timezone

from backend.trading_monitor.ibkr import IbkrMarketDataClient
from backend.trading_monitor.models import Bar, NewsContext, PriceUpdate, ValidationError, normalize_symbol
from backend.trading_monitor.news import Headline, analyze_headlines


class ModelValidationTests(unittest.TestCase):
    def test_symbol_normalization_and_validation(self):
        self.assertEqual(normalize_symbol(" voo "), "VOO")
        with self.assertRaises(ValidationError):
            normalize_symbol("")
        with self.assertRaises(ValidationError):
            normalize_symbol("bad symbol")

    def test_price_update_rejects_invalid_market_data(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValidationError):
            PriceUpdate("VOO", price=0, source_ts=now, received_ts=now)
        with self.assertRaises(ValidationError):
            PriceUpdate("VOO", price=100, bid=101, ask=100, source_ts=now, received_ts=now)

    def test_bar_rejects_impossible_ohlc(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValidationError):
            Bar("VOO", now, open=100, high=99, low=101, close=100, volume=1000)
        with self.assertRaises(ValidationError):
            Bar("VOO", now, open=105, high=101, low=99, close=100, volume=1000)

    def test_news_context_modifier_bounds(self):
        with self.assertRaises(ValidationError):
            NewsContext(score_modifier=16)


class NewsAnalyzerTests(unittest.TestCase):
    def test_neutral_when_no_headlines(self):
        context = analyze_headlines([])

        self.assertEqual(context.score_modifier, 0)
        self.assertFalse(context.risk_override)

    def test_negative_macro_reduces_confidence(self):
        context = analyze_headlines([Headline("Fed signals hawkish rate hike path")])

        self.assertLess(context.score_modifier, 0)
        self.assertIn("fed_rates", context.categories)

    def test_positive_macro_increases_confidence(self):
        context = analyze_headlines([Headline("Cooling inflation supports soft landing")])

        self.assertGreater(context.score_modifier, 0)

    def test_high_risk_headline_sets_override(self):
        context = analyze_headlines([Headline("Market halt follows flash crash")])

        self.assertTrue(context.risk_override)
        self.assertEqual(context.score_modifier, -15)

    def test_gold_headline_categories_for_iau(self):
        context = analyze_headlines([Headline("Gold rises as treasury yield falls")], symbol="IAU")

        self.assertIn("gold_macro", context.categories)


class IbkrAdapterTests(unittest.TestCase):
    def test_normalize_tick_creates_price_update(self):
        now = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
        update = IbkrMarketDataClient.normalize_tick(
            "voo",
            100,
            source_ts=now,
            bid=99.9,
            ask=100.1,
            delayed=True,
        )

        self.assertEqual(update.symbol, "VOO")
        self.assertEqual(update.price, 100)
        self.assertTrue(update.delayed)
        self.assertEqual(update.source, "ibkr")

    def test_ibkr_adapter_does_not_expose_order_methods(self):
        client = IbkrMarketDataClient.__new__(IbkrMarketDataClient)

        forbidden = [name for name in dir(client) if "order" in name.lower() or "trade" in name.lower()]
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()

