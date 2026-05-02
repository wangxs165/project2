from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence
from zoneinfo import ZoneInfo

from .models import Bar, PriceUpdate


class DemoMarketDataProvider:
    """Deterministic provider for exercising signal UI outside market hours."""

    def latest_price(self, symbol: str, now: datetime) -> PriceUpdate:
        bars = self.intraday_bars(symbol, now)
        latest = bars[-1]
        return PriceUpdate(
            symbol=symbol,
            price=latest.close,
            source_ts=latest.timestamp,
            received_ts=now,
            volume=latest.volume,
            delayed=True,
            source="demo",
        )

    def intraday_bars(self, symbol: str, now: datetime) -> Sequence[Bar]:
        baseline = _baseline_price(symbol)
        start = now.replace(hour=6, minute=30, second=0, microsecond=0)
        closes = [
            baseline * 1.015,
            baseline * 1.006,
            baseline * 0.996,
            baseline * 0.988,
            baseline * 0.981,
            baseline * 0.975,
            baseline * 0.973,
            baseline * 0.972,
        ]
        bars = []
        for index, close in enumerate(closes):
            high = max(close * 1.004, baseline * 1.017)
            low = min(close * 0.997, baseline * 0.972)
            bars.append(
                Bar(
                    symbol=symbol,
                    timestamp=start + timedelta(minutes=index * 5),
                    open=close * 1.002,
                    high=high,
                    low=low,
                    close=close,
                    volume=1000 + (index * 220),
                    kind="intraday",
                    source="demo",
                )
            )
        return bars

    def daily_closes(self, symbol: str, lookback_days: int) -> Sequence[float]:
        baseline = _baseline_price(symbol)
        values = [baseline * (0.99 + (index % 10) * 0.001) for index in range(max(lookback_days, 30))]
        return values[-lookback_days:]


def demo_market_time(now: datetime) -> datetime:
    pacific = ZoneInfo("America/Los_Angeles")
    market_day = now.astimezone(pacific)
    return market_day.replace(hour=9, minute=0, second=0, microsecond=0)


def _baseline_price(symbol: str) -> float:
    return {
        "IAU": 86.0,
        "VOO": 660.0,
        "MO": 58.0,
        "BTC": 34.0,
    }.get(symbol, 100.0)
