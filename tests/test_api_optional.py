import importlib.util
import tempfile
import unittest
from pathlib import Path

from backend.trading_monitor.api import create_app
from backend.trading_monitor.config import AppConfig
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
            app = create_app(config=config, storage=storage, monitoring_service=service)
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

            stopped = client.post("/monitoring/stop")
            self.assertFalse(stopped.json()["monitoring"])

            storage.close()


if __name__ == "__main__":
    unittest.main()
