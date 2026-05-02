from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from .config import AppConfig, load_config
from .demo import DemoMarketDataProvider, demo_market_time
from .ibkr import IbkrMarketDataClient
from .monitoring import MonitoringService, NeutralNewsProvider
from .models import DISCLAIMER, NotificationRecord, ScoreBreakdown, SignalDecision, normalize_symbol
from .runtime import BackgroundMonitoringRunner, MonitoringRuntime
from .signal_engine import SignalInput, evaluate_buy_window
from .storage import Storage
from .telegram import TelegramClient
from .yahoo import YFinanceMarketDataClient


def create_app(
    config: Optional[AppConfig] = None,
    storage: Optional[Storage] = None,
    monitoring_service: Optional[MonitoringService] = None,
    market_data_provider=None,
):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError(
            "FastAPI is not installed. Install API dependencies with: "
            'python3 -m pip install -e ".[api]"'
        ) from exc

    app_config = config or load_config()
    app_storage = storage or Storage(app_config.db_path)
    app_storage.initialize(app_config.symbols)
    market_data = market_data_provider
    if market_data is None:
        if app_config.data_provider.name == "ibkr":
            market_data = IbkrMarketDataClient(app_config.ibkr)
        else:
            market_data = YFinanceMarketDataClient(
                interval=app_config.data_provider.intraday_interval,
                daily_lookback_period=app_config.data_provider.daily_lookback_period,
            )
    service = monitoring_service or MonitoringService(
        storage=app_storage,
        config=app_config,
        market_data=market_data,
        notifier=TelegramClient(app_config.telegram.bot_token, app_config.telegram.chat_id),
        news_provider=NeutralNewsProvider(),
        stale_after_seconds=app_config.monitoring.stale_after_seconds,
    )
    runner = BackgroundMonitoringRunner(service, app_config.monitoring.interval_seconds)
    runtime = MonitoringRuntime(app_storage, runner)
    runtime.data_provider = app_config.data_provider.name
    static_dir = Path(__file__).parent / "static"

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            runtime.stop()

    app = FastAPI(
        title="Intraday Investment Monitoring App",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")

    @app.get("/health")
    def health():
        return {
            "ok": True,
            "monitoring_only": True,
            "auto_trade_enabled": False,
            "disclaimer": DISCLAIMER,
        }

    @app.get("/status")
    def status():
        return runtime.status()

    @app.get("/symbols")
    def list_symbols():
        return {"symbols": app_storage.get_watchlist()}

    @app.post("/symbols")
    def add_symbol(payload: Dict[str, str]):
        symbol = payload.get("symbol", "")
        try:
            normalized = app_storage.add_symbol(symbol)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"symbol": normalized, "symbols": app_storage.get_watchlist()}

    @app.delete("/symbols/{symbol}")
    def remove_symbol(symbol: str):
        try:
            normalized = normalize_symbol(symbol)
            removed = app_storage.remove_symbol(normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"symbol": normalized, "removed": removed, "symbols": app_storage.get_watchlist()}

    @app.post("/monitoring/start")
    def start_monitoring():
        return runtime.start()

    @app.post("/monitoring/stop")
    def stop_monitoring():
        return runtime.stop()

    @app.post("/monitoring/run-once")
    def run_monitoring_once():
        return runtime.run_once()

    @app.post("/monitoring/run-demo")
    def run_demo_analysis():
        demo_time = demo_market_time(datetime.now(timezone.utc))
        demo_provider = DemoMarketDataProvider()
        generated = 0
        errors = []
        for symbol in app_storage.get_watchlist():
            try:
                price = demo_provider.latest_price(symbol, demo_time)
                bars = list(demo_provider.intraday_bars(symbol, demo_time))
                daily_closes = list(demo_provider.daily_closes(symbol, 220))
                app_storage.save_price(price)
                for bar in bars:
                    app_storage.save_bar(bar)
                signal = evaluate_buy_window(
                    SignalInput(
                        symbol=symbol,
                        current_price=price.price,
                        intraday_bars=bars,
                        daily_closes=daily_closes,
                        news_context=NeutralNewsProvider().context_for(symbol),
                        created_at=demo_time,
                        min_confidence=app_config.alerts.min_confidence,
                        market_is_open=True,
                        data_is_stale=False,
                        in_open_avoidance_window=False,
                    )
                )
                app_storage.save_signal(signal)
                generated += 1
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")
        return {
            "demo": True,
            "market_time": demo_time.isoformat(),
            "result": {
                "evaluated_symbols": len(app_storage.get_watchlist()),
                "generated_signals": generated,
                "sent_notifications": 0,
                "blocked_notifications": 0,
                "errors": errors,
                "market_open": True,
            },
        }

    @app.get("/prices")
    def prices():
        return {"prices": app_storage.latest_prices()}

    @app.get("/history/open-close")
    def open_close_history(days: int = 5):
        bounded_days = max(1, min(days, 20))
        result = {}
        errors = []
        for symbol in app_storage.get_watchlist():
            try:
                bars = list(market_data.daily_bars(symbol, bounded_days))
                result[symbol] = [
                    {
                        "date": bar.timestamp.date().isoformat(),
                        "open": bar.open,
                        "close": bar.close,
                        "high": bar.high,
                        "low": bar.low,
                        "volume": bar.volume,
                        "source": bar.source,
                    }
                    for bar in bars[-bounded_days:]
                ]
            except Exception as exc:
                result[symbol] = []
                errors.append({"symbol": symbol, "error": str(exc)})
        return {"days": bounded_days, "history": result, "errors": errors}

    @app.post("/prices/refresh")
    def refresh_prices():
        now = datetime.now(timezone.utc)
        refreshed = []
        errors = []
        for symbol in app_storage.get_watchlist():
            try:
                price = market_data.latest_price(symbol, now)
                app_storage.save_price(price)
                refreshed.append(symbol)
            except Exception as exc:
                errors.append({"symbol": symbol, "error": str(exc)})
        return {
            "refreshed": refreshed,
            "errors": errors,
            "prices": app_storage.latest_prices(),
        }

    @app.get("/signals")
    def signals(limit: int = 100):
        return {"signals": app_storage.list_signals(limit=limit)}

    @app.get("/notifications")
    def notifications(limit: int = 100):
        return {"notifications": app_storage.list_notifications(limit=limit)}

    @app.post("/notifications/test")
    def test_notification():
        dummy = SignalDecision(
            symbol=app_storage.get_watchlist()[0],
            current_price=1.0,
            suggested_buy_price=1.0,
            confidence=0,
            band="Test notification",
            should_alert=False,
            reasons=["Telegram test notification."],
            market_context_summary="Manual test.",
            score_breakdown=ScoreBreakdown(0, 0, 0, 0, 0),
            created_at=datetime.now(timezone.utc),
        )
        client = TelegramClient(app_config.telegram.bot_token, app_config.telegram.chat_id)
        record = client.send_signal(dummy)
        app_storage.save_notification(record)
        return {"status": record.status, "error": record.error}

    return app


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError(
            "uvicorn is not installed. Install API dependencies with: "
            'python3 -m pip install -e ".[api]"'
        ) from exc

    config = load_config()
    uvicorn.run(create_app(config), host=config.gui.host, port=config.gui.port)


if __name__ == "__main__":
    main()
