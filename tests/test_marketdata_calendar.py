from datetime import date

import pytest

from swell_quant.marketdata.source_calendar import fetch_trade_calendar
from swell_quant.marketdata.store import MarketStore


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


class FakeCalendarProvider:
    def __init__(self, trade_dates):
        self.trade_dates = trade_dates

    def tool_trade_date_hist_sina(self):
        return FakeFrame([{"trade_date": d} for d in self.trade_dates])


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_fetch_trade_calendar_sorts_and_filters():
    provider = FakeCalendarProvider(["2024-06-28", "2024-06-27", "2024-07-01", "2024-07-05"])
    days = fetch_trade_calendar(provider, start=date(2024, 6, 27), end=date(2024, 7, 1))
    assert days == [date(2024, 6, 27), date(2024, 6, 28), date(2024, 7, 1)]


def test_calendar_store_roundtrip_and_queries(store):
    days = [date(2024, 6, 27), date(2024, 6, 28), date(2024, 7, 1)]
    store.write_trade_calendar(days)
    assert store.has_trade_calendar()
    assert store.is_trading_day(date(2024, 6, 28)) is True
    assert store.is_trading_day(date(2024, 6, 29)) is False  # 周末不在表中
    # 6/29、6/30 是周末 → <= 6/30 的最近交易日是 6/28。
    assert store.latest_trading_day(date(2024, 6, 30)) == date(2024, 6, 28)
    assert store.latest_trading_day(date(2024, 7, 1)) == date(2024, 7, 1)


def test_write_calendar_is_idempotent(store):
    days = [date(2024, 6, 27), date(2024, 6, 28)]
    store.write_trade_calendar(days)
    store.write_trade_calendar(days)
    n = store._connection.execute("SELECT count(*) FROM trade_calendar").fetchone()[0]
    assert n == 2


def test_latest_trading_day_empty_is_none(store):
    assert store.has_trade_calendar() is False
    assert store.latest_trading_day(date(2024, 6, 30)) is None
