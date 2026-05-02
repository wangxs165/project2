from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import floor
from typing import List, Optional, Sequence

from .indicators import (
    clamp,
    median_recent_volume,
    moving_average,
    range_percentile,
    realized_volatility,
    rsi,
    support_level,
    vwap,
)
from .models import Bar, NewsContext, ScoreBreakdown, SignalDecision, normalize_symbol


@dataclass(frozen=True)
class SignalInput:
    symbol: str
    current_price: float
    intraday_bars: Sequence[Bar]
    daily_closes: Sequence[float]
    news_context: NewsContext
    created_at: datetime
    min_confidence: int = 75
    market_is_open: bool = True
    data_is_stale: bool = False
    in_open_avoidance_window: bool = False


def confidence_band(score: int) -> str:
    if score < 50:
        return "No action suggested"
    if score < 65:
        return "Weak opportunity, monitor only"
    if score < 75:
        return "Moderate opportunity"
    if score < 85:
        return "Strong opportunity"
    return "Very strong opportunity, still manual review required"


def calculate_suggested_buy_price(
    current_price: float,
    vwap_value: Optional[float],
    support_price: Optional[float],
    precision: int = 2,
) -> float:
    candidates = [current_price]
    if vwap_value and vwap_value > 0:
        candidates.append(vwap_value * 0.997)
    if support_price and support_price > 0:
        candidates.append(support_price * 1.002)
    scale = 10**precision
    return floor(min(candidates) * scale) / scale


def _intraday_component(current_price: float, bars: Sequence[Bar]) -> float:
    percentile = range_percentile(current_price, bars)
    vwap_value = vwap(bars)
    if percentile is None and vwap_value is None:
        return 0.0

    range_quality = 0.0
    if percentile is not None:
        range_quality = clamp((0.5 - percentile) / 0.5, 0.0, 1.0)

    vwap_quality = 0.0
    if vwap_value is not None:
        vwap_quality = clamp((vwap_value - current_price) / (vwap_value * 0.01), 0.0, 1.0)

    return 30.0 * ((0.6 * range_quality) + (0.4 * vwap_quality))


def _historical_component(current_price: float, daily_closes: Sequence[float]) -> float:
    if not daily_closes:
        return 0.0
    ma5 = moving_average(daily_closes, 5)
    ma20 = moving_average(daily_closes, 20)
    support = support_level(daily_closes, 20)

    setup = 0.0
    if ma5 and current_price <= ma5:
        setup += 0.30
    if ma20 and current_price <= ma20:
        setup += 0.30
    if support:
        support_quality = clamp((support * 1.015 - current_price) / (support * 0.02), 0.0, 1.0)
        setup += 0.40 * support_quality
    return 25.0 * clamp(setup, 0.0, 1.0)


def _volatility_component(current_price: float, bars: Sequence[Bar], daily_closes: Sequence[float]) -> float:
    percentile = range_percentile(current_price, bars)
    if percentile is None:
        return 0.0
    vol = realized_volatility(daily_closes)
    if vol is None:
        vol_quality = 0.5
    else:
        vol_quality = clamp(vol / 0.02, 0.0, 1.0)
    dip_quality = clamp((0.45 - percentile) / 0.45, 0.0, 1.0)
    return 20.0 * ((0.7 * dip_quality) + (0.3 * vol_quality))


def _news_component(news_context: NewsContext) -> float:
    if news_context.risk_override:
        return 0.0
    return clamp(10.0 + news_context.score_modifier, 0.0, 15.0)


def _volume_component(bars: Sequence[Bar]) -> float:
    if not bars:
        return 0.0
    latest = bars[-1].volume
    median = median_recent_volume(bars)
    if median is None:
        return 4.0
    return 10.0 * clamp(latest / median, 0.0, 1.0)


def evaluate_buy_window(signal_input: SignalInput) -> SignalDecision:
    symbol = normalize_symbol(signal_input.symbol)
    current_price = float(signal_input.current_price)
    bars = list(signal_input.intraday_bars)
    daily_closes = [float(value) for value in signal_input.daily_closes if value > 0]

    vwap_value = vwap(bars)
    support_price = support_level(daily_closes, 20)

    breakdown = ScoreBreakdown(
        intraday_discount=round(_intraday_component(current_price, bars), 2),
        historical_setup=round(_historical_component(current_price, daily_closes), 2),
        volatility_quality=round(_volatility_component(current_price, bars, daily_closes), 2),
        news_context=round(_news_component(signal_input.news_context), 2),
        volume_confirmation=round(_volume_component(bars), 2),
    )
    confidence = int(round(clamp(breakdown.total, 0.0, 100.0)))
    reasons: List[str] = []

    percentile = range_percentile(current_price, bars)
    if percentile is not None:
        reasons.append(f"Price is in the lower {int(round(percentile * 100))}% of today's range.")
    if vwap_value is not None and current_price < vwap_value:
        reasons.append("Price is below VWAP.")
    current_rsi = rsi([bar.close for bar in bars], period=14)
    if current_rsi is not None:
        if current_rsi < 35:
            reasons.append("RSI is near oversold territory.")
        elif current_rsi < 50:
            reasons.append("RSI is below neutral and being monitored.")
    if signal_input.news_context.summary:
        reasons.append(signal_input.news_context.summary)

    blockers: List[str] = []
    if not signal_input.market_is_open:
        blockers.append("Market is closed.")
    if signal_input.data_is_stale:
        blockers.append("Data is stale.")
    if signal_input.in_open_avoidance_window:
        blockers.append("Inside configured post-open waiting window.")
    if signal_input.news_context.risk_override:
        blockers.append("Major risk news override is active.")

    suggested_price = calculate_suggested_buy_price(current_price, vwap_value, support_price)
    should_alert = confidence >= signal_input.min_confidence and not blockers

    if blockers:
        reasons.extend(blockers)
    if not reasons:
        reasons.append("No favorable intraday setup detected.")

    return SignalDecision(
        symbol=symbol,
        current_price=current_price,
        suggested_buy_price=suggested_price,
        confidence=confidence,
        band=confidence_band(confidence),
        should_alert=should_alert,
        reasons=reasons,
        market_context_summary=signal_input.news_context.summary,
        score_breakdown=breakdown,
        created_at=signal_input.created_at,
    )
