# Execution Log

This file records implementation progress so work can resume after network,
tooling, or context interruptions.

## 2026-05-01

### Checkpoint 1: Planning Accepted

- Read `trading_monitoring.md`.
- Created implementation plan in the assistant response.
- Created comprehensive test strategy in `test_plan.md`.

### Checkpoint 2: Initial Implementation Started

- Created project scaffold directories:
  - `backend/trading_monitor/`
  - `backend/trading_monitor/static/`
  - `tests/`
  - `docs/`
  - `data/`
- Chose dependency-light first pass because `pytest` is not installed and
  internet access may be unreliable.
- Standard-library `unittest` is used for initial verification.

### Checkpoint 3: Phase I Core Backend Scaffold Implemented

- Added core backend modules:
  - `backend/trading_monitor/models.py`
  - `backend/trading_monitor/config.py`
  - `backend/trading_monitor/storage.py`
  - `backend/trading_monitor/market_hours.py`
  - `backend/trading_monitor/indicators.py`
  - `backend/trading_monitor/signal_engine.py`
  - `backend/trading_monitor/risk.py`
  - `backend/trading_monitor/news.py`
  - `backend/trading_monitor/telegram.py`
  - `backend/trading_monitor/ibkr.py`
  - `backend/trading_monitor/runtime.py`
- Added FastAPI-compatible API scaffold in `backend/trading_monitor/api.py`.
- Added local dashboard scaffold in `backend/trading_monitor/static/index.html`.
- Added project metadata and environment examples:
  - `pyproject.toml`
  - `.env.example`
  - `.gitignore`
  - `README.md`

### Checkpoint 4: Automated Tests Added

- Added standard-library `unittest` suites covering:
  - configuration safety
  - market-hours boundaries and holidays
  - indicator calculations
  - signal scoring and blockers
  - SQLite persistence
  - alert cooldowns and daily caps
  - Telegram formatting and error handling
  - news classification
  - IBKR market-data-only adapter constraints
  - optional FastAPI dependency behavior

Verification results:

```text
python3 -m unittest discover -s tests
Ran 52 tests in 0.034s
OK (skipped=1)
```

The skipped test is the FastAPI integration test because FastAPI is not
installed in the current environment.

Syntax verification:

```text
PYTHONPYCACHEPREFIX=/tmp/project2_pycache python3 -m compileall backend tests
OK
```

The first `compileall` attempt failed because Python tried to write bytecode to
`/Users/simwang/Library/Caches/...`, which is outside the writable sandbox. The
rerun with `PYTHONPYCACHEPREFIX=/tmp/project2_pycache` passed.

### Checkpoint 5: Monitoring Cycle and Backtesting Added

- Added provider-driven monitoring service in `backend/trading_monitor/monitoring.py`.
  - Runs one market-hours-gated evaluation cycle.
  - Persists latest prices, bars, signals, and notification records.
  - Applies stale-data detection.
  - Applies alert cooldown and per-symbol daily alert cap.
  - Logs blocked notification attempts.
- Added deterministic intraday backtesting runner in `backend/trading_monitor/backtest.py`.
  - Evaluates signals without lookahead by passing only bars visible at each timestamp.
  - Compares generated signal prices against open, noon, close, and seeded-random baselines.
  - Produces reproducible random baseline results.
- Expanded `backend/trading_monitor/ibkr.py` into a market-data-only provider shell.
  - Supports latest-price, intraday-bar, and daily-close fetch methods when `ib_insync` is installed.
  - Still exposes no order/trade placement methods.

Verification results:

```text
python3 -m unittest discover -s tests
Ran 59 tests in 0.047s
OK (skipped=1)
```

Syntax verification:

```text
PYTHONPYCACHEPREFIX=/tmp/project2_pycache python3 -m compileall backend tests
OK
```

### Checkpoint 6: Virtualenv, API Dependencies, and Port Check

- Created `.venv`.
- Initial editable install failed because the system pip was old and needed a
  setuptools packaging shim.
- Added:
  - `setup.py`
  - `MANIFEST.in`
- Upgraded venv packaging tools:

```text
.venv/bin/python -m pip install --upgrade pip setuptools wheel
```

- Installed API and test dependencies:

```text
.venv/bin/python -m pip install -e '.[api]'
.venv/bin/python -m pip install -e '.[test]'
```

- Verified tests inside the venv:

```text
.venv/bin/python -m unittest discover -s tests
Ran 59 tests in 0.186s
OK (skipped=1)

.venv/bin/python -m pytest -q
58 passed, 1 skipped in 0.19s
```

- Attempted to start the local API:

```text
.venv/bin/python -m backend.trading_monitor.api
```

The server reached application startup but failed to bind to
`127.0.0.1:8080` with:

```text
[Errno 1] operation not permitted
```

This was not a port-conflict error. A later port check showed:

- No listener on `8080`.
- `ControlCe` is listening on ports `5000` and `7000`.
- No `openclaw` text was found in this project.
- `ps` and `pgrep` process-list checks are restricted in the sandbox.

### Checkpoint 7: Local API Started After Permission Approval

- User granted operation permission for binding the local API.
- Started the FastAPI dashboard successfully:

```text
.venv/bin/python -m backend.trading_monitor.api
Uvicorn running on http://127.0.0.1:8080
```

- Verified endpoints with `curl`:

```text
GET /health
{"ok":true,"monitoring_only":true,"auto_trade_enabled":false,...}

GET /symbols
{"symbols":["IAU","VOO"]}

GET /status
{"monitoring":false,"ibkr_connected":false,"tracked_symbols":["IAU","VOO"],...}
```

- Local dashboard URL:
  `http://127.0.0.1:8080`

### Checkpoint 8: Monitoring Lifecycle Wired Into API

- Replaced start/stop flag-only behavior with a real background monitoring
  runner in `backend/trading_monitor/runtime.py`.
- Added config fields:
  - `MONITOR_INTERVAL_SECONDS`, default `60`
  - `STALE_AFTER_SECONDS`, default `120`
- API now builds a `MonitoringService` backed by:
  - SQLite storage
  - `IbkrMarketDataClient`
  - `TelegramClient`
  - neutral news provider
- Added endpoint:

```text
POST /monitoring/run-once
```

- `POST /monitoring/start` now starts a daemon monitoring loop.
- `POST /monitoring/stop` stops the loop and joins the thread.
- FastAPI shutdown uses a lifespan handler to stop monitoring cleanly.
- Dashboard now displays runner cycle count and last cycle result.
- Added runtime/API tests with fake monitoring service injection.

Verification:

```text
.venv/bin/python -m pytest -q
62 passed, 1 skipped in 0.19s

.venv/bin/python -m unittest discover -s tests
Ran 63 tests in 0.203s
OK (skipped=1)
```

- Restarted updated API at `http://127.0.0.1:8080`.
- Verified:
  - `GET /health`
  - `GET /status`
  - `POST /monitoring/run-once`
  - `POST /monitoring/start`
  - `POST /monitoring/stop`
- The current `run-once` result showed `market_open:false` because it was run
  after the configured regular U.S. trading session.

### Checkpoint 9: IBKR Dependency Installed, Live Port Not Detected

- Installed IBKR optional dependency:

```text
.venv/bin/python -m pip install -e '.[ibkr]'
```

- Verified `ib_insync` version:

```text
0.9.86
```

- Checked common local IBKR API ports:
  - `7496`
  - `7497`
  - `4001`
  - `4002`
- No listener was detected on those ports, so live IBKR connection testing
  cannot proceed until TWS or IB Gateway is running with API access enabled.

### Checkpoint 10: yfinance Selected As Default Provider

- User chose yfinance/Yahoo Finance as the default data source to avoid the
  IB Gateway setup blocker.
- Added `backend/trading_monitor/yahoo.py`.
- API now selects the market-data provider from `DATA_PROVIDER`, defaulting to
  `yfinance`.
- Added yfinance-specific environment settings:
  - `YFINANCE_INTRADAY_INTERVAL`
  - `YFINANCE_DAILY_LOOKBACK_PERIOD`
- Kept IBKR as an optional provider through `DATA_PROVIDER=ibkr`.
- Documented yfinance latency/risk tradeoffs in `README.md` and kept alerts
  protected by stale-data checks.

### Checkpoint 11: yfinance Dependency and API Smoke Test

- Installed yfinance into `.venv` with:

```text
.venv/bin/python -m pip install -e ".[api,yfinance]"
```

- Cleared macOS quarantine metadata from the project venv native libraries so
  NumPy/yfinance could import.
- Reinstalled missing `pydantic-core` binary dependency so FastAPI imports work.
- Verified tests:

```text
.venv/bin/python -m pytest -q
66 passed, 1 skipped

python3 -m unittest discover -s tests
Ran 67 tests
OK (skipped=1)
```

- Started the local API at `http://127.0.0.1:8080`.
- Verified:
  - `GET /health`
  - `GET /status`
  - `GET /symbols`
  - `POST /monitoring/run-once`
  - `GET /prices`
  - `GET /signals`
- `POST /monitoring/run-once` correctly returned `market_open:false` and did
  not fetch data because the test ran outside regular U.S. market hours.
- Verified direct yfinance provider fetch for tracked symbols:

```text
IAU 86.72000122070312 2026-05-01T15:59:00-04:00 yfinance
VOO 662.510009765625 2026-05-01T15:59:00-04:00 yfinance
```

### Checkpoint 12: Manual Price Refresh Endpoint

- Added `POST /prices/refresh`.
- The endpoint fetches latest available provider prices for the watchlist and
  saves them to SQLite immediately, including outside market hours.
- The endpoint does not generate signals and does not send notifications.
- Dashboard now has a Refresh Prices button.

### Checkpoint 13: Dashboard Price Tables and Daily History

- Added `GET /history/open-close`.
- The endpoint returns recent daily open, close, high, low, volume, and source
  values for each watchlist symbol.
- Reworked the dashboard from raw JSON blocks to structured operational tables:
  - latest price table
  - 5-day open/close history by symbol
  - compact status metrics
  - compact signal and notification tables

### Checkpoint 14: Run Analysis Dashboard Workflow

- Added a Run Analysis button that calls `POST /monitoring/run-once`.
- Added analysis summary text for the last run, including closed-market skips.
- Replaced compact signal rows with detailed signal cards:
  - current price
  - suggested buy price
  - alert status
  - confidence
  - reasoning bullets
  - component score breakdown
- Added price freshness badges for fresh, market-closed, and stale source data.

### Checkpoint 15: Closed-Market Demo Analysis

- Added deterministic demo market data provider in `backend/trading_monitor/demo.py`.
- Added `POST /monitoring/run-demo` for exercising signal generation while the
  market is closed.
- Demo analysis uses an in-hours timestamp and writes demo signals directly, so
  it can populate signal cards without sending real notifications.
- Dashboard now has a Demo Analysis button.
- Fixed suggested-price rounding so cent rounding never pushes the suggested
  price above the current price.

### Checkpoint 16: Refined Signal Criteria

- Revised signal weights:
  - intraday/VWAP setup
  - momentum recovery
  - historical setup
  - volatility-adjusted dip quality
  - volume confirmation
  - news context
- Added blockers for continuing lower lows and aggressive selling volume.
- Changed the strong setup expectation to require stabilization after a dip,
  instead of rewarding a still-falling price below VWAP.

### Checkpoint 17: Daily OHLC Backtest Panel

- Added daily-OHLC synthetic backtesting helper.
- Added `GET /backtest/daily`.
- Dashboard now includes a Backtest panel with average signal entry compared
  against open, noon, close, and random baselines.
- The endpoint returns an explicit warning that this uses synthetic intraday
  paths from daily OHLC and is for rough validation only.

### Resume Principle

Before each major implementation phase:

1. Read `RESUME.md`.
2. Run `python3 -m unittest discover -s tests`.
3. Continue from the first unchecked item in `RESUME.md`.
4. Update both `EXECUTION_LOG.md` and `RESUME.md` before stopping.
