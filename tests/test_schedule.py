import datetime as dt

from briarpipe.schedule import is_due

NOW = dt.datetime(2026, 6, 10, 8, 0)


def test_first_time_is_always_due():
    assert is_due("weekly", None, NOW) is True
    assert is_due("daily", "", NOW) is True


def test_daily():
    assert is_due("daily", "2026-06-09", NOW) is True   # 1 day
    assert is_due("daily", "2026-06-10", NOW) is False  # same day


def test_weekly():
    assert is_due("weekly", "2026-06-03", NOW) is True   # 7 days
    assert is_due("weekly", "2026-06-05", NOW) is False  # 5 days


def test_monthly():
    assert is_due("monthly", "2026-05-10", NOW) is True    # 31 days
    assert is_due("monthly", "2026-05-20", NOW) is False   # 21 days


def test_unreadable_date_publishes_rather_than_stalling():
    assert is_due("weekly", "garbage", NOW) is True
