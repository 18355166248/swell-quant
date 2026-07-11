from datetime import date

import pytest

from swell_quant.marketdata.records import ValuationRecord
from swell_quant.marketdata.source_valuation import (
    ValuationSourceError,
    build_valuation_records,
    fetch_valuations_baidu,
)
from swell_quant.marketdata.store import MarketStore


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def _val(symbol, day, item, value, source="baidu"):
    return ValuationRecord(symbol=symbol, date=date(2026, 1, day), item=item, value=value, source=source)


# ---- store ----

def test_valuation_roundtrip(store):
    store.write_valuations([_val("600519", 1, "pe_ttm", 18.2), _val("600519", 1, "pb", 5.5)])
    recs = store.get_valuations(["600519"], as_of=date(2026, 1, 31), lookback=1)
    got = {r.item: r.value for r in recs}
    assert got == {"pe_ttm": 18.2, "pb": 5.5}


def test_valuation_idempotent_and_upsert(store):
    store.write_valuations([_val("600519", 1, "pe_ttm", 18.2)])
    store.write_valuations([_val("600519", 1, "pe_ttm", 19.0)])  # 同主键 → 覆盖
    [rec] = store.get_valuations(["600519"], as_of=date(2026, 1, 31), lookback=1)
    assert rec.value == 19.0
    n = store._connection.execute("SELECT count(*) FROM stock_valuation").fetchone()[0]
    assert n == 1


def test_valuation_as_of_and_lookback_per_item(store):
    store.write_valuations([_val("600519", d, "pe_ttm", 10.0 + d) for d in (1, 2, 3, 4)])
    store.write_valuations([_val("600519", d, "pb", 5.0 + d) for d in (1, 2, 3, 4)])
    recs = store.get_valuations(["600519"], as_of=date(2026, 1, 3), lookback=2)
    by_item = {}
    for r in recs:
        by_item.setdefault(r.item, []).append((r.date.day, r.value))
    # 每个 item 各取 <= 1/3 的最近 2 条，升序。
    assert by_item["pe_ttm"] == [(2, 12.0), (3, 13.0)]
    assert by_item["pb"] == [(2, 7.0), (3, 8.0)]


def test_valuation_get_max_date(store):
    assert store.get_max_date("600519", table="stock_valuation") is None
    store.write_valuations([_val("600519", d, "pe_ttm", 10.0) for d in (1, 2, 3)])
    assert store.get_max_date("600519", table="stock_valuation") == date(2026, 1, 3)


# ---- source ----

class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


class FakeBaidu:
    def __init__(self, series_by_indicator):
        self.series_by_indicator = series_by_indicator
        self.calls = []

    def stock_zh_valuation_baidu(self, symbol, indicator, period):
        self.calls.append((symbol, indicator, period))
        return FakeFrame(self.series_by_indicator.get(indicator, []))


def test_build_skips_missing_values():
    rows = [
        {"date": "2026-01-01", "value": 18.2},
        {"date": "2026-01-02", "value": None},  # 缺值跳过
        {"date": "2026-01-03", "value": 18.5},
    ]
    recs = build_valuation_records("600519", "pe_ttm", rows, source="baidu")
    assert [(r.date.day, r.value) for r in recs] == [(1, 18.2), (3, 18.5)]


def test_fetch_baidu_uses_digits_and_merges_items():
    fake = FakeBaidu({
        "市盈率(TTM)": [{"date": "2026-01-01", "value": 18.2}],
        "市净率": [{"date": "2026-01-01", "value": 5.5}],
        "总市值": [{"date": "2026-01-01", "value": 15000.0}],
    })
    recs = fetch_valuations_baidu("600519.SH", fake)  # 带后缀 → 应转纯 6 位
    assert all(c[0] == "600519" for c in fake.calls)  # 纯 6 位代码
    assert {r.item for r in recs} == {"pe_ttm", "pb", "total_mv"}


def test_fetch_baidu_unknown_item_raises():
    with pytest.raises(ValuationSourceError):
        fetch_valuations_baidu("600519", FakeBaidu({}), items=("bogus",))


def test_fetch_baidu_empty_raises():
    with pytest.raises(ValuationSourceError):
        fetch_valuations_baidu("600519", FakeBaidu({}), items=("pe_ttm",))


# ---- collect_valuations ----

from swell_quant.marketdata.collect import collect_valuations  # noqa: E402

_NOW = None  # collect_valuations 生成 batch_id 用当前时间即可


def test_collect_valuations_first_and_incremental(store):
    calls = {"n": 0}

    def fake_fetch(symbol, provider, *, items, period, source):
        calls["n"] += 1
        # 首次返回 1-3 日，第二次返回 1-4 日（含已存的旧日）。
        days = (1, 2, 3) if calls["n"] == 1 else (1, 2, 3, 4)
        return [_val(symbol, d, "pe_ttm", 10.0 + d, source) for d in days]

    r1 = collect_valuations(["600519"], store, provider=None, fetch=fake_fetch)
    assert r1.results[0].rows == 3
    r2 = collect_valuations(["600519"], store, provider=None, fetch=fake_fetch)
    assert r2.results[0].rows == 1  # 只有 1/4 是新观测
    assert store.get_max_date("600519", table="stock_valuation") == date(2026, 1, 4)


def test_collect_valuations_failure_isolated_and_logged(store):
    def fake_fetch(symbol, provider, *, items, period, source):
        if symbol == "bad":
            raise RuntimeError("boom")
        return [_val(symbol, 1, "pe_ttm", 18.0, source)]

    result = collect_valuations(["600519", "bad"], store, provider=None, fetch=fake_fetch)
    assert result.status == "partial"
    assert result.succeeded == ("600519",)
    log = store.get_ingestion_log()
    assert log[-1]["table_name"] == "stock_valuation"
    assert log[-1]["status"] == "partial"
