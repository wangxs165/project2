from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Protocol

from .monitoring import MonitoringCycleResult
from .storage import Storage


class MonitoringServiceProtocol(Protocol):
    def run_once(self, now: Optional[datetime] = None) -> MonitoringCycleResult:
        ...


class BackgroundMonitoringRunner:
    def __init__(self, service: MonitoringServiceProtocol, interval_seconds: int) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.service = service
        self.interval_seconds = interval_seconds
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.cycles_completed = 0
        self.last_cycle_at = ""
        self.last_cycle_result: Optional[MonitoringCycleResult] = None
        self.last_error = ""

    def start(self) -> bool:
        with self._lock:
            if self.is_running():
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, name="monitoring-loop", daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout_seconds: float = 5.0) -> bool:
        with self._lock:
            thread = self._thread
            if thread is None:
                return False
            self._stop_event.set()
        thread.join(timeout=timeout_seconds)
        with self._lock:
            if not thread.is_alive():
                self._thread = None
                return True
            return False

    def run_once(self, now: Optional[datetime] = None) -> MonitoringCycleResult:
        result = self.service.run_once(now)
        with self._lock:
            self.cycles_completed += 1
            self.last_cycle_at = datetime.now(timezone.utc).isoformat()
            self.last_cycle_result = result
            self.last_error = ""
        return result

    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def status(self) -> Dict[str, object]:
        with self._lock:
            return {
                "thread_alive": self.is_running(),
                "interval_seconds": self.interval_seconds,
                "cycles_completed": self.cycles_completed,
                "last_cycle_at": self.last_cycle_at,
                "last_cycle_result": asdict(self.last_cycle_result)
                if self.last_cycle_result is not None
                else None,
                "last_error": self.last_error,
            }

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                with self._lock:
                    self.last_error = str(exc)
            self._stop_event.wait(self.interval_seconds)


@dataclass
class MonitoringRuntime:
    storage: Storage
    runner: BackgroundMonitoringRunner
    running: bool = False
    started_at: str = ""
    stopped_at: str = ""
    ibkr_connected: bool = False
    ibkr_status: str = "not connected"

    def start(self) -> Dict[str, object]:
        started = self.runner.start()
        if started:
            self.running = True
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.stopped_at = ""
        else:
            self.running = self.runner.is_running()
        return self.status()

    def stop(self) -> Dict[str, object]:
        stopped = self.runner.stop()
        if stopped or not self.runner.is_running():
            self.running = False
            self.stopped_at = datetime.now(timezone.utc).isoformat()
        return self.status()

    def run_once(self) -> Dict[str, object]:
        self.runner.run_once()
        return self.status()

    def status(self) -> Dict[str, object]:
        latest_prices = self.storage.latest_prices()
        runner_status = self.runner.status()
        self.running = bool(runner_status["thread_alive"])
        return {
            "monitoring": self.running,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "ibkr_connected": self.ibkr_connected,
            "ibkr_status": self.ibkr_status,
            "tracked_symbols": self.storage.get_watchlist(),
            "latest_price_count": len(latest_prices),
            "runner": runner_status,
        }
