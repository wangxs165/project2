from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Protocol, Sequence

from .config import AppConfig
from .market_hours import is_open_avoidance_window, is_regular_market_hours, to_market_timezone
from .models import Bar, NewsContext, NotificationRecord, PriceUpdate
from .risk import AlertGate
from .signal_engine import SignalInput, evaluate_buy_window
from .storage import Storage


class MarketDataProvider(Protocol):
    def latest_price(self, symbol: str, now: datetime) -> PriceUpdate:
        ...

    def intraday_bars(self, symbol: str, now: datetime) -> Sequence[Bar]:
        ...

    def daily_closes(self, symbol: str, lookback_days: int) -> Sequence[float]:
        ...


class NewsProvider(Protocol):
    def context_for(self, symbol: str) -> NewsContext:
        ...


class SignalNotifier(Protocol):
    def send_signal(self, signal, now: datetime) -> NotificationRecord:
        ...


class NeutralNewsProvider:
    def context_for(self, symbol: str) -> NewsContext:
        return NewsContext(summary="News context unavailable or neutral.")


@dataclass
class MonitoringCycleResult:
    evaluated_symbols: int = 0
    generated_signals: int = 0
    sent_notifications: int = 0
    blocked_notifications: int = 0
    errors: List[str] = field(default_factory=list)
    market_open: bool = False


class MonitoringService:
    def __init__(
        self,
        storage: Storage,
        config: AppConfig,
        market_data: MarketDataProvider,
        notifier: SignalNotifier,
        news_provider: NewsProvider = NeutralNewsProvider(),
        stale_after_seconds: int = 120,
    ) -> None:
        self.storage = storage
        self.config = config
        self.market_data = market_data
        self.notifier = notifier
        self.news_provider = news_provider
        self.stale_after_seconds = stale_after_seconds

    def run_once(self, now: Optional[datetime] = None) -> MonitoringCycleResult:
        current_time = now or datetime.now(timezone.utc)
        market_time = to_market_timezone(current_time, self.config.market_hours)
        market_open = is_regular_market_hours(market_time, self.config.market_hours)
        open_delay = is_open_avoidance_window(market_time, self.config.market_hours)
        result = MonitoringCycleResult(market_open=market_open)

        if not market_open:
            return result

        gate = AlertGate(self.storage, self.config.alerts)
        for symbol in self.storage.get_watchlist():
            result.evaluated_symbols += 1
            try:
                price = self.market_data.latest_price(symbol, market_time)
                bars = list(self.market_data.intraday_bars(symbol, market_time))
                daily_closes = list(self.market_data.daily_closes(symbol, 220))
                news_context = self.news_provider.context_for(symbol)

                self.storage.save_price(price)
                for bar in bars:
                    self.storage.save_bar(bar)

                age_seconds = abs((market_time - price.received_ts).total_seconds())
                data_is_stale = age_seconds > self.stale_after_seconds

                signal = evaluate_buy_window(
                    SignalInput(
                        symbol=symbol,
                        current_price=price.price,
                        intraday_bars=bars,
                        daily_closes=daily_closes,
                        news_context=news_context,
                        created_at=market_time,
                        min_confidence=self.config.alerts.min_confidence,
                        market_is_open=market_open,
                        data_is_stale=data_is_stale,
                        in_open_avoidance_window=open_delay,
                    )
                )
                self.storage.save_signal(signal)
                result.generated_signals += 1

                gate_result = gate.evaluate(signal, market_time)
                if gate_result.allowed:
                    record = self.notifier.send_signal(signal, market_time)
                    self.storage.save_notification(record)
                    if record.status == "sent":
                        result.sent_notifications += 1
                    else:
                        result.errors.append(record.error or "Notification failed")
                elif signal.confidence >= self.config.alerts.min_confidence:
                    self.storage.save_notification(
                        NotificationRecord(
                            symbol=symbol,
                            status="blocked",
                            confidence=signal.confidence,
                            message=gate_result.reason,
                            created_at=market_time,
                        )
                    )
                    result.blocked_notifications += 1
            except Exception as exc:
                result.errors.append(f"{symbol}: {exc}")

        return result
