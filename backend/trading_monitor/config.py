from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

from .models import normalize_symbol


class ConfigError(ValueError):
    """Raised when application configuration is invalid."""


def _bool_from_env(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Invalid boolean value: {value!r}")


def _int_from_env(value: str, default: int, name: str) -> int:
    if value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class MarketHoursConfig:
    timezone: str = "America/Los_Angeles"
    start: str = "06:30"
    end: str = "13:00"
    regular_hours_only: bool = True
    avoid_open_minutes: int = 10


@dataclass(frozen=True)
class AlertConfig:
    min_confidence: int = 75
    cooldown_minutes: int = 30
    max_alerts_per_symbol_per_day: int = 3


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool = True
    bot_token: str = ""
    chat_id: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


@dataclass(frozen=True)
class IbkrConfig:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 11


@dataclass(frozen=True)
class GuiConfig:
    host: str = "127.0.0.1"
    port: int = 8080


@dataclass(frozen=True)
class MonitoringConfig:
    interval_seconds: int = 60
    stale_after_seconds: int = 120


@dataclass(frozen=True)
class AppConfig:
    symbols: Tuple[str, ...] = ("VOO", "IAU")
    db_path: Path = Path("data/trading_monitor.sqlite")
    market_hours: MarketHoursConfig = MarketHoursConfig()
    alerts: AlertConfig = AlertConfig()
    telegram: TelegramConfig = TelegramConfig()
    ibkr: IbkrConfig = IbkrConfig()
    gui: GuiConfig = GuiConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    auto_trade_enabled: bool = False

    def __post_init__(self) -> None:
        symbols = tuple(dict.fromkeys(normalize_symbol(symbol) for symbol in self.symbols))
        if not symbols:
            raise ConfigError("At least one symbol must be configured")
        object.__setattr__(self, "symbols", symbols)
        if self.alerts.min_confidence < 0 or self.alerts.min_confidence > 100:
            raise ConfigError("min_confidence must be between 0 and 100")
        if self.alerts.cooldown_minutes < 0:
            raise ConfigError("cooldown_minutes must be non-negative")
        if self.alerts.max_alerts_per_symbol_per_day < 1:
            raise ConfigError("max_alerts_per_symbol_per_day must be at least 1")
        if self.market_hours.avoid_open_minutes < 0:
            raise ConfigError("avoid_open_minutes must be non-negative")
        if self.gui.host != "127.0.0.1":
            raise ConfigError("Phase I GUI must bind to 127.0.0.1")
        if self.monitoring.interval_seconds < 1:
            raise ConfigError("monitoring interval must be at least 1 second")
        if self.monitoring.stale_after_seconds < 1:
            raise ConfigError("stale data threshold must be at least 1 second")
        if self.auto_trade_enabled:
            raise ConfigError("auto_trade_enabled must remain false")


def load_config(env: Mapping[str, str] = os.environ) -> AppConfig:
    symbols_raw = env.get("WATCHLIST", "")
    symbols = tuple(part.strip() for part in symbols_raw.split(",") if part.strip()) or ("VOO", "IAU")

    auto_trade_enabled = _bool_from_env(env.get("AUTO_TRADE_ENABLED", "false"))
    if auto_trade_enabled:
        raise ConfigError("AUTO_TRADE_ENABLED must be false; this app is monitoring-only")

    return AppConfig(
        symbols=symbols,
        db_path=Path(env.get("APP_DB_PATH", "data/trading_monitor.sqlite")),
        market_hours=MarketHoursConfig(
            timezone=env.get("MARKET_TIMEZONE", "America/Los_Angeles"),
            start=env.get("MARKET_OPEN", "06:30"),
            end=env.get("MARKET_CLOSE", "13:00"),
            avoid_open_minutes=_int_from_env(env.get("AVOID_OPEN_MINUTES", ""), 10, "AVOID_OPEN_MINUTES"),
        ),
        alerts=AlertConfig(
            min_confidence=_int_from_env(env.get("MIN_CONFIDENCE", ""), 75, "MIN_CONFIDENCE"),
            cooldown_minutes=_int_from_env(env.get("ALERT_COOLDOWN_MINUTES", ""), 30, "ALERT_COOLDOWN_MINUTES"),
            max_alerts_per_symbol_per_day=_int_from_env(
                env.get("MAX_ALERTS_PER_SYMBOL_PER_DAY", ""),
                3,
                "MAX_ALERTS_PER_SYMBOL_PER_DAY",
            ),
        ),
        telegram=TelegramConfig(
            enabled=_bool_from_env(env.get("TELEGRAM_ENABLED", "true"), default=True),
            bot_token=env.get("TELEGRAM_BOT_TOKEN", ""),
            chat_id=env.get("TELEGRAM_CHAT_ID", ""),
        ),
        ibkr=IbkrConfig(
            host=env.get("IBKR_HOST", "127.0.0.1"),
            port=_int_from_env(env.get("IBKR_PORT", ""), 7497, "IBKR_PORT"),
            client_id=_int_from_env(env.get("IBKR_CLIENT_ID", ""), 11, "IBKR_CLIENT_ID"),
        ),
        gui=GuiConfig(
            host=env.get("APP_HOST", "127.0.0.1"),
            port=_int_from_env(env.get("APP_PORT", ""), 8080, "APP_PORT"),
        ),
        monitoring=MonitoringConfig(
            interval_seconds=_int_from_env(
                env.get("MONITOR_INTERVAL_SECONDS", ""),
                60,
                "MONITOR_INTERVAL_SECONDS",
            ),
            stale_after_seconds=_int_from_env(
                env.get("STALE_AFTER_SECONDS", ""),
                120,
                "STALE_AFTER_SECONDS",
            ),
        ),
        auto_trade_enabled=auto_trade_enabled,
    )
