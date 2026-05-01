from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .config import AlertConfig
from .models import SignalDecision, normalize_symbol
from .storage import Storage


@dataclass(frozen=True)
class AlertGateResult:
    allowed: bool
    reason: str


class AlertGate:
    def __init__(self, storage: Storage, config: AlertConfig) -> None:
        self.storage = storage
        self.config = config

    def evaluate(self, signal: SignalDecision, now: Optional[datetime] = None) -> AlertGateResult:
        symbol = normalize_symbol(signal.symbol)
        current_time = now or signal.created_at

        if not signal.should_alert:
            return AlertGateResult(False, "Signal is below alert threshold or blocked by signal engine.")
        if signal.confidence < self.config.min_confidence:
            return AlertGateResult(False, "Signal confidence is below configured minimum.")

        day_prefix = current_time.date().isoformat()
        sent_today = self.storage.count_notifications_for_day(symbol, day_prefix)
        if sent_today >= self.config.max_alerts_per_symbol_per_day:
            return AlertGateResult(False, "Daily alert cap reached for symbol.")

        latest = self.storage.latest_notification(symbol)
        if latest and latest.get("status") == "sent":
            latest_created = datetime.fromisoformat(str(latest["created_at"]))
            elapsed_minutes = (current_time - latest_created).total_seconds() / 60.0
            if elapsed_minutes < self.config.cooldown_minutes:
                return AlertGateResult(False, "Alert cooldown has not elapsed.")

        return AlertGateResult(True, "Alert allowed.")

