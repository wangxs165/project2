# Resume Checkpoint

Last updated: 2026-05-02

## Current Goal

Build the Phase I local-only MVP from `trading_monitoring.md` with robust tests.

## Current State

- Planning document exists: `trading_monitoring.md`
- Comprehensive test plan exists: `test_plan.md`
- Initial Phase I backend scaffold is implemented.
- Core business logic is implemented for:
  - config safety
  - market-hours detection
  - data validation
  - indicator calculations
  - signal scoring
  - suggested buying price calculation
  - alert cooldown and daily cap gates
  - Telegram alert formatting
  - SQLite persistence
  - simple news context classification
  - IBKR market-data-only adapter shell
  - yfinance/Yahoo Finance market-data provider
- Provider-driven monitoring cycle service is implemented.
- Deterministic intraday backtesting runner is implemented.
- API start/stop is wired to a real background monitoring runner.
- `POST /monitoring/run-once` is available.
- Local FastAPI API scaffold exists.
- Local static dashboard scaffold exists at `backend/trading_monitor/static/index.html`.
- `.venv` exists and has FastAPI, uvicorn, pytest, httpx, and ib_insync installed.
- No live yfinance, IBKR, Telegram, or internet-dependent tests should be required for
  default verification.

## Verification Command

```bash
python3 -m unittest discover -s tests
```

## Next Work Items

- [x] Finish backend core modules.
- [x] Add standard-library automated tests.
- [x] Run the test suite.
- [x] Add local API/dashboard scaffold.
- [x] Record passing/failing tests and next steps here.
- [x] Install optional API and yfinance dependencies.
- [x] Run FastAPI integration tests after dependency installation.
- [x] Add one-command local launcher for API/dashboard:
  `./scripts/start_app.sh`
- [x] Implement provider-driven monitoring cycle.
- [x] Implement deterministic historical backtesting runner.
- [x] Wire monitoring service into API start/stop lifecycle.
- [x] Test yfinance provider against live Yahoo Finance responses.
- [x] Skip real IBKR smoke testing for now; yfinance is the active Phase I provider.
- [x] Add historical-bar ingestion storage APIs beyond the current provider calls.
- [x] Configure Telegram environment and run live Telegram smoke test.
- [x] Add live/manual Phase I smoke-test checklist results.

## Known Environment Notes

- Python version observed: 3.9.6 for system Python; `.venv` uses the project
  runtime with FastAPI, uvicorn, pytest, httpx, yfinance, and ib_insync.
- The directory is a git repository with GitHub remote
  `git@github.com:wangxs165/project2.git`.
- Keep the app local-only by default: `127.0.0.1:8080`.
- Default test result on 2026-05-01:
  `59 tests OK, 1 skipped because FastAPI is not installed`.
- Venv test result on 2026-05-01:
  `.venv/bin/python -m pytest -q` -> `58 passed, 1 skipped`.
- Syntax sweep command:
  `PYTHONPYCACHEPREFIX=/tmp/project2_pycache python3 -m compileall backend tests`
- Port check on 2026-05-01:
  `8080` is not listening; `5000` and `7000` are used by `ControlCe`.
- Local API startup reached app initialization but sandbox binding to
  `127.0.0.1:8080` failed with `operation not permitted`.
- After user granted operation permission, local API started successfully on:
  `http://127.0.0.1:8080`
- Verified endpoints:
  - `GET /health`
  - `GET /symbols`
  - `GET /status`
- Updated endpoint verification:
  - `POST /monitoring/run-once`
  - `POST /monitoring/start`
  - `POST /monitoring/stop`
- Current venv test result:
  `.venv/bin/python -m pytest -q` -> `74 passed, 1 skipped`.
- Current unittest result:
  `python3 -m unittest discover -s tests` -> `75 tests OK, 1 skipped`.
- `ib_insync` is installed: `0.9.86`.
- No local listener was detected on common IBKR ports `7496`, `7497`, `4001`,
  or `4002`. Start TWS or IB Gateway with API access enabled before live IBKR
  testing.
- Added IBKR connectivity probe:
  `python3 -m backend.trading_monitor.ibkr_probe --symbol VOO`
- Default provider changed to yfinance on 2026-05-01 so development can proceed
  without IB Gateway. IBKR is optional via `DATA_PROVIDER=ibkr`.
- yfinance is installed and imports successfully in `.venv`.
- Local API verified on `http://127.0.0.1:8080`.
- Direct yfinance provider smoke test returned IAU and VOO prices from the
  2026-05-01 market close. Monitoring `run-once` correctly skipped provider
  fetch outside regular market hours.
- Added manual price refresh endpoint:
  `POST /prices/refresh`. It fetches provider prices outside market hours but
  does not generate signals or alerts.
- Added recent daily history endpoint:
  `GET /history/open-close`. The dashboard shows the latest 5 trading days'
  open and close values in a table.
- Dashboard now includes a Run Analysis button and readable signal cards with
  reasons, suggested price, alert status, and score breakdown.
- Added `POST /monitoring/run-demo` plus a Demo Analysis dashboard button for
  closed-market UI testing with deterministic sample data and no real alerts.
- Signal scoring now includes momentum recovery, lower-low and aggressive
  selling-volume blockers, and volatility-adjusted dip quality.
- Added `GET /backtest/daily` and a dashboard Backtest panel using synthetic
  daily-OHLC intraday paths for rough validation against open/noon/close/random
  baselines.
- Added local launcher script:
  `./scripts/start_app.sh`. It starts the API if needed and opens Chrome to
  `http://127.0.0.1:8080`.
- Added historical bar storage/read APIs:
  - `POST /history/refresh`
  - `GET /history/bars/{symbol}`
- Live yfinance smoke test on 2026-05-02 returned VOO and IAU latest bars from
  the 2026-05-01 market close, with 390 intraday bars and 5 daily bars for each.
- Telegram live smoke test succeeded on 2026-05-02 after correcting
  `TELEGRAM_CHAT_ID`; `POST /notifications/test` returned
  `{"status":"sent","error":null}`.
- Dashboard now includes stored-history controls and a stored-intraday backtest
  action.
- Backtest output now includes signal rate, false-signal count/rate, and daily
  OHLC threshold sensitivity.
- Dashboard now includes hover help for score components, backtest terms, and
  history/backtest actions so non-specialist users can understand the terminology.
- Dashboard help now uses an in-app tooltip that opens on hover, focus, or click
  instead of relying on browser-native title text.
- Live market-hours test on 2026-05-04 succeeded with yfinance:
  - direct VOO and IAU bars were about 60 seconds old
  - `POST /monitoring/run-once` returned `market_open: true`
  - active watchlist symbols were evaluated with no provider errors
  - no Telegram alert was sent because live confidence scores were below the
    configured threshold
- Fixed latest-price selection to use the newest inserted price row per symbol,
  avoiding stale dashboard prices when UTC and Pacific timestamp strings are
  mixed in SQLite.
- Latest Prices and Signals now only return active watchlist symbols, so old
  persisted data for removed symbols is hidden from the dashboard.
- The Signals dashboard section now spans the full width and uses more prominent
  cards for easier review.

## Manual Smoke-Test Checklist

- [x] yfinance live data returns VOO and IAU latest observed bars.
- [x] Telegram test notification sends successfully.
- [x] Local API binds to `127.0.0.1:8080`.
- [x] `GET /health` reports `monitoring_only: true` and
  `auto_trade_enabled: false`.
- [x] `GET /status` reports `data_provider: yfinance`.
- [x] `POST /monitoring/run-once` safely skips signal generation while the
  market is closed.
- [x] Static scan found no broker order-placement code paths.
- [x] IBKR live smoke test intentionally skipped for Phase I because yfinance
  is the active provider.
