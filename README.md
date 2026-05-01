# Intraday Investment Monitoring App

Local-only monitoring and suggestion app for recurring investment decisions.

This app is intentionally monitoring-only:

- It does not place trades.
- It does not connect to broker order execution.
- It does not submit buy, sell, limit, market, or stop orders.
- Every alert must be manually reviewed by the user.

See `trading_monitoring.md` for the product plan and `test_plan.md` for the
robustness test strategy.

## Current Implementation Status

The current codebase contains the initial backend scaffold, core domain logic,
SQLite persistence, notification formatting, a small local dashboard, and
standard-library tests.

Because this project may be interrupted, use:

- `EXECUTION_LOG.md` for chronological execution history.
- `RESUME.md` for the latest checkpoint and next commands.

## Run Tests

```bash
python3 -m unittest discover -s tests
```

## Run Local API

Install runtime dependencies first:

```bash
python3 -m pip install -e ".[api]"
```

Then start the local app:

```bash
python3 -m backend.trading_monitor.api
```

The app binds to `127.0.0.1:8080` by default.

Useful local checks:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/status
curl -X POST http://127.0.0.1:8080/monitoring/run-once
curl -X POST http://127.0.0.1:8080/monitoring/start
curl -X POST http://127.0.0.1:8080/monitoring/stop
```

For IBKR live data, TWS or IB Gateway must be running locally and listening on
the configured API port, usually `7497` for paper TWS or `4002` for paper IB
Gateway.

## Check IBKR Market Data

Start and log in to TWS or IB Gateway first. In TWS, open Global Configuration,
then API, then Settings:

- Enable socket clients.
- Keep connections limited to localhost for this local Phase I app.
- Verify the socket port, commonly `7497` for paper TWS, `7496` for live TWS,
  `4002` for paper IB Gateway, or `4001` for live IB Gateway.

Then run:

```bash
python3 -m backend.trading_monitor.ibkr_probe --symbol VOO
```

The probe checks common local API ports, connects through the same
market-data-only adapter used by the app, and requests one market-data sample.
It does not expose order placement methods.
