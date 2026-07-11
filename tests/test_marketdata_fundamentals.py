from datetime import date

import pytest

from swell_quant.marketdata.records import FundamentalRecord
from swell_quant.marketdata.store import MarketStore


def _fund(symbol, event, knowledge, item, value, source="test"):
    return FundamentalRecord(
        symbol=symbol,
        event_date=date(*event),
        knowledge_date=date(*knowledge),
        item=item,
        value=value,
        source=source,
    )


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_write_then_read_roundtrip(store):
    store.write_fundamentals(
        [_fund("600519", (2025, 3, 31), (2025, 4, 20), "net_profit", 100.0)]
    )
    [rec] = store.get_fundamentals(["600519"], as_of=date(2025, 12, 31))
    assert rec.item == "net_profit"
    assert rec.value == 100.0
    assert rec.event_date == date(2025, 3, 31)
    assert rec.knowledge_date == date(2025, 4, 20)


def test_pit_hides_not_yet_announced_event(store):
    # Q1 于 4/20 公告；Q2 于 7/18 公告。
    store.write_fundamentals(
        [
            _fund("600519", (2025, 3, 31), (2025, 4, 20), "net_profit", 100.0),
            _fund("600519", (2025, 6, 30), (2025, 7, 18), "net_profit", 130.0),
        ]
    )
    # 7/1 站点：只知道 Q1，Q2 尚未公告 → 返回 Q1。
    [early] = store.get_fundamentals(["600519"], as_of=date(2025, 7, 1))
    assert early.event_date == date(2025, 3, 31)
    assert early.value == 100.0
    # 8/1 站点：Q2 已公告 → 返回最新报告期 Q2。
    [late] = store.get_fundamentals(["600519"], as_of=date(2025, 8, 1))
    assert late.event_date == date(2025, 6, 30)
    assert late.value == 130.0


def test_pit_respects_restatement(store):
    # 同一报告期 Q1：原始 4/20 报 100，8/15 修正为 110（两行都保留）。
    store.write_fundamentals(
        [
            _fund("600519", (2025, 3, 31), (2025, 4, 20), "net_profit", 100.0),
            _fund("600519", (2025, 3, 31), (2025, 8, 15), "net_profit", 110.0),
        ]
    )
    # 修正前站点：只看得到原始值。
    [before] = store.get_fundamentals(["600519"], as_of=date(2025, 5, 1))
    assert before.value == 100.0
    # 修正后站点：看得到修正值（不泄露给过去）。
    [after] = store.get_fundamentals(["600519"], as_of=date(2025, 9, 1))
    assert after.value == 110.0


def test_restatement_history_is_preserved(store):
    # PK 含 knowledge_date：原始与修正各占一行，不互相覆盖。
    store.write_fundamentals(
        [
            _fund("600519", (2025, 3, 31), (2025, 4, 20), "net_profit", 100.0),
            _fund("600519", (2025, 3, 31), (2025, 8, 15), "net_profit", 110.0),
        ]
    )
    rows = store._connection.execute(
        "SELECT count(*) FROM stock_fundamental WHERE event_date = ?", [date(2025, 3, 31)]
    ).fetchone()[0]
    assert rows == 2


def test_write_fundamentals_is_idempotent(store):
    batch = [_fund("600519", (2025, 3, 31), (2025, 4, 20), "net_profit", 100.0)]
    store.write_fundamentals(batch)
    store.write_fundamentals(batch)  # 同主键
    rows = store._connection.execute("SELECT count(*) FROM stock_fundamental").fetchone()[0]
    assert rows == 1


def test_multiple_items_and_symbols(store):
    store.write_fundamentals(
        [
            _fund("600519", (2025, 3, 31), (2025, 4, 20), "net_profit", 100.0),
            _fund("600519", (2025, 3, 31), (2025, 4, 20), "revenue", 500.0),
            _fund("000001", (2025, 3, 31), (2025, 4, 25), "net_profit", 80.0),
        ]
    )
    recs = store.get_fundamentals(["600519", "000001"], as_of=date(2025, 12, 31))
    got = {(r.symbol, r.item): r.value for r in recs}
    assert got == {
        ("600519", "net_profit"): 100.0,
        ("600519", "revenue"): 500.0,
        ("000001", "net_profit"): 80.0,
    }


def test_empty_symbols_returns_empty(store):
    assert store.get_fundamentals([], as_of=date(2025, 1, 1)) == []
