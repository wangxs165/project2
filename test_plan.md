# Intraday Investment Monitoring App Test Plan

This document defines the test cases that should be implemented alongside the
application described in `trading_monitoring.md`. The goal is to make every
monitoring, scoring, notification, and dashboard behavior testable before the
app is used for live decisions.

## 1. Testing Goals

The test suite must verify that the app:

- Monitors only during regular U.S. trading hours.
- Never places, prepares, submits, or suggests broker execution orders.
- Handles stale, missing, delayed, malformed, and unavailable data safely.
- Produces deterministic and explainable signal scores.
- Sends Telegram alerts only when all risk controls pass.
- Preserves all signal and notification history.
- Keeps secrets out of logs, responses, and persisted records.
- Recovers cleanly from IBKR, network, Telegram, and database failures.

## 2. Recommended Test Stack

- Backend unit tests: `pytest`
- Async/API tests: `pytest-asyncio`, `httpx`
- Time control: `freezegun` or `time-machine`
- HTTP mocking: `respx` or `responses`
- Database tests: SQLite temporary databases per test
- Frontend unit tests: `vitest`, React Testing Library
- End-to-end GUI tests: Playwright
- Static checks: `ruff`, `mypy`, secret scanning
- Coverage target: at least 90% for signal engine, risk controls, config, and notification logic

## 3. Test Data Strategy

Use deterministic fixtures rather than live market data in automated tests.

Core fixtures:

- One normal trading day for `VOO`.
- One normal trading day for `IAU`.
- A flat-price day with low volatility.
- A sharp selloff day.
- A recovery-from-low day.
- A stale-data sequence.
- A missing-volume sequence.
- A delayed-data sequence.
- A holiday or weekend session.
- A daylight-saving-time boundary day.
- News fixtures with positive, neutral, negative, and high-risk headlines.

Live IBKR and Telegram tests should be optional manual smoke tests, gated behind
environment variables, and excluded from default CI.

## 4. Unit Test Cases

### 4.1 Configuration

Test cases:

- Loads default symbols `VOO` and `IAU` when no user watchlist exists.
- Accepts valid stock and ETF symbols.
- Rejects empty symbols, duplicate symbols, invalid characters, and overly long symbols.
- Normalizes symbols to uppercase.
- Loads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` only from environment variables.
- Rejects invalid confidence thresholds below 0 or above 100.
- Rejects invalid cooldown values and max-alert limits.
- Defaults to local-only GUI host `127.0.0.1`.
- Keeps `auto_trade_enabled` false and fails startup if it is set true.
- Does not log secrets during config validation failures.

### 4.2 Market Hours

Test cases:

- Returns open at `06:30 America/Los_Angeles` on a normal U.S. trading day.
- Returns closed before `06:30`.
- Returns closed at and after `13:00`.
- Returns closed on Saturday and Sunday.
- Returns closed on known U.S. market holidays.
- Handles daylight-saving-time changes without shifting the intended Pacific-time session.
- Blocks alerts during the first configurable 5 to 15 minutes after market open.
- Resets daily alert counters based on the configured market timezone.
- Handles system clock timezone differences correctly.

### 4.3 Data Normalization

Test cases:

- Converts IBKR tick data into a common price update model.
- Converts historical bars into a common bar model.
- Handles delayed market data with an explicit delayed flag.
- Rejects negative prices, zero prices, impossible volumes, and malformed timestamps.
- Handles missing bid, ask, last, or volume fields without crashing.
- Preserves source timestamp and ingestion timestamp.
- Detects out-of-order bars and stores them consistently.
- Deduplicates repeated bars for the same symbol and timestamp.

### 4.4 IBKR Data Service

Use mocked `ib_insync` objects.

Test cases:

- Connects successfully to TWS or IB Gateway.
- Reports disconnected status when connection fails.
- Retries connection with bounded backoff.
- Requests live market data when available.
- Falls back to delayed data when live data is unavailable.
- Handles permission errors for unsubscribed market data.
- Handles unknown or invalid symbols.
- Detects stale data after the configured freshness threshold.
- Recovers after a simulated disconnect.
- Does not call any broker order placement methods.

### 4.5 Indicator Calculations

Test cases:

- Computes VWAP correctly from price and volume bars.
- Returns unavailable VWAP when all volumes are missing or zero.
- Computes intraday high, low, and range percentile correctly.
- Computes RSI for normal data.
- Handles insufficient RSI history gracefully.
- Handles flat prices without division-by-zero errors.
- Computes moving averages for 5, 20, 50, and 200 day windows.
- Handles missing historical windows without inventing data.
- Computes volatility-adjusted dip quality deterministically.
- Produces no `NaN` or infinite values in public signal output.

### 4.6 Signal Engine

Test cases:

- Produces no signal when price is above VWAP and not near the lower daily range.
- Produces a moderate signal when price is near the lower range, below VWAP, and momentum stabilizes.
- Produces a strong signal when all price, VWAP, volatility, volume, and news factors align.
- Blocks signals when data is stale.
- Blocks signals during closed-market periods.
- Blocks signals during the configured post-open waiting window.
- Reduces confidence for negative market news.
- Reduces confidence for high-risk macro headlines.
- Does not allow news alone to create a buy suggestion.
- Explains the score with component-level reasons.
- Keeps scores inside the 0 to 100 range.
- Assigns confidence bands correctly: no action, weak, moderate, strong, very strong.

### 4.7 Suggested Buying Price

Test cases:

- Uses the minimum of current price, VWAP discount, and support-buffer price.
- Never suggests a price above current price.
- Handles missing VWAP by using remaining valid inputs.
- Handles missing support level by using remaining valid inputs.
- Rounds prices according to instrument tick size or configured precision.
- Does not include tranche sizing in any output.
- Includes manual-review language with every suggestion.

### 4.8 Risk Controls

Test cases:

- Blocks alerts when data is stale.
- Blocks alerts outside regular trading hours.
- Blocks repeat alerts inside the cooldown period.
- Allows a new alert after cooldown expires.
- Enforces maximum 3 alerts per symbol per day by default.
- Maintains independent alert counters per symbol.
- Resets alert counters on the next trading day.
- Pauses alerts during a simulated major market shock event.
- Logs blocked alert attempts with a reason.
- Does not send duplicate alerts under concurrent signal evaluation.

### 4.9 Telegram Notification Agent

Use mocked Telegram API responses.

Test cases:

- Sends a formatted test notification.
- Sends a real signal notification with ticker, current price, suggested price, confidence, reasoning, context, and disclaimer.
- Includes `Monitoring suggestion only. This app does not place trades. Manual review required.` in every alert.
- Excludes tranche sizing from every alert.
- Handles missing bot token.
- Handles missing chat ID.
- Handles Telegram API timeout.
- Handles Telegram API 4xx and 5xx responses.
- Retries only when retry policy allows.
- Logs notification success and failure.
- Does not log the bot token.

### 4.10 Database Layer

Test cases:

- Creates schema from a clean database.
- Persists watchlist entries.
- Persists intraday bars.
- Persists daily bars.
- Persists calculated indicators.
- Persists generated signals.
- Persists sent notification records.
- Enforces uniqueness where required.
- Handles duplicate insert attempts idempotently.
- Rolls back failed transactions.
- Handles database locked errors with clear service status.
- Supports app restart without losing watchlist, signals, or notification history.

### 4.11 News Context Analyzer

Test cases:

- Fetches headlines from configured source.
- Deduplicates repeated headlines.
- Classifies broad market news.
- Classifies Federal Reserve and interest-rate news.
- Classifies inflation and jobs data news.
- Classifies gold-related macro news for `IAU`.
- Classifies geopolitical risk headlines.
- Produces neutral context when no relevant news is available.
- Handles source outage or rate limit without crashing signal generation.
- Applies confidence modifiers within configured bounds.

## 5. API Integration Test Cases

Test cases:

- `GET /health` returns app status.
- `GET /status` returns IBKR connection, monitoring state, data freshness, and scheduler state.
- `GET /symbols` returns current watchlist.
- `POST /symbols` adds a valid symbol.
- `POST /symbols` rejects invalid symbols.
- `DELETE /symbols/{symbol}` removes a symbol.
- `POST /monitoring/start` starts monitoring idempotently.
- `POST /monitoring/stop` stops monitoring idempotently.
- `GET /prices` returns latest price status per symbol.
- `GET /signals` returns signal history.
- `GET /notifications` returns notification history.
- `POST /notifications/test` sends a Telegram test message.
- API responses do not include secrets.
- Concurrent start and stop requests do not corrupt monitoring state.

## 6. Frontend Test Cases

### 6.1 Component Tests

Test cases:

- Watchlist renders default symbols.
- Add-symbol form validates input.
- Remove-symbol action updates visible watchlist.
- Monitoring button reflects stopped, starting, running, stopping, and error states.
- Price table renders stale-data warnings.
- Signal history renders confidence score and explanation.
- Notification history renders sent and failed statuses.
- IBKR status indicator renders connected, disconnected, delayed, and stale states.
- Empty states render without layout breakage.

### 6.2 End-to-End Tests

Use Playwright against the local app with mocked backend or seeded test database.

Test cases:

- User opens dashboard and sees local monitoring status.
- User adds `SPY` and it appears in the watchlist.
- User removes a symbol and it disappears from the watchlist.
- User starts monitoring and sees running status.
- User stops monitoring and sees stopped status.
- User sees stale data warning when backend marks a symbol stale.
- User sees a generated signal in history.
- User sees Telegram notification history after an alert.
- User cannot enable automatic trading because no such control exists.
- Dashboard works at desktop and mobile viewport sizes without overlapping text.

## 7. Backtesting Test Cases

Test cases:

- Runs a backtest from deterministic intraday fixture data.
- Compares app signals against buy-at-open baseline.
- Compares app signals against buy-at-noon baseline.
- Compares app signals against buy-at-close baseline.
- Compares app signals against random-time baseline with seeded randomness.
- Prevents lookahead bias by using only data available at each simulated timestamp.
- Produces reproducible results for the same fixture and seed.
- Handles days with no generated signals.
- Handles missing bars in historical data.
- Stores backtest summary metrics.
- Reports false signal count, opportunity count, and threshold sensitivity.

## 8. Security and Compliance Test Cases

Test cases:

- App binds to `127.0.0.1` by default.
- Phase I does not expose public remote access.
- Secrets are never returned by API endpoints.
- Secrets are never written to notification history.
- Logs redact Telegram token and other credentials.
- CORS defaults are restrictive.
- No route or service exposes broker order execution.
- Static test fails if code imports or calls IBKR order placement APIs.
- Every alert includes monitoring-only disclaimer.
- Documentation states the app is not financial advice and does not execute trades.

## 9. Resilience Test Cases

Test cases:

- IBKR disconnect during monitoring does not crash the app.
- IBKR reconnect resumes data updates.
- Telegram outage does not block future signal evaluation.
- News source outage degrades to neutral context.
- Database write failure marks service unhealthy and preserves process stability.
- Scheduler job exception is logged and does not kill the scheduler.
- App restart resumes persisted watchlist.
- App restart does not resend old alerts.
- Concurrent signal evaluations for the same symbol do not create duplicate notifications.
- Large watchlist remains within acceptable polling and UI latency limits.

## 10. Manual Smoke Tests

These tests require real local services and should not run in CI by default.

Test cases:

- Connect to local TWS or IB Gateway.
- Confirm delayed or live price data for `VOO`.
- Confirm delayed or live price data for `IAU`.
- Send a Telegram test alert to the configured chat.
- Run the app through one full regular-hours monitoring session.
- Confirm no broker order prompt, order ticket, or execution action occurs.
- Confirm dashboard is reachable only on localhost.

## 11. Milestone Test Gates

Milestone 1, local data connection:

- Market-hours tests pass.
- IBKR mock connection tests pass.
- Data normalization tests pass.
- Stale-data tests pass.

Milestone 2, configurable watchlist:

- Config tests pass.
- Watchlist database tests pass.
- Symbol API tests pass.
- Watchlist frontend tests pass.

Milestone 3, signal engine:

- Indicator tests pass.
- Signal engine tests pass.
- Suggested price tests pass.
- Risk-control tests pass.

Milestone 4, Telegram alerts:

- Notification formatting tests pass.
- Telegram error-handling tests pass.
- Cooldown and max-alert tests pass.
- Disclaimer tests pass.

Milestone 5, local web GUI:

- API integration tests pass.
- Frontend component tests pass.
- Playwright dashboard flows pass.
- Responsive layout checks pass.

Milestone 6, backtesting:

- Backtest fixture tests pass.
- Baseline comparison tests pass.
- Lookahead-bias prevention tests pass.

Milestone 7, news context:

- News ingestion tests pass.
- News classification tests pass.
- Confidence modifier tests pass.
- Source outage tests pass.

Milestone 8, remote access:

- Authentication tests pass.
- HTTPS or tunnel configuration tests pass.
- Credential hardening tests pass.
- Local monitoring-only guarantees still pass.

## 12. Definition of Done

A feature is done only when:

- Unit tests cover normal, edge, and failure paths.
- Integration tests verify API and persistence behavior.
- Risk controls have explicit regression tests.
- No test requires live IBKR, Telegram, or news APIs unless marked manual.
- Secrets are redacted in logs and responses.
- All alerts include the monitoring-only disclaimer.
- No code path can place or submit trades.
- Tests are deterministic and can run repeatedly on a clean machine.
