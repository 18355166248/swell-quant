from datetime import date

import pytest

from swell_quant.marketdata.records import UniverseMemberRecord
from swell_quant.marketdata.source_universe import (
    UniverseSourceError,
    fetch_index_constituents,
    snapshot_index_universe,
)
from swell_quant.marketdata.store import MarketStore


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def _member(snap_day, symbol, index="000300"):
    return UniverseMemberRecord(
        snapshot_date=date(2026, 1, snap_day), index_code=index, symbol=symbol, source="test"
    )


# ---- store ----


def test_get_universe_uses_latest_snapshot_on_or_before(store):
    store.write_universe_members([_member(1, "600000"), _member(1, "600519")])
    store.write_universe_members([_member(10, "600519"), _member(10, "000001")])  # 成分变了
    # as_of 1/5 → 用 1/1 快照。
    assert store.get_universe("000300", date(2026, 1, 5)) == ["600000", "600519"]
    # as_of 1/15 → 用 1/10 快照（600000 已剔除，000001 纳入）。
    assert store.get_universe("000300", date(2026, 1, 15)) == ["000001", "600519"]


def test_get_universe_before_any_snapshot_empty(store):
    store.write_universe_members([_member(10, "600519")])
    assert store.get_universe("000300", date(2026, 1, 1)) == []


def test_universe_idempotent(store):
    store.write_universe_members([_member(1, "600519")])
    store.write_universe_members([_member(1, "600519")])
    n = store._connection.execute("SELECT count(*) FROM universe_member").fetchone()[0]
    assert n == 1


def test_universe_isolated_by_index(store):
    store.write_universe_members(
        [_member(1, "600519", index="000300"), _member(1, "300750", index="000905")]
    )
    assert store.get_universe("000300", date(2026, 1, 5)) == ["600519"]
    assert store.get_universe("000905", date(2026, 1, 5)) == ["300750"]


# ---- source ----


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        return self.rows


class FakeProvider:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def index_stock_cons(self, symbol):
        self.calls.append(symbol)
        return FakeFrame(self.rows)


def test_fetch_constituents_normalizes_codes():
    provider = FakeProvider(
        [
            {"品种代码": "600519", "品种名称": "贵州茅台"},
            {"品种代码": "1", "品种名称": "怪数据"},  # 补零到 6 位
            {"品种代码": "600519", "品种名称": "重复"},  # 去重
        ]
    )
    codes = fetch_index_constituents("000300", provider)
    assert codes == ["600519", "000001"]
    assert provider.calls == ["000300"]


def test_fetch_constituents_empty_raises():
    with pytest.raises(UniverseSourceError):
        fetch_index_constituents("000300", FakeProvider([]))


def test_snapshot_writes_members(store):
    provider = FakeProvider([{"品种代码": "600519"}, {"品种代码": "000001"}])
    n = snapshot_index_universe(store, "000300", provider, snapshot_date=date(2026, 1, 1))
    assert n == 2
    assert store.get_universe("000300", date(2026, 1, 1)) == ["000001", "600519"]
