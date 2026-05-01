from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Set, Tuple
from zoneinfo import ZoneInfo

from .config import MarketHoursConfig


def _parse_hhmm(value: str) -> time:
    hour_raw, minute_raw = value.split(":", 1)
    return time(hour=int(hour_raw), minute=int(minute_raw))


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year, 12, 31)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _easter(year: int) -> date:
    # Anonymous Gregorian algorithm.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def us_market_holidays(year: int) -> Set[date]:
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Presidents' Day
        _easter(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))  # Juneteenth
    return holidays


def to_market_timezone(moment: datetime, config: MarketHoursConfig) -> datetime:
    tz = ZoneInfo(config.timezone)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=tz)
    return moment.astimezone(tz)


def market_open_close(day: date, config: MarketHoursConfig) -> Tuple[datetime, datetime]:
    tz = ZoneInfo(config.timezone)
    open_time = _parse_hhmm(config.start)
    close_time = _parse_hhmm(config.end)
    return (
        datetime.combine(day, open_time, tzinfo=tz),
        datetime.combine(day, close_time, tzinfo=tz),
    )


def is_market_day(day: date) -> bool:
    return day.weekday() < 5 and day not in us_market_holidays(day.year)


def is_regular_market_hours(moment: datetime, config: MarketHoursConfig = MarketHoursConfig()) -> bool:
    local = to_market_timezone(moment, config)
    if not is_market_day(local.date()):
        return False
    open_dt, close_dt = market_open_close(local.date(), config)
    return open_dt <= local < close_dt


def is_open_avoidance_window(moment: datetime, config: MarketHoursConfig = MarketHoursConfig()) -> bool:
    local = to_market_timezone(moment, config)
    if not is_market_day(local.date()):
        return False
    open_dt, _ = market_open_close(local.date(), config)
    return open_dt <= local < open_dt + timedelta(minutes=config.avoid_open_minutes)

