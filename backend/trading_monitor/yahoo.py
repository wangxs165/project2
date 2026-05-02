from __future__ import annotations

from datetime import datetime
from typing import Sequence

from .models import Bar, PriceUpdate, normalize_symbol


class YFinanceUnavailable(RuntimeError):
    """Raised when yfinance is unavailable or Yahoo data cannot be loaded."""


class YFinanceMarketDataClient:
    """Market-data provider backed by yfinance/Yahoo Finance.

    This provider is intended for low-cost monitoring. Yahoo data is
    informational, may be delayed or cached, and has no formal latency SLA.
    """

    def __init__(self, interval: str = "1m", daily_lookback_period: str = "1y") -> None:
        self.interval = interval
        self.daily_lookback_period = daily_lookback_period

    def latest_price(self, symbol: str, now: datetime) -> PriceUpdate:
        bars = list(self.intraday_bars(symbol, now))
        if not bars:
            raise YFinanceUnavailable(f"No intraday bars returned for {symbol}")
        latest = bars[-1]
        return PriceUpdate(
            symbol=symbol,
            price=latest.close,
            source_ts=latest.timestamp,
            received_ts=now,
            volume=latest.volume,
            delayed=True,
            source="yfinance",
        )

    def intraday_bars(self, symbol: str, now: datetime) -> Sequence[Bar]:
        ticker = self._ticker(symbol)
        frame = ticker.history(
            period="1d",
            interval=self.interval,
            prepost=False,
            auto_adjust=False,
            actions=False,
            timeout=10,
        )
        return self._bars_from_frame(symbol, frame, kind="intraday")

    def daily_closes(self, symbol: str, lookback_days: int) -> Sequence[float]:
        return [bar.close for bar in self.daily_bars(symbol, lookback_days)]

    def daily_bars(self, symbol: str, lookback_days: int) -> Sequence[Bar]:
        ticker = self._ticker(symbol)
        frame = ticker.history(
            period=self.daily_lookback_period or "1mo",
            interval="1d",
            prepost=False,
            auto_adjust=False,
            actions=False,
            timeout=10,
        )
        return self._bars_from_frame(symbol, frame, kind="daily")[-lookback_days:]

    def _ticker(self, symbol: str):
        try:
            import yfinance as yf  # type: ignore
        except ImportError as exc:
            raise YFinanceUnavailable(
                'yfinance is not installed. Install with: python3 -m pip install -e ".[yfinance]"'
            ) from exc
        return yf.Ticker(normalize_symbol(symbol))

    @staticmethod
    def _bars_from_frame(symbol: str, frame, kind: str) -> Sequence[Bar]:
        if frame is None or frame.empty:
            return []
        bars = []
        for timestamp, row in frame.dropna(subset=["Open", "High", "Low", "Close"]).iterrows():
            volume = row.get("Volume", 0)
            if volume != volume:
                volume = 0
            bars.append(
                Bar(
                    symbol=symbol,
                    timestamp=timestamp.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(volume or 0),
                    kind=kind,
                    source="yfinance",
                )
            )
        return bars
