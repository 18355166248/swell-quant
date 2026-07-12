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


def _member(snap_day, symbol, index="000300", inclusion=(2016, 1, 1)):
    return UniverseMemberRecord(
        snapshot_date=date(2026, 1, snap_day),
        index_code=index,
        symbol=symbol,
        inclusion_date=date(*inclusion),
        source="test",
    )


# ---- store: snapshot selection ----


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


# ---- store: inclusion-date filtering (survivorship mitigation) ----


def test_approximate_mode_excludes_not_yet_included(store):
    # 快照 2026-01-01：a 于 2015 纳入、b 于 2020 纳入。
    store.write_universe_members(
        [
            _member(1, "a_early", inclusion=(2015, 1, 1)),
            _member(1, "b_late", inclusion=(2020, 6, 1)),
        ]
    )
    # 严格 PIT：2018 < 唯一快照 2026 → 无可用快照 → 空。
    assert store.get_universe("000300", date(2018, 1, 1)) == []
    # 近似模式：用最近快照近似历史，2018 时 b 尚未纳入被排除 → 只剩 a。
    assert store.get_universe("000300", date(2018, 1, 1), approximate_from_latest=True) == [
        "a_early"
    ]
    # 2021 时两者都已纳入。
    assert store.get_universe("000300", date(2021, 1, 1), approximate_from_latest=True) == [
        "a_early",
        "b_late",
    ]


def test_approximate_mode_uses_future_snapshot(store):
    store.write_universe_members([_member(1, "600519", inclusion=(2010, 1, 1))])
    assert store.get_universe("000300", date(2020, 1, 1)) == []  # 严格：无 <= as_of 的快照
    assert store.get_universe("000300", date(2020, 1, 1), approximate_from_latest=True) == [
        "600519"
    ]


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


def _row(code, inclusion="2020-01-01", name="x"):
    return {"品种代码": code, "品种名称": name, "纳入日期": inclusion}


def test_fetch_constituents_returns_code_and_inclusion():
    provider = FakeProvider(
        [
            _row("600519", "2005-04-08"),
            _row("1", "2021-12-13"),  # 补零到 6 位
            _row("600519", "2005-04-08"),  # 去重
        ]
    )
    members = fetch_index_constituents("000300", provider)
    assert members == [("600519", date(2005, 4, 8)), ("000001", date(2021, 12, 13))]
    assert provider.calls == ["000300"]


def test_fetch_constituents_empty_raises():
    with pytest.raises(UniverseSourceError):
        fetch_index_constituents("000300", FakeProvider([]))


def test_snapshot_writes_members_with_inclusion(store):
    provider = FakeProvider([_row("600519", "2005-04-08"), _row("000001", "2021-12-13")])
    n = snapshot_index_universe(store, "000300", provider, snapshot_date=date(2026, 1, 1))
    assert n == 2
    # 2010 as_of（近似模式）：只有 2005 纳入的 600519 可见。
    assert store.get_universe("000300", date(2010, 1, 1), approximate_from_latest=True) == [
        "600519"
    ]
    assert store.get_universe("000300", date(2026, 1, 1)) == ["000001", "600519"]
