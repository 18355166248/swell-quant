from datetime import date

import pytest

from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore


def _bar(symbol, day, close, adj_factor=1.0, source="test"):
    return BarRecord(
        symbol=symbol,
        date=date(2026, 1, day),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100,
        amount=close * 100,
        adj_factor=adj_factor,
        source=source,
    )


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_write_then_read_roundtrip(store):
    store.write_bars([_bar("600519", 1, 10.0), _bar("600519", 2, 11.0)])
    bars = store.get_bars(["600519"], as_of=date(2026, 1, 31), lookback=10)
    assert [(b.date.day, b.close) for b in bars] == [(1, 10.0), (2, 11.0)]


def test_write_is_idempotent(store):
    batch = [_bar("600519", 1, 10.0), _bar("600519", 2, 11.0)]
    store.write_bars(batch)
    store.write_bars(batch)  # 重复灌同一批
    bars = store.get_bars(["600519"], as_of=date(2026, 1, 31), lookback=10)
    assert len(bars) == 2  # 行数不增


def test_upsert_updates_existing_value(store):
    store.write_bars([_bar("600519", 1, 10.0, adj_factor=1.0)])
    store.write_bars([_bar("600519", 1, 10.0, adj_factor=1.25)])  # 同主键，新因子
    [bar] = store.get_bars(["600519"], as_of=date(2026, 1, 31), lookback=10)
    assert bar.adj_factor == 1.25


def test_as_of_excludes_future(store):
    store.write_bars([_bar("600519", d, 10.0 + d) for d in (1, 2, 3, 4, 5)])
    bars = store.get_bars(["600519"], as_of=date(2026, 1, 3), lookback=10)
    assert [b.date.day for b in bars] == [1, 2, 3]  # d4/d5 是 as_of 之后，不可见


def test_lookback_takes_most_recent(store):
    store.write_bars([_bar("600519", d, 10.0 + d) for d in (1, 2, 3, 4, 5)])
    bars = store.get_bars(["600519"], as_of=date(2026, 1, 5), lookback=2)
    assert [b.date.day for b in bars] == [4, 5]  # 最近 2 条，升序返回


def test_lookback_is_per_symbol(store):
    store.write_bars(
        [_bar("600519", d, 10.0) for d in (1, 2, 3)] + [_bar("000001", d, 20.0) for d in (1, 2, 3)]
    )
    bars = store.get_bars(["600519", "000001"], as_of=date(2026, 1, 31), lookback=2)
    by_symbol = {}
    for b in bars:
        by_symbol.setdefault(b.symbol, []).append(b.date.day)
    assert by_symbol == {"600519": [2, 3], "000001": [2, 3]}  # 每票各取最近 2 条


def test_hfq_view_derives_adjusted_price(store):
    # raw 收盘 10，因子 1.25 → 后复权收盘 12.5；raw 表仍是 10。
    store.write_bars([_bar("600519", 1, 10.0, adj_factor=1.25)])
    [raw] = store.get_bars(["600519"], as_of=date(2026, 1, 31), lookback=10)
    [hfq] = store.get_bars_hfq(["600519"], as_of=date(2026, 1, 31), lookback=10)
    assert raw.close == 10.0
    assert hfq.close == pytest.approx(12.5)
    assert hfq.open == pytest.approx(12.5)
    assert hfq.adj_factor == 1.25  # 视图保留因子信息


def test_get_max_date(store):
    assert store.get_max_date("600519") is None
    store.write_bars([_bar("600519", d, 10.0) for d in (1, 2, 3)])
    assert store.get_max_date("600519") == date(2026, 1, 3)


def test_empty_inputs(store):
    store.write_bars([])  # 不报错
    assert store.get_bars([], as_of=date(2026, 1, 1), lookback=10) == []
    assert store.get_bars(["600519"], as_of=date(2026, 1, 1), lookback=0) == []


def test_persists_to_file(tmp_path):
    db = tmp_path / "marketdata.duckdb"
    with MarketStore(db) as s:
        s.write_bars([_bar("600519", 1, 10.0)])
    # 重开同一文件，数据还在（schema 用 IF NOT EXISTS，不覆盖）。
    with MarketStore(db) as s:
        bars = s.get_bars(["600519"], as_of=date(2026, 1, 31), lookback=10)
    assert [b.date.day for b in bars] == [1]
