import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.trading_monitor.config import MarketHoursConfig
from backend.trading_monitor.market_hours import (
    is_market_day,
    is_open_avoidance_window,
    is_regular_market_hours,
    us_market_holidays,
)


PACIFIC = ZoneInfo("America/Los_Angeles")


class MarketHoursTests(unittest.TestCase):
    def test_market_is_open_at_regular_open(self):
        moment = datetime(2026, 5, 1, 6, 30, tzinfo=PACIFIC)

        self.assertTrue(is_regular_market_hours(moment))

    def test_market_is_closed_before_open_and_at_close(self):
        before_open = datetime(2026, 5, 1, 6, 29, tzinfo=PACIFIC)
        at_close = datetime(2026, 5, 1, 13, 0, tzinfo=PACIFIC)

        self.assertFalse(is_regular_market_hours(before_open))
        self.assertFalse(is_regular_market_hours(at_close))

    def test_weekends_are_closed(self):
        saturday = datetime(2026, 5, 2, 9, 0, tzinfo=PACIFIC)

        self.assertFalse(is_regular_market_hours(saturday))
        self.assertFalse(is_market_day(saturday.date()))

    def test_us_market_holidays_are_closed(self):
        independence_day_observed = datetime(2026, 7, 3, 9, 0, tzinfo=PACIFIC)
        thanksgiving = datetime(2026, 11, 26, 9, 0, tzinfo=PACIFIC)

        self.assertIn(independence_day_observed.date(), us_market_holidays(2026))
        self.assertFalse(is_regular_market_hours(independence_day_observed))
        self.assertFalse(is_regular_market_hours(thanksgiving))

    def test_daylight_saving_time_does_not_shift_pacific_session(self):
        after_dst_start = datetime(2026, 3, 9, 6, 30, tzinfo=PACIFIC)

        self.assertTrue(is_regular_market_hours(after_dst_start))

    def test_open_avoidance_window(self):
        config = MarketHoursConfig(avoid_open_minutes=15)
        inside = datetime(2026, 5, 1, 6, 40, tzinfo=PACIFIC)
        outside = datetime(2026, 5, 1, 6, 46, tzinfo=PACIFIC)

        self.assertTrue(is_open_avoidance_window(inside, config))
        self.assertFalse(is_open_avoidance_window(outside, config))

    def test_naive_datetime_is_assumed_to_be_market_timezone(self):
        naive = datetime(2026, 5, 1, 6, 30)

        self.assertTrue(is_regular_market_hours(naive))


if __name__ == "__main__":
    unittest.main()

