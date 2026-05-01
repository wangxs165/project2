from __future__ import annotations

import math
import statistics
from typing import Iterable, List, Optional, Sequence, Tuple

from .models import Bar


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def vwap(bars: Iterable[Bar]) -> Optional[float]:
    total_volume = 0.0
    total_value = 0.0
    for bar in bars:
        if bar.volume > 0:
            total_volume += bar.volume
            total_value += bar.close * bar.volume
    if total_volume <= 0:
        return None
    return total_value / total_volume


def intraday_high_low(bars: Sequence[Bar]) -> Optional[Tuple[float, float]]:
    if not bars:
        return None
    return max(bar.high for bar in bars), min(bar.low for bar in bars)


def range_percentile(price: float, bars: Sequence[Bar]) -> Optional[float]:
    high_low = intraday_high_low(bars)
    if high_low is None:
        return None
    high, low = high_low
    if math.isclose(high, low):
        return 0.5
    return clamp((price - low) / (high - low), 0.0, 1.0)


def moving_average(values: Sequence[float], window: int) -> Optional[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        return None
    recent = values[-window:]
    return sum(recent) / window


def rsi(values: Sequence[float], period: int = 14) -> Optional[float]:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) <= period:
        return None

    deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
    recent = deltas[-period:]
    gains = [delta for delta in recent if delta > 0]
    losses = [-delta for delta in recent if delta < 0]
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period

    if math.isclose(average_gain, 0.0) and math.isclose(average_loss, 0.0):
        return 50.0
    if math.isclose(average_loss, 0.0):
        return 100.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def realized_volatility(values: Sequence[float]) -> Optional[float]:
    if len(values) < 3:
        return None
    returns: List[float] = []
    for previous, current in zip(values, values[1:]):
        if previous <= 0:
            continue
        returns.append((current - previous) / previous)
    if len(returns) < 2:
        return None
    return statistics.pstdev(returns)


def support_level(values: Sequence[float], lookback: int = 20) -> Optional[float]:
    if not values:
        return None
    recent = values[-lookback:]
    return min(recent)


def median_recent_volume(bars: Sequence[Bar], lookback: int = 20) -> Optional[float]:
    volumes = [bar.volume for bar in bars[-lookback:] if bar.volume > 0]
    if not volumes:
        return None
    return statistics.median(volumes)

