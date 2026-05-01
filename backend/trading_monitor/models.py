from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


DISCLAIMER = "Monitoring suggestion only. This app does not place trades. Manual review required."

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class ValidationError(ValueError):
    """Raised when user or market data is invalid."""


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not _SYMBOL_RE.match(normalized):
        raise ValidationError(f"Invalid symbol: {symbol!r}")
    return normalized


def require_positive_number(name: str, value: float) -> float:
    if value is None or value <= 0:
        raise ValidationError(f"{name} must be positive")
    return float(value)


def require_non_negative_number(name: str, value: float) -> float:
    if value is None or value < 0:
        raise ValidationError(f"{name} must be non-negative")
    return float(value)


def require_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValidationError(f"{name} must be a datetime")
    return value


@dataclass(frozen=True)
class PriceUpdate:
    symbol: str
    price: float
    source_ts: datetime
    received_ts: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    volume: Optional[float] = None
    delayed: bool = False
    source: str = "unknown"

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "price", require_positive_number("price", self.price))
        object.__setattr__(self, "source_ts", require_datetime("source_ts", self.source_ts))
        object.__setattr__(self, "received_ts", require_datetime("received_ts", self.received_ts))
        for attr in ("bid", "ask", "last"):
            value = getattr(self, attr)
            if value is not None:
                object.__setattr__(self, attr, require_positive_number(attr, value))
        if self.volume is not None:
            object.__setattr__(self, "volume", require_non_negative_number("volume", self.volume))
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValidationError("bid cannot be greater than ask")


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    kind: str = "intraday"
    source: str = "unknown"

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "timestamp", require_datetime("timestamp", self.timestamp))
        for attr in ("open", "high", "low", "close"):
            object.__setattr__(self, attr, require_positive_number(attr, getattr(self, attr)))
        object.__setattr__(self, "volume", require_non_negative_number("volume", self.volume))
        if self.low > self.high:
            raise ValidationError("low cannot be greater than high")
        if not self.low <= self.open <= self.high:
            raise ValidationError("open must be inside high/low range")
        if not self.low <= self.close <= self.high:
            raise ValidationError("close must be inside high/low range")
        if self.kind not in {"intraday", "daily"}:
            raise ValidationError("kind must be 'intraday' or 'daily'")


@dataclass(frozen=True)
class NewsContext:
    summary: str = "News context unavailable or neutral."
    score_modifier: int = 0
    risk_override: bool = False
    categories: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.score_modifier < -15 or self.score_modifier > 15:
            raise ValidationError("score_modifier must be between -15 and 15")


@dataclass(frozen=True)
class ScoreBreakdown:
    intraday_discount: float
    historical_setup: float
    volatility_quality: float
    news_context: float
    volume_confirmation: float

    @property
    def total(self) -> float:
        return (
            self.intraday_discount
            + self.historical_setup
            + self.volatility_quality
            + self.news_context
            + self.volume_confirmation
        )

    def as_dict(self) -> Dict[str, float]:
        return {
            "intraday_discount": self.intraday_discount,
            "historical_setup": self.historical_setup,
            "volatility_quality": self.volatility_quality,
            "news_context": self.news_context,
            "volume_confirmation": self.volume_confirmation,
        }


@dataclass(frozen=True)
class SignalDecision:
    symbol: str
    current_price: float
    suggested_buy_price: Optional[float]
    confidence: int
    band: str
    should_alert: bool
    reasons: List[str]
    market_context_summary: str
    score_breakdown: ScoreBreakdown
    created_at: datetime
    disclaimer: str = DISCLAIMER

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "current_price", require_positive_number("current_price", self.current_price))
        if self.suggested_buy_price is not None:
            object.__setattr__(
                self,
                "suggested_buy_price",
                require_positive_number("suggested_buy_price", self.suggested_buy_price),
            )
            if self.suggested_buy_price > self.current_price:
                raise ValidationError("suggested_buy_price cannot be above current_price")
        if self.confidence < 0 or self.confidence > 100:
            raise ValidationError("confidence must be between 0 and 100")
        require_datetime("created_at", self.created_at)


@dataclass(frozen=True)
class NotificationRecord:
    symbol: str
    status: str
    message: str
    created_at: datetime
    error: Optional[str] = None
    confidence: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        require_datetime("created_at", self.created_at)
        if self.status not in {"sent", "failed", "blocked"}:
            raise ValidationError("notification status must be sent, failed, or blocked")
        if self.confidence is not None and not 0 <= self.confidence <= 100:
            raise ValidationError("confidence must be between 0 and 100")

