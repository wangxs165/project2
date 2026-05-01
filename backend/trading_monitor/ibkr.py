from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Sequence

from .config import IbkrConfig
from .models import PriceUpdate, normalize_symbol


class IbkrUnavailable(RuntimeError):
    """Raised when ib_insync is unavailable or IBKR cannot be reached."""


@dataclass(frozen=True)
class IbkrConnectionStatus:
    connected: bool
    delayed: bool = False
    message: str = ""


class IbkrMarketDataClient:
    """Thin market-data-only adapter around ib_insync.

    This class intentionally does not expose order placement methods.
    """

    def __init__(self, config: IbkrConfig) -> None:
        self.config = config
        self._ib = None

    def connect(self) -> IbkrConnectionStatus:
        try:
            from ib_insync import IB  # type: ignore
        except ImportError as exc:
            raise IbkrUnavailable("ib_insync is not installed") from exc

        self._ib = IB()
        try:
            self._ib.connect(self.config.host, self.config.port, clientId=self.config.client_id)
        except Exception as exc:  # pragma: no cover - exercised by manual/integration tests
            return IbkrConnectionStatus(False, message=str(exc))
        return IbkrConnectionStatus(bool(self._ib.isConnected()), message="connected")

    def _require_ib(self):
        if self._ib is None:
            status = self.connect()
            if not status.connected:
                raise IbkrUnavailable(status.message or "IBKR is not connected")
        return self._ib

    def _stock_contract(self, symbol: str):
        try:
            from ib_insync import Stock  # type: ignore
        except ImportError as exc:
            raise IbkrUnavailable("ib_insync is not installed") from exc
        return Stock(normalize_symbol(symbol), "SMART", "USD")

    def latest_price(self, symbol: str, now: datetime) -> PriceUpdate:
        ib = self._require_ib()
        contract = self._stock_contract(symbol)
        ib.qualifyContracts(contract)
        ticker = ib.reqMktData(contract, "", False, False)
        ib.sleep(1)

        market_price = ticker.marketPrice()
        bid = getattr(ticker, "bid", None)
        ask = getattr(ticker, "ask", None)
        last = getattr(ticker, "last", None)
        volume = getattr(ticker, "volume", None)

        if market_price is None or market_price <= 0:
            prices = [value for value in (last, bid, ask) if value is not None and value > 0]
            if bid is not None and ask is not None and bid > 0 and ask > 0:
                prices.append((bid + ask) / 2)
            if not prices:
                raise IbkrUnavailable(f"No usable market price for {symbol}")
            market_price = prices[0]

        return PriceUpdate(
            symbol=symbol,
            price=float(market_price),
            bid=bid if bid and bid > 0 else None,
            ask=ask if ask and ask > 0 else None,
            last=last if last and last > 0 else None,
            volume=volume if volume and volume >= 0 else None,
            delayed=False,
            source="ibkr",
            source_ts=now,
            received_ts=now,
        )

    def intraday_bars(self, symbol: str, now: datetime) -> Sequence["Bar"]:
        return self._historical_bars(
            symbol=symbol,
            duration="1 D",
            bar_size="5 mins",
            kind="intraday",
            lookback_limit=None,
        )

    def daily_closes(self, symbol: str, lookback_days: int) -> Sequence[float]:
        bars = self._historical_bars(
            symbol=symbol,
            duration=f"{max(lookback_days, 1)} D",
            bar_size="1 day",
            kind="daily",
            lookback_limit=lookback_days,
        )
        return [bar.close for bar in bars]

    def _historical_bars(
        self,
        symbol: str,
        duration: str,
        bar_size: str,
        kind: str,
        lookback_limit: Optional[int],
    ) -> Sequence["Bar"]:
        from .models import Bar

        ib = self._require_ib()
        contract = self._stock_contract(symbol)
        ib.qualifyContracts(contract)
        raw_bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        converted: List[Bar] = []
        for raw in raw_bars:
            timestamp = raw.date
            if not isinstance(timestamp, datetime):
                timestamp = datetime.combine(timestamp, datetime.min.time(), tzinfo=timezone.utc)
            elif timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            converted.append(
                Bar(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=float(raw.open),
                    high=float(raw.high),
                    low=float(raw.low),
                    close=float(raw.close),
                    volume=float(raw.volume or 0),
                    kind=kind,
                    source="ibkr",
                )
            )
        if lookback_limit is not None:
            return converted[-lookback_limit:]
        return converted

    @staticmethod
    def normalize_tick(
        symbol: str,
        price: float,
        source_ts: Optional[datetime] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        last: Optional[float] = None,
        volume: Optional[float] = None,
        delayed: bool = False,
    ) -> PriceUpdate:
        now = datetime.now(timezone.utc)
        return PriceUpdate(
            symbol=normalize_symbol(symbol),
            price=price,
            bid=bid,
            ask=ask,
            last=last,
            volume=volume,
            delayed=delayed,
            source="ibkr",
            source_ts=source_ts or now,
            received_ts=now,
        )
