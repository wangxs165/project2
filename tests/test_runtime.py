import unittest
from datetime import datetime, timezone

from backend.trading_monitor.monitoring import MonitoringCycleResult
from backend.trading_monitor.runtime import BackgroundMonitoringRunner


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


class FailingMonitoringService:
    def run_once(self, now=None):
        raise RuntimeError("cycle failed")


class BackgroundMonitoringRunnerTests(unittest.TestCase):
    def test_run_once_records_result(self):
        service = FakeMonitoringService()
        runner = BackgroundMonitoringRunner(service, interval_seconds=1)

        result = runner.run_once(datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc))
        status = runner.status()

        self.assertEqual(result.evaluated_symbols, 1)
        self.assertEqual(status["cycles_completed"], 1)
        self.assertEqual(status["last_cycle_result"]["generated_signals"], 1)

    def test_start_and_stop_are_idempotent(self):
        service = FakeMonitoringService()
        runner = BackgroundMonitoringRunner(service, interval_seconds=1)

        self.assertTrue(runner.start())
        self.assertFalse(runner.start())
        self.assertTrue(runner.status()["thread_alive"])
        self.assertTrue(runner.stop())
        self.assertFalse(runner.status()["thread_alive"])
        self.assertFalse(runner.stop())

    def test_loop_records_errors_without_crashing_start(self):
        runner = BackgroundMonitoringRunner(FailingMonitoringService(), interval_seconds=1)

        self.assertTrue(runner.start())
        runner.stop()
        self.assertEqual(runner.status()["last_error"], "cycle failed")

    def test_invalid_interval_rejected(self):
        with self.assertRaises(ValueError):
            BackgroundMonitoringRunner(FakeMonitoringService(), interval_seconds=0)


if __name__ == "__main__":
    unittest.main()

