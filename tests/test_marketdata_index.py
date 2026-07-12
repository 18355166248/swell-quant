from datetime import date

import pytest

from swell_quant.marketdata.records import IndexBarRecord
from swell_quant.marketdata.source_index import (
    IndexSourceError,
    build_index_bars,
    fetch_index_bars_sina,
)
from swell_quant.marketdata.store import MarketStore


def _ix(day, close, code="sh000300"):
    return IndexBarRecord(index_code=code, date=date(2026, 1, day), close=close, source="test")


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


# ---- store ----


def test_write_and_forward_read(store):
    store.write_index_bars([_ix(d, 100.0 + d) for d in (1, 2, 3, 4, 5)])
    bars = store.get_index_bar_forward("sh000300", start=date(2026, 1, 2), horizon=2)
    assert [(b.date.day, b.close) for b in bars] == [(2, 102.0), (3, 103.0), (4, 104.0)]


def test_index_write_idempotent(store):
    store.write_index_bars([_ix(1, 100.0)])
    store.write_index_bars([_ix(1, 100.0)])
    n = store._connection.execute("SELECT count(*) FROM index_bar").fetchone()[0]
    assert n == 1


def test_forward_insufficient_returns_short(store):
    store.write_index_bars([_ix(1, 100.0), _ix(2, 101.0)])
    bars = store.get_index_bar_forward("sh000300", start=date(2026, 1, 1), horizon=5)
    assert len(bars) == 2  # 只有 2 根


# ---- source ----


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        return self.rows


class FakeSina:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def stock_zh_index_daily(self, symbol):
        self.calls.append(symbol)
        return FakeFrame(self.rows)


def test_build_index_bars_sorts_by_date():
    rows = [{"date": "2026-01-03", "close": 103.0}, {"date": "2026-01-01", "close": 101.0}]
    bars = build_index_bars("sh000300", rows, source="sina")
    assert [b.date.day for b in bars] == [1, 3]


def test_fetch_index_bars_sina():
    fake = FakeSina([{"date": "2026-01-01", "close": 100.0}])
    bars = fetch_index_bars_sina("sh000300", fake)
    assert fake.calls == ["sh000300"]
    assert bars[0].close == 100.0


def test_fetch_index_empty_raises():
    with pytest.raises(IndexSourceError):
        fetch_index_bars_sina("sh000300", FakeSina([]))
