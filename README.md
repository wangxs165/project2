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
