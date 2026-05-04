from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import Bar, NotificationRecord, PriceUpdate, SignalDecision, normalize_symbol


class Storage:
    """Small SQLite persistence layer for the local Phase I app."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def initialize(self, default_symbols: Iterable[str] = ("VOO", "IAU")) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS watchlist (
                    symbol TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    bid REAL,
                    ask REAL,
                    last REAL,
                    volume REAL,
                    delayed INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    source_ts TEXT NOT NULL,
                    received_ts TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_prices_symbol_received
                    ON prices(symbol, received_ts DESC);

                CREATE TABLE IF NOT EXISTS bars (
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    source TEXT NOT NULL,
                    PRIMARY KEY(symbol, timestamp, kind)
                );

                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    current_price REAL NOT NULL,
                    suggested_buy_price REAL,
                    confidence INTEGER NOT NULL,
                    band TEXT NOT NULL,
                    should_alert INTEGER NOT NULL,
                    reasons_json TEXT NOT NULL,
                    market_context_summary TEXT NOT NULL,
                    score_breakdown_json TEXT NOT NULL,
                    disclaimer TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_signals_symbol_created
                    ON signals(symbol, created_at DESC);

                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence INTEGER,
                    message TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_notifications_symbol_created
                    ON notifications(symbol, created_at DESC);
                """
            )
            for symbol in default_symbols:
                self.add_symbol(symbol)
            self._conn.commit()

    def add_symbol(self, symbol: str) -> str:
        normalized = normalize_symbol(symbol)
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO watchlist(symbol) VALUES (?)",
                (normalized,),
            )
            self._conn.commit()
        return normalized

    def remove_symbol(self, symbol: str) -> bool:
        normalized = normalize_symbol(symbol)
        with self._lock:
            cursor = self._conn.execute("DELETE FROM watchlist WHERE symbol = ?", (normalized,))
            self._conn.commit()
            return cursor.rowcount > 0

    def get_watchlist(self) -> List[str]:
        with self._lock:
            rows = self._conn.execute("SELECT symbol FROM watchlist ORDER BY symbol").fetchall()
        return [row["symbol"] for row in rows]

    def save_price(self, update: PriceUpdate) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO prices(
                    symbol, price, bid, ask, last, volume, delayed, source, source_ts, received_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    update.symbol,
                    update.price,
                    update.bid,
                    update.ask,
                    update.last,
                    update.volume,
                    int(update.delayed),
                    update.source,
                    update.source_ts.isoformat(),
                    update.received_ts.isoformat(),
                ),
            )
            self._conn.commit()

    def latest_prices(self) -> Dict[str, Dict[str, object]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT p.*
                FROM prices p
                JOIN (
                    SELECT symbol, MAX(id) AS id
                    FROM prices
                    GROUP BY symbol
                ) latest
                    ON latest.symbol = p.symbol AND latest.id = p.id
                ORDER BY p.symbol
                """
            ).fetchall()
        return {row["symbol"]: dict(row) for row in rows}

    def save_bar(self, bar: Bar) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO bars(
                    symbol, timestamp, kind, open, high, low, close, volume, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bar.symbol,
                    bar.timestamp.isoformat(),
                    bar.kind,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume,
                    bar.source,
                ),
            )
            self._conn.commit()

    def save_bars(self, bars: Iterable[Bar]) -> int:
        saved = 0
        with self._lock:
            for bar in bars:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO bars(
                        symbol, timestamp, kind, open, high, low, close, volume, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bar.symbol,
                        bar.timestamp.isoformat(),
                        bar.kind,
                        bar.open,
                        bar.high,
                        bar.low,
                        bar.close,
                        bar.volume,
                        bar.source,
                    ),
                )
                saved += 1
            self._conn.commit()
        return saved

    def list_bars(self, symbol: str, kind: str = "intraday", limit: int = 100) -> List[Dict[str, object]]:
        normalized = normalize_symbol(symbol)
        if kind not in {"intraday", "daily"}:
            raise ValueError("kind must be 'intraday' or 'daily'")
        bounded_limit = max(1, min(limit, 1000))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT *
                FROM bars
                WHERE symbol = ? AND kind = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (normalized, kind, bounded_limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_signal(self, signal: SignalDecision) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO signals(
                    symbol, current_price, suggested_buy_price, confidence, band,
                    should_alert, reasons_json, market_context_summary,
                    score_breakdown_json, disclaimer, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.symbol,
                    signal.current_price,
                    signal.suggested_buy_price,
                    signal.confidence,
                    signal.band,
                    int(signal.should_alert),
                    json.dumps(signal.reasons),
                    signal.market_context_summary,
                    json.dumps(signal.score_breakdown.as_dict()),
                    signal.disclaimer,
                    signal.created_at.isoformat(),
                ),
            )
            self._conn.commit()

    def list_signals(self, limit: int = 100) -> List[Dict[str, object]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM signals
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["should_alert"] = bool(item["should_alert"])
            item["reasons"] = json.loads(item.pop("reasons_json"))
            item["score_breakdown"] = json.loads(item.pop("score_breakdown_json"))
            result.append(item)
        return result

    def save_notification(self, record: NotificationRecord) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO notifications(symbol, status, confidence, message, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.symbol,
                    record.status,
                    record.confidence,
                    record.message,
                    record.error,
                    record.created_at.isoformat(),
                ),
            )
            self._conn.commit()

    def list_notifications(self, limit: int = 100) -> List[Dict[str, object]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM notifications
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_notifications_for_day(self, symbol: str, day_prefix: str) -> int:
        normalized = normalize_symbol(symbol)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM notifications
                WHERE symbol = ?
                  AND status = 'sent'
                  AND created_at >= ?
                  AND created_at < ?
                """,
                (normalized, f"{day_prefix}T00:00:00", f"{day_prefix}T23:59:59.999999"),
            ).fetchone()
        return int(row["count"])

    def latest_notification(self, symbol: str) -> Optional[Dict[str, object]]:
        normalized = normalize_symbol(symbol)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM notifications
                WHERE symbol = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
        return dict(row) if row else None
