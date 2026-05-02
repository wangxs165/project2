import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.trading_monitor.api import create_app
from backend.trading_monitor.config import AppConfig
from backend.trading_monitor.models import PriceUpdate
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

            refresh_prices = client.post("/prices/refresh")
            self.assertEqual(refresh_prices.status_code, 200)
            self.assertEqual(refresh_prices.json()["errors"], [])
            self.assertIn("VOO", refresh_prices.json()["prices"])

            stopped = client.post("/monitoring/stop")
            self.assertFalse(stopped.json()["monitoring"])

            storage.close()


if __name__ == "__main__":
    unittest.main()
