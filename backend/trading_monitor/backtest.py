from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Mapping, Optional, Sequence

from .models import Bar, NewsContext
from .signal_engine import SignalInput, evaluate_buy_window


@dataclass(frozen=True)
class BacktestDayResult:
    day: date
    signal_price: Optional[float]
    signal_confidence: Optional[int]
    open_price: float
    noon_price: float
    close_price: float
    random_price: float


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    days_tested: int
    signal_days: int
    threshold: int
    average_signal_price: Optional[float]
    average_open_price: float
    average_noon_price: float
    average_close_price: float
    average_random_price: float
    day_results: Sequence[BacktestDayResult] = field(default_factory=list)

    def baseline_deltas(self) -> Dict[str, Optional[float]]:
        if self.average_signal_price is None:
            return {"open": None, "noon": None, "close": None, "random": None}
        return {
            "open": self.average_open_price - self.average_signal_price,
            "noon": self.average_noon_price - self.average_signal_price,
            "close": self.average_close_price - self.average_signal_price,
            "random": self.average_random_price - self.average_signal_price,
        }


def _average(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _nearest_noon_bar(bars: Sequence[Bar]) -> Bar:
    return min(bars, key=lambda bar: abs((bar.timestamp.hour * 60 + bar.timestamp.minute) - (12 * 60)))


def run_intraday_backtest(
    symbol: str,
    sessions: Mapping[date, Sequence[Bar]],
    historical_daily_closes: Sequence[float],
    threshold: int = 75,
    news_context: NewsContext = NewsContext(summary="News context unavailable or neutral."),
    random_seed: int = 7,
) -> BacktestResult:
    rng = random.Random(random_seed)
    day_results = []
    signal_prices = []
    open_prices = []
    noon_prices = []
    close_prices = []
    random_prices = []
    rolling_daily_closes = list(historical_daily_closes)

    for session_day in sorted(sessions):
        bars = list(sessions[session_day])
        if not bars:
            continue

        first_bar = bars[0]
        noon_bar = _nearest_noon_bar(bars)
        last_bar = bars[-1]
        random_bar = rng.choice(bars)
        signal_price = None
        signal_confidence = None

        for index in range(len(bars)):
            visible_bars = bars[: index + 1]
            current_bar = visible_bars[-1]
            signal = evaluate_buy_window(
                SignalInput(
                    symbol=symbol,
                    current_price=current_bar.close,
                    intraday_bars=visible_bars,
                    daily_closes=rolling_daily_closes,
                    news_context=news_context,
                    created_at=current_bar.timestamp,
                    min_confidence=threshold,
                    market_is_open=True,
                    data_is_stale=False,
                    in_open_avoidance_window=False,
                )
            )
            if signal.should_alert:
                signal_price = signal.current_price
                signal_confidence = signal.confidence
                signal_prices.append(signal.current_price)
                break

        open_prices.append(first_bar.open)
        noon_prices.append(noon_bar.close)
        close_prices.append(last_bar.close)
        random_prices.append(random_bar.close)
        day_results.append(
            BacktestDayResult(
                day=session_day,
                signal_price=signal_price,
                signal_confidence=signal_confidence,
                open_price=first_bar.open,
                noon_price=noon_bar.close,
                close_price=last_bar.close,
                random_price=random_bar.close,
            )
        )
        rolling_daily_closes.append(last_bar.close)

    return BacktestResult(
        symbol=symbol,
        days_tested=len(day_results),
        signal_days=len(signal_prices),
        threshold=threshold,
        average_signal_price=_average(signal_prices),
        average_open_price=_average(open_prices) or 0.0,
        average_noon_price=_average(noon_prices) or 0.0,
        average_close_price=_average(close_prices) or 0.0,
        average_random_price=_average(random_prices) or 0.0,
        day_results=day_results,
    )

