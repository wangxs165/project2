from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Optional

from .models import DISCLAIMER, NotificationRecord, SignalDecision


class TelegramError(RuntimeError):
    """Raised when Telegram notification sending fails."""


def redact_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def format_signal_message(signal: SignalDecision) -> str:
    suggested = (
        f"${signal.suggested_buy_price:.2f} or below"
        if signal.suggested_buy_price is not None
        else "Unavailable"
    )
    reasoning = "\n".join(f"- {reason}" for reason in signal.reasons)
    return (
        "BUY WINDOW SUGGESTION\n\n"
        f"Ticker: {signal.symbol}\n"
        f"Current price: ${signal.current_price:.2f}\n"
        f"Suggested buying price: {suggested}\n"
        f"Confidence: {signal.confidence} / 100\n\n"
        "Reasoning:\n"
        f"{reasoning}\n\n"
        f"{DISCLAIMER}"
    )


class TelegramClient:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout_seconds: int = 10,
        opener: Optional[Callable[[urllib.request.Request, int], object]] = None,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.urlopen

    def send_message(self, text: str) -> None:
        if not self.bot_token:
            raise TelegramError("Telegram bot token is not configured")
        if not self.chat_id:
            raise TelegramError("Telegram chat ID is not configured")

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps({"chat_id": self.chat_id, "text": text}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            response = self._opener(request, self.timeout_seconds)
            status = getattr(response, "status", 200)
            if status >= 400:
                raise TelegramError(f"Telegram API returned HTTP {status}")
        except urllib.error.URLError as exc:
            raise TelegramError(f"Telegram API request failed: {exc.reason}") from exc

    def send_signal(self, signal: SignalDecision, now: Optional[datetime] = None) -> NotificationRecord:
        message = format_signal_message(signal)
        created_at = now or datetime.now(timezone.utc)
        try:
            self.send_message(message)
            return NotificationRecord(
                symbol=signal.symbol,
                status="sent",
                confidence=signal.confidence,
                message=message,
                created_at=created_at,
            )
        except TelegramError as exc:
            return NotificationRecord(
                symbol=signal.symbol,
                status="failed",
                confidence=signal.confidence,
                message=message,
                error=str(exc).replace(self.bot_token, redact_secret(self.bot_token)),
                created_at=created_at,
            )

