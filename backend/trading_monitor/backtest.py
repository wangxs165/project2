from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
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


def synthesize_intraday_sessions_from_daily_bars(
    daily_bars: Sequence[Bar],
    bars_per_day: int = 8,
) -> Dict[date, Sequence[Bar]]:
    sessions: Dict[date, Sequence[Bar]] = {}
    if bars_per_day < 4:
        raise ValueError("bars_per_day must be at least 4")

    for daily_bar in daily_bars:
        day = daily_bar.timestamp.date()
        template = [
            daily_bar.open,
            daily_bar.high,
            (daily_bar.open + daily_bar.high + daily_bar.low) / 3,
            daily_bar.low,
            (daily_bar.low + daily_bar.close) / 2,
            daily_bar.close,
        ]
        values = _resample_path(template, bars_per_day)
        session = []
        for index, close in enumerate(values):
            previous = values[index - 1] if index > 0 else daily_bar.open
            local_high = max(close, previous)
            local_low = min(close, previous)
            session.append(
                Bar(
                    symbol=daily_bar.symbol,
                    timestamp=daily_bar.timestamp + timedelta(minutes=index * 45),
                    open=previous,
                    high=max(local_high, daily_bar.low),
                    low=min(local_low, daily_bar.high),
                    close=close,
                    volume=max(daily_bar.volume / bars_per_day, 0),
                    kind="intraday",
                    source=f"{daily_bar.source}-synthetic",
                )
            )
        sessions[day] = session
    return sessions


def run_daily_ohlc_backtest(
    symbol: str,
    daily_bars: Sequence[Bar],
    threshold: int = 75,
    random_seed: int = 7,
) -> BacktestResult:
    ordered = sorted(daily_bars, key=lambda bar: bar.timestamp)
    if len(ordered) < 25:
        return BacktestResult(
            symbol=symbol,
            days_tested=0,
            signal_days=0,
            threshold=threshold,
            average_signal_price=None,
            average_open_price=0.0,
            average_noon_price=0.0,
            average_close_price=0.0,
            average_random_price=0.0,
            day_results=[],
        )

    historical = [bar.close for bar in ordered[:20]]
    test_bars = ordered[20:]
    sessions = synthesize_intraday_sessions_from_daily_bars(test_bars)
    return run_intraday_backtest(
        symbol=symbol,
        sessions=sessions,
        historical_daily_closes=historical,
        threshold=threshold,
        random_seed=random_seed,
    )


def _resample_path(values: Sequence[float], output_count: int) -> Sequence[float]:
    if output_count == len(values):
        return list(values)
    result = []
    max_source_index = len(values) - 1
    for index in range(output_count):
        position = index * max_source_index / (output_count - 1)
        lower = int(position)
        upper = min(lower + 1, max_source_index)
        weight = position - lower
        result.append((values[lower] * (1 - weight)) + (values[upper] * weight))
    return result
