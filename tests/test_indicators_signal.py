import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.trading_monitor.indicators import (
    moving_average,
    range_percentile,
    realized_volatility,
    rsi,
    support_level,
    vwap,
)
from backend.trading_monitor.models import Bar, NewsContext
from backend.trading_monitor.signal_engine import (
    SignalInput,
    calculate_suggested_buy_price,
    confidence_band,
    evaluate_buy_window,
)


PACIFIC = ZoneInfo("America/Los_Angeles")


def bar(close, volume=1000, high=None, low=None, minute=0):
    high = high if high is not None else close + 1
    low = low if low is not None else close - 1
    return Bar(
        symbol="VOO",
        timestamp=datetime(2026, 5, 1, 7, minute, tzinfo=PACIFIC),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=volume,
        source="test",
    )


class IndicatorTests(unittest.TestCase):
    def test_vwap_uses_volume_weighting(self):
        bars = [bar(100, volume=100), bar(110, volume=300)]

        self.assertEqual(vwap(bars), 107.5)

    def test_vwap_returns_none_when_volume_missing(self):
        self.assertIsNone(vwap([bar(100, volume=0), bar(101, volume=0)]))

    def test_range_percentile_handles_normal_and_flat_ranges(self):
        bars = [bar(100, high=110, low=90)]
        flat = [bar(100, high=100, low=100)]

        self.assertAlmostEqual(range_percentile(95, bars), 0.25)
        self.assertEqual(range_percentile(100, flat), 0.5)

    def test_rsi_handles_insufficient_flat_and_rising_data(self):
        self.assertIsNone(rsi([1, 2, 3], period=14))
        self.assertEqual(rsi([100] * 20), 50.0)
        self.assertEqual(rsi(list(range(1, 30))), 100.0)

    def test_moving_average_support_and_volatility(self):
        values = [100, 101, 99, 102, 98, 103]

        self.assertEqual(moving_average(values, 3), (102 + 98 + 103) / 3)
        self.assertEqual(support_level(values, 4), 98)
        self.assertIsNotNone(realized_volatility(values))


class SignalEngineTests(unittest.TestCase):
    def test_confidence_bands(self):
        self.assertEqual(confidence_band(49), "No action suggested")
        self.assertEqual(confidence_band(50), "Weak opportunity, monitor only")
        self.assertEqual(confidence_band(65), "Moderate opportunity")
        self.assertEqual(confidence_band(75), "Strong opportunity")
        self.assertEqual(confidence_band(85), "Very strong opportunity, still manual review required")

    def test_high_price_above_vwap_does_not_alert(self):
        bars = [bar(100), bar(101), bar(102), bar(103), bar(104)]
        signal = evaluate_buy_window(
            SignalInput(
                symbol="VOO",
                current_price=105,
                intraday_bars=bars,
                daily_closes=[100 + index * 0.1 for index in range(30)],
                news_context=NewsContext(summary="News context is neutral."),
                created_at=datetime(2026, 5, 1, 9, 0, tzinfo=PACIFIC),
            )
        )

        self.assertFalse(signal.should_alert)
        self.assertLess(signal.confidence, 50)

    def test_strong_setup_alerts_with_explanation(self):
        bars = [
            bar(103, volume=900, high=104, low=99, minute=0),
            bar(102, volume=950, high=104, low=99, minute=1),
            bar(101, volume=1000, high=104, low=99, minute=2),
            bar(100, volume=1100, high=104, low=99, minute=3),
            bar(99.5, volume=1500, high=104, low=99, minute=4),
        ]
        daily = [103, 102, 101, 100.8, 100.5, 100.4, 100.3, 100.2, 100.1, 100] * 3

        signal = evaluate_buy_window(
            SignalInput(
                symbol="voo",
                current_price=99.5,
                intraday_bars=bars,
                daily_closes=daily,
                news_context=NewsContext(summary="News context is neutral."),
                created_at=datetime(2026, 5, 1, 9, 0, tzinfo=PACIFIC),
            )
        )

        self.assertEqual(signal.symbol, "VOO")
        self.assertTrue(signal.should_alert)
        self.assertGreaterEqual(signal.confidence, 75)
        self.assertLessEqual(signal.suggested_buy_price, signal.current_price)
        self.assertTrue(any("VWAP" in reason for reason in signal.reasons))

    def test_stale_closed_open_delay_and_risk_override_block_alerts(self):
        bars = [bar(103), bar(102), bar(101), bar(100), bar(99.5)]
        daily = [101] * 30

        for overrides in (
            {"data_is_stale": True},
            {"market_is_open": False},
            {"in_open_avoidance_window": True},
        ):
            signal = evaluate_buy_window(
                SignalInput(
                    symbol="VOO",
                    current_price=99.5,
                    intraday_bars=bars,
                    daily_closes=daily,
                    news_context=NewsContext(summary="News context is neutral."),
                    created_at=datetime(2026, 5, 1, 9, 0, tzinfo=PACIFIC),
                    **overrides,
                )
            )
            self.assertFalse(signal.should_alert)

        risk_signal = evaluate_buy_window(
            SignalInput(
                symbol="VOO",
                current_price=99.5,
                intraday_bars=bars,
                daily_closes=daily,
                news_context=NewsContext(
                    summary="Major risk headline detected.",
                    score_modifier=-15,
                    risk_override=True,
                ),
                created_at=datetime(2026, 5, 1, 9, 0, tzinfo=PACIFIC),
            )
        )
        self.assertFalse(risk_signal.should_alert)

    def test_suggested_buy_price_never_exceeds_current_price(self):
        price = calculate_suggested_buy_price(current_price=100, vwap_value=105, support_price=102)

        self.assertEqual(price, 100)

    def test_suggested_buy_price_uses_vwap_or_support_when_lower(self):
        price = calculate_suggested_buy_price(current_price=100, vwap_value=99, support_price=101)

        self.assertEqual(price, round(99 * 0.997, 2))


if __name__ == "__main__":
    unittest.main()

