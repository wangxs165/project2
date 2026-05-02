# Resume Checkpoint

Last updated: 2026-05-01

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
- [ ] Install optional API and yfinance dependencies when internet access is available:
  `python3 -m pip install -e ".[api,yfinance]"`
- [ ] Run FastAPI integration tests after dependency installation:
  `python3 -m unittest tests.test_api_optional`
- [x] Add one-command local launcher for API/dashboard:
  `./scripts/start_app.sh`
- [x] Implement provider-driven monitoring cycle.
- [x] Implement deterministic historical backtesting runner.
- [x] Wire monitoring service into API start/stop lifecycle.
- [ ] Test yfinance provider against live Yahoo Finance responses.
- [ ] Keep real IBKR market-data provider optional for local TWS or IB Gateway.
- [x] Add historical-bar ingestion storage APIs beyond the current provider calls.
- [ ] Add live/manual smoke-test checklist results for IBKR and Telegram.

## Known Environment Notes

- Python version observed: 3.9.6
- `pytest` is not installed.
- The directory is not currently a git repository.
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
  `.venv/bin/python -m pytest -q` -> `66 passed, 1 skipped`.
- Current unittest result:
  `python3 -m unittest discover -s tests` -> `67 tests OK, 1 skipped`.
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
