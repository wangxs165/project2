# Intraday Investment Monitoring & Suggestion App Plan

## 1. Purpose

This application is designed to monitor selected market instruments, analyze intraday price behavior, compare current prices against historical patterns and relevant news, and send suggestion notifications when a potentially favorable buying window is detected.

The app is intended to support recurring investment decisions by identifying relative low-price opportunities within a trading day.

## 2. Explicit Scope Boundary

This application is for **monitoring and suggestion only**.

It will **not**:

* Place trades automatically
* Connect to a broker for order execution
* Submit buy, sell, limit, market, or stop orders
* Rebalance a portfolio automatically
* Make final investment decisions on behalf of the user

All investment actions must be manually reviewed and executed by the user outside of this application.

The app may provide suggested buying prices, timing windows, confidence levels, and reasoning, but these outputs are informational signals only.

## 3. Target Instruments

Default monitored instruments:

* VOO, Vanguard S&P 500 ETF
* IAU, iShares Gold Trust

The user should be able to configure which stocks or ETFs are monitored through the web-based GUI.

Configurable watchlist examples:

* VOO
* IAU
* SPY
* IVV
* QQQ
* GLD
* Individual stocks selected by the user

The system should not hard-code the watchlist. VOO and IAU are the initial defaults only.

## 4. Core Use Case

The user has a recurring investment plan and wants to buy during relatively favorable intraday price windows instead of buying at a fixed time regardless of market conditions.

Example workflow:

1. User opens the local web-based GUI.
2. User configures the stocks or ETFs to monitor.
3. User launches the monitoring session from the GUI.
4. App monitors prices during regular U.S. trading hours only.
5. App compares current price against intraday range, VWAP, recent volatility, and historical patterns.
6. App checks relevant market/news context.
7. App identifies a potential relative low-price window.
8. App sends a Telegram notification with a suggested buying price and confidence score.
9. User views the signal and dashboard in the web GUI.
10. User manually reviews the suggestion.
11. User decides whether or not to place a trade manually.

## 5. Key Requirements

### 5.1 Real-Time or Near Real-Time Data

The app should ingest real-time or near real-time price data during regular U.S. trading days.

The app should monitor **regular trading hours only**:

* U.S. market open: 6:30 AM Pacific Time
* U.S. market close: 1:00 PM Pacific Time

Pre-market and after-hours monitoring are out of scope for the initial version.

Primary Phase I data source:

* Yahoo Finance through `yfinance`

This is used for local development and personal monitoring because it avoids
broker desktop setup. It should be treated as informational, potentially delayed
or cached, and not broker-grade market data.

Optional data source:

* Interactive Brokers / IBKR via TWS API or IB Gateway

The system should support:

* Live price updates
* Intraday bars
* Historical bars
* Market status detection
* Handling of delayed or unavailable data

### 5.2 Historical Analysis

The app should compare current prices with historical data, including:

* Previous close
* Opening price
* Intraday high and low
* VWAP
* 5-day, 20-day, 50-day, and 200-day moving averages
* Recent volatility
* Typical intraday price range
* Recent support/resistance levels
* RSI or other momentum indicators

### 5.3 News and Market Context

The app should include a news/context module to avoid generating buy suggestions purely from price movement.

Relevant context may include:

* Broad market news
* Federal Reserve and interest-rate news
* Inflation data
* Jobs data
* Treasury yield movement
* Gold-related macro news for IAU
* Geopolitical events
* Major earnings or index-moving events

News should be used as a confidence modifier rather than the sole trigger.

### 5.4 Relative Intraday Low Detection

The main goal is not to predict the absolute bottom of the day.

The goal is to identify a relatively attractive intraday buying window based on:

* Price near the lower part of the day’s range
* Price below VWAP
* Stabilizing downside momentum
* Reasonable volume support
* No major negative news override
* Favorable or neutral historical context

### 5.5 Telegram Notification Agent

When a qualified buying window is detected, the app should send a Telegram notification.

The notification should include:

* Instrument symbol
* Current price
* Suggested buying price
* Confidence level
* Reasoning summary
* Market context summary
* Reminder that the user must manually review and execute any trade

The app should not suggest tranche sizing in the notification.

Example notification:

```text
BUY WINDOW SUGGESTION

Ticker: IAU
Current price: $XX.XX
Suggested buying price: $XX.XX or below
Confidence: 76 / 100

Reasoning:
- Price is near the lower 20% of today’s range
- Price is below VWAP
- RSI is recovering from oversold territory
- News context is neutral for gold

Manual review required. This app will not place trades.
```

### 5.6 Web-Based GUI

The application should include a web-based GUI.

For Phase I, the GUI should run locally only.

The GUI should allow the user to:

* Launch and stop the monitoring session
* Configure monitored stocks and ETFs
* View current monitored instruments
* View live or near-real-time price status
* View signal history
* View Telegram notification history
* View confidence score explanations
* View app status, including data-provider status and data freshness

For Phase II, the GUI should be accessible over the internet with proper authentication and security controls.

## 6. Non-Goals

The app should not attempt to:

* Guarantee the lowest price of the day
* Predict short-term market direction with certainty
* Automatically execute trades
* Replace personal judgment or financial advice
* Trade options, margin, futures, or leveraged products in the initial version
* Generate high-frequency trading signals

## 7. Data Sources

### 7.1 yfinance / Yahoo Finance Market Data

yfinance is the default Phase I provider.

It can be used for:

* Recent intraday bars
* Latest observed bar price
* Daily historical closes
* ETF and stock monitoring prototypes

Important considerations:

* yfinance is not affiliated with or endorsed by Yahoo.
* Yahoo data is informational and may be delayed or cached.
* There is no broker-grade uptime, latency, or accuracy guarantee.
* Intraday history is limited by Yahoo/yfinance constraints.
* The app must block alerts when data timestamps become stale.

### 7.2 Optional IBKR Market Data

IBKR can be used as an optional market data source through:

* Trader Workstation, TWS
* IB Gateway
* TWS API
* Python wrapper such as `ib_insync`

Data types to request:

* Real-time market data if available
* Delayed market data if real-time data is unavailable
* Historical bars
* Intraday bars

Important consideration:

IBKR market data availability depends on account permissions, exchange subscriptions, and whether the data is real-time, delayed, or non-consolidated.

### 7.2 Optional Public or Free Data Sources

Optional backup data sources:

* Yahoo Finance, for historical reference only
* Stooq, for historical prices
* Alpha Vantage free tier, with rate limits
* Finnhub free tier, depending on availability
* NewsAPI or RSS feeds for news context

Free data should be treated carefully because it may be delayed, rate-limited, incomplete, or unsuitable for real-time intraday monitoring.

## 8. System Components

### 8.1 Data Ingestion Service

Responsible for:

* Connecting to IBKR
* Requesting market data
* Normalizing price updates
* Storing intraday and historical bars
* Detecting stale data
* Handling API reconnects

### 8.2 Historical Data Store

Stores:

* Intraday bars
* Daily bars
* Calculated indicators
* Signal history
* Notification history

Suggested database:

* PostgreSQL for general storage
* TimescaleDB if time-series volume grows
* SQLite for early local prototype

### 8.3 Signal Engine

Responsible for scoring buy-window opportunities.

Inputs:

* Current price
* Intraday range
* VWAP
* Moving averages
* RSI or momentum indicators
* Volume
* Volatility
* News context

Output:

* Buy-window detected: yes/no
* Suggested buying price
* Confidence score
* Explanation

### 8.4 News Context Analyzer

Responsible for:

* Fetching relevant market headlines
* Categorizing news by impact
* Detecting major risk events
* Adjusting confidence score
* Producing a short summary for the notification

### 8.5 Notification Agent

Responsible for:

* Formatting alert messages
* Sending messages via Telegram bot
* Enforcing alert cooldown rules
* Logging all sent notifications

### 8.6 Configuration Layer

User-configurable settings:

* Symbols to monitor
* Market hours, fixed to regular trading hours for the initial version
* Minimum confidence threshold
* Alert cooldown period
* Maximum alerts per symbol per day, default 3
* Recurring investment schedule, default daily
* Telegram chat ID
* Data source preferences
* GUI access settings

The user should be able to edit the monitored stock or ETF list from the web-based GUI.

## 9. Signal Scoring Model

Initial scoring range: 0–100.

Example scoring model:

| Factor                                | Weight |
| ------------------------------------- | -----: |
| Intraday price discount vs VWAP/range |    30% |
| Historical technical setup            |    25% |
| Volatility-adjusted dip quality       |    20% |
| News and macro context                |    15% |
| Volume and liquidity confirmation     |    10% |

Suggested confidence bands:

|  Score | Meaning                                               |
| -----: | ----------------------------------------------------- |
|   0–49 | No action suggested                                   |
|  50–64 | Weak opportunity, monitor only                        |
|  65–74 | Moderate opportunity                                  |
|  75–84 | Strong opportunity                                    |
| 85–100 | Very strong opportunity, still manual review required |

## 10. Suggested Buying Price Logic

The suggested buying price should be based on:

* Current bid/ask or last price
* VWAP
* Recent support level
* Intraday low buffer
* Volatility-adjusted expected range

Example logic:

```text
suggested_buy_price = min(
  current_price,
  vwap * 0.997,
  recent_support_price * 1.002
)
```

The exact formula should be validated through backtesting.

## 11. Risk Controls

The system should include safeguards:

* Do not send alerts during stale data conditions
* Do not send repeated alerts too frequently
* Avoid first 5–15 minutes of market open unless explicitly enabled
* Pause alerts during major market shock events
* Cap number of alerts per symbol per day
* Clearly label all alerts as suggestions only
* Log all alerts for later review
* Never place trades automatically

## 12. Backtesting Plan

Before relying on live suggestions, the system should be backtested against historical intraday data.

Backtesting should answer:

* How often did the app identify a reasonable buying window?
* Did suggested prices perform better than buying at market open?
* Did suggested prices perform better than buying at market close?
* How many false signals occurred?
* Which indicators improved or reduced signal quality?
* What confidence threshold worked best?

Baseline comparisons:

* Buy at market open
* Buy at noon
* Buy at market close
* Buy randomly during the trading day
* Buy using app-generated signals

## 13. Deployment Options

### 13.1 Phase I: Local-Only Deployment

Phase I should run entirely on the user’s local machine.

Requirements:

* IB Gateway or TWS running locally
* Python backend service running locally
* Local web-based GUI
* Internet connection for market/news data and Telegram notifications
* Telegram bot token
* Local database

Phase I access model:

* GUI available on localhost only
* No public internet exposure
* No remote access
* No cloud deployment requirement

### 13.2 Phase II: Internet-Accessible Deployment

Phase II should allow the user to access the dashboard through the internet.

Requirements:

* Secure authentication
* HTTPS
* Reverse proxy or secure tunnel
* Strong credential management
* IP allowlisting or VPN where possible
* Protection for Telegram and IBKR credentials
* Clear separation between dashboard access and trading execution

Even in Phase II, the app remains monitoring-only and must not place trades.

### 13.3 Home Server or NAS

Good for continuous monitoring after the local prototype is stable.

Requirements:

* Always-on machine
* Secure credential storage
* Restart handling
* Monitoring/logging

### 13.4 Cloud Server

Possible in Phase II or later, but more complex because IBKR Gateway may require authentication and session management.

Consider only after the local MVP is stable.

## 14. Recommended Tech Stack

MVP stack:

* Python
* `ib_insync` for IBKR API integration
* Pandas for analysis
* SQLite or PostgreSQL for storage
* APScheduler for scheduled jobs
* FastAPI for backend API
* Local web-based GUI
* React, Next.js, or simple FastAPI/Jinja UI for dashboard
* Telegram Bot API for notifications
* Docker for deployment packaging

Optional later:

* TimescaleDB
* Redis
* Celery
* Streamlit or React dashboard
* LLM-based news summarization

## 15. MVP Milestones

### Milestone 1: Local Data Connection

* Connect to IBKR through IB Gateway or TWS
* Pull live or delayed data for VOO and IAU
* Store intraday bars locally
* Confirm monitoring only during regular trading hours

### Milestone 2: Configurable Watchlist

* Add ability to configure monitored stocks and ETFs
* Store watchlist in local config or database
* Support VOO and IAU as default instruments
* Allow user to add/remove symbols from the local GUI

### Milestone 3: Basic Signal Engine

* Calculate VWAP
* Calculate intraday range percentile
* Calculate RSI
* Generate simple confidence score
* Do not suggest tranche sizing

### Milestone 4: Telegram Alert

* Create Telegram bot
* Send test alert
* Send real signal alert
* Add cooldown rules
* Limit alerts to maximum 3 times per symbol per day
* Include monitoring-only disclaimer in every alert

### Milestone 5: Local Web-Based GUI

* Launch and stop monitoring from GUI
* Configure monitored stocks and ETFs
* View current prices and data freshness
* View signal history
* View notification history
* View data-provider connection status

### Milestone 6: Historical Backtest

* Collect historical intraday data
* Compare signal performance against fixed-time daily buying
* Adjust scoring model

### Milestone 7: News Context

* Add market news ingestion
* Categorize headline impact
* Modify confidence score based on news context

### Milestone 8: Phase II Remote Access

* Add secure internet access to dashboard
* Add authentication
* Add HTTPS or secure tunnel
* Harden credential management
* Keep trading execution disabled

## 16. Example Configuration

```yaml
symbols:
  default:
    - VOO
    - IAU
  user_configurable: true

market_hours:
  timezone: America/Los_Angeles
  regular_hours_only: true
  start: "06:30"
  end: "13:00"
  include_premarket: false
  include_after_hours: false

alerts:
  min_confidence: 75
  cooldown_minutes: 30
  max_alerts_per_symbol_per_day: 3

investment_plan:
  mode: recurring_manual
  schedule: daily
  tranche_sizing_suggestions_enabled: false

execution:
  auto_trade_enabled: false
  manual_review_required: true

telegram:
  enabled: true
  bot_token_env: TELEGRAM_BOT_TOKEN
  chat_id_env: TELEGRAM_CHAT_ID

gui:
  enabled: true
  phase_1_access: local_only
  host: "127.0.0.1"
  port: 8080
  allow_symbol_configuration: true
  allow_launch_monitoring: true
  dashboard_enabled: true

phase_2_remote_access:
  enabled: false
  requires_authentication: true
  requires_https: true
  recommended_access_method: vpn_or_secure_tunnel
```

```text
Monitoring suggestion only. This app does not place trades. Manual review required.
```

## 17. Compliance and Disclaimer Text

Every alert should include a short disclaimer:

```text
Monitoring suggestion only. This app does not place trades. Manual review required.
```

Longer disclaimer for documentation:

This application provides informational monitoring and signal suggestions only. It is not financial advice, does not guarantee investment performance, and does not execute trades. The user is responsible for reviewing all information and making any investment decisions independently.

## 18. Product Decisions

The following decisions have been made for the initial version:

| Question                      | Decision                                                      |
| ----------------------------- | ------------------------------------------------------------- |
| S&P 500 proxy                 | VOO                                                           |
| Trading session               | Regular trading hours only                                    |
| Recurring investment schedule | Daily                                                         |
| Maximum alerts per day        | Maximum 3 alerts per symbol per day                           |
| Tranche sizing suggestions    | No                                                            |
| Dashboard                     | Yes, web-based GUI                                            |
| Phase I deployment            | Local-only                                                    |
| Phase II deployment           | Internet-accessible with authentication and security controls |
| Watchlist                     | User-configurable through the GUI                             |

## 19. Remaining Open Questions

* Should the local GUI use React/Next.js or a simpler FastAPI/Jinja interface for the first version?
* Should symbols be stored in a YAML config file, SQLite database, or both?
* Which free or low-cost news source should be used for Phase I?
* Should historical backtesting be available from the GUI or only through scripts in Phase I?
* Should Phase II remote access use VPN, Tailscale, Cloudflare Tunnel, or direct HTTPS hosting?
