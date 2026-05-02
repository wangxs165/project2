import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.trading_monitor.api import create_app
from backend.trading_monitor.config import AppConfig
from backend.trading_monitor.models import Bar, PriceUpdate
from backend.trading_monitor.monitoring import MonitoringCycleResult
from backend.trading_monitor.storage import Storage


class FakeMonitoringService:
    def __init__(self):
        self.calls = 0

    def run_once(self, now=None):
        self.calls += 1
        return MonitoringCycleResult(
            evaluated_symbols=1,
            generated_signals=1,
            sent_notifications=0,
            market_open=True,
        )


class FakeMarketDataProvider:
    def latest_price(self, symbol, now):
        return PriceUpdate(
            symbol=symbol,
            price=100.0 if symbol == "VOO" else 50.0,
            source_ts=datetime(2026, 5, 1, 20, 0, tzinfo=timezone.utc),
            received_ts=now,
            source="fake",
            delayed=True,
        )

    def daily_bars(self, symbol, lookback_days):
        start = datetime(2026, 4, 27, 20, 0, tzinfo=timezone.utc)
        bars = []
        for index in range(lookback_days):
            open_price = 100.0 + index
            close_price = open_price + 0.5
            bars.append(
                Bar(
                    symbol=symbol,
                    timestamp=start + timedelta(days=index),
                    open=open_price,
                    high=close_price + 1,
                    low=open_price - 1,
                    close=close_price,
                    volume=1000 + index,
                    kind="daily",
                    source="fake",
                )
            )
        return bars


class ApiOptionalDependencyTests(unittest.TestCase):
    def test_create_app_has_helpful_error_without_fastapi(self):
        if importlib.util.find_spec("fastapi") is not None:
            self.skipTest("FastAPI is installed; integration test covers this path.")

        with self.assertRaises(RuntimeError) as context:
            create_app()

        self.assertIn("FastAPI is not installed", str(context.exception))


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class ApiIntegrationTests(unittest.TestCase):
    def test_core_api_routes(self):
        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory() as tempdir:
            storage = Storage(Path(tempdir) / "api.sqlite")
            config = AppConfig(db_path=Path(tempdir) / "api.sqlite")
            service = FakeMonitoringService()
            app = create_app(
                config=config,
                storage=storage,
                monitoring_service=service,
                market_data_provider=FakeMarketDataProvider(),
            )
            client = TestClient(app)

            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertTrue(health.json()["monitoring_only"])

            symbols = client.get("/symbols")
            self.assertEqual(symbols.json()["symbols"], ["IAU", "VOO"])

            added = client.post("/symbols", json={"symbol": "spy"})
            self.assertEqual(added.status_code, 200)
            self.assertIn("SPY", added.json()["symbols"])

            started = client.post("/monitoring/start")
            self.assertTrue(started.json()["monitoring"])

            run_once = client.post("/monitoring/run-once")
            self.assertEqual(run_once.status_code, 200)
            self.assertGreaterEqual(run_once.json()["runner"]["cycles_completed"], 1)

            demo = client.post("/monitoring/run-demo")
            self.assertEqual(demo.status_code, 200)
            self.assertTrue(demo.json()["demo"])
            self.assertTrue(demo.json()["result"]["market_open"])
            self.assertGreaterEqual(demo.json()["result"]["generated_signals"], 1)

            refresh_prices = client.post("/prices/refresh")
            self.assertEqual(refresh_prices.status_code, 200)
            self.assertEqual(refresh_prices.json()["errors"], [])
            self.assertIn("VOO", refresh_prices.json()["prices"])

            history = client.get("/history/open-close")
            self.assertEqual(history.status_code, 200)
            self.assertEqual(history.json()["days"], 5)
            self.assertEqual(len(history.json()["history"]["VOO"]), 5)
            self.assertIn("open", history.json()["history"]["VOO"][0])
            self.assertIn("close", history.json()["history"]["VOO"][0])

            backtest = client.get("/backtest/daily?symbol=VOO&days=35")
            self.assertEqual(backtest.status_code, 200)
            self.assertEqual(backtest.json()["symbol"], "VOO")
            self.assertEqual(backtest.json()["method"], "synthetic_daily_ohlc")
            self.assertIn("open", backtest.json()["deltas"])

            stopped = client.post("/monitoring/stop")
            self.assertFalse(stopped.json()["monitoring"])

            storage.close()


if __name__ == "__main__":
    unittest.main()
