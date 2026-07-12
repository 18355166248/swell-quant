from datetime import date

import pytest

from swell_quant.marketdata.collect import collect_fundamentals
from swell_quant.marketdata.source_fundamentals import (
    FundamentalSourceError,
    build_fundamental_records,
    fetch_fundamentals,
    statutory_disclosure_date,
)
from swell_quant.marketdata.store import MarketStore


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


def _row(code, roe=None, np_yoy=None, rev_yoy=None):
    return {
        "股票代码": code,
        "净资产收益率": roe,
        "净利润-同比增长": np_yoy,
        "营业总收入-同比增长": rev_yoy,
    }


# ---- statutory_disclosure_date ----


def test_statutory_dates_for_standard_periods():
    assert statutory_disclosure_date(date(2024, 3, 31)) == date(2024, 4, 30)
    assert statutory_disclosure_date(date(2024, 6, 30)) == date(2024, 8, 31)
    assert statutory_disclosure_date(date(2024, 9, 30)) == date(2024, 10, 31)
    assert statutory_disclosure_date(date(2024, 12, 31)) == date(2025, 4, 30)  # 年报次年披露


# ---- build_fundamental_records ----


def test_build_sets_event_and_knowledge_dates():
    frame = FakeFrame([_row("600519", roe=10.57)])
    [rec] = build_fundamental_records(frame, "20240331", items=("roe",))
    assert rec.symbol == "600519"
    assert rec.event_date == date(2024, 3, 31)
    assert rec.knowledge_date == date(2024, 4, 30)  # 保守估计，非源里的“最新公告日”
    assert rec.value == pytest.approx(10.57)


def test_build_skips_nan_values():
    frame = FakeFrame([_row("600519", roe=float("nan"), np_yoy=15.0)])
    recs = build_fundamental_records(frame, "20240331", items=("roe", "net_profit_yoy"))
    items = {r.item for r in recs}
    assert items == {"net_profit_yoy"}  # roe 为 NaN 被跳过


def test_build_multiple_items_and_symbols():
    frame = FakeFrame([_row("600519", roe=10.0, np_yoy=15.0), _row("000001", roe=8.0)])
    recs = build_fundamental_records(frame, "20240331", items=("roe", "net_profit_yoy"))
    got = {(r.symbol, r.item): r.value for r in recs}
    assert got == {
        ("600519", "roe"): 10.0,
        ("600519", "net_profit_yoy"): 15.0,
        ("000001", "roe"): 8.0,
    }


def test_fetch_empty_raises():
    class P:
        def stock_yjbb_em(self, date):
            return FakeFrame([])

    with pytest.raises(FundamentalSourceError):
        fetch_fundamentals(P(), "20240331")


# ---- collect_fundamentals ----


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_collect_filters_to_pool_and_is_period_driven(store):
    calls = []

    def fake_fetch(provider, period, *, items, source):
        calls.append(period)
        return build_fundamental_records(
            FakeFrame([_row("600519", roe=10.0), _row("000001", roe=8.0), _row("999999", roe=1.0)]),
            period,
            items=("roe",),
            source=source,
        )

    result = collect_fundamentals(
        ["600519", "000001"],
        store,
        provider=None,
        periods=["20240331", "20240630"],
        items=("roe",),
        fetch=fake_fetch,
    )
    assert calls == ["20240331", "20240630"]  # 按期驱动
    # 每期 2 条（池外 999999 被过滤），共 4。
    assert result.total_rows == 4
    recs = store.get_fundamentals(["600519", "000001", "999999"], as_of=date(2024, 12, 31))
    assert {r.symbol for r in recs} == {"600519", "000001"}


def test_collect_is_idempotent(store):
    def fake_fetch(provider, period, *, items, source):
        return build_fundamental_records(
            FakeFrame([_row("600519", roe=10.0)]), period, items=("roe",), source=source
        )

    collect_fundamentals(["600519"], store, provider=None, periods=["20240331"], fetch=fake_fetch)
    collect_fundamentals(["600519"], store, provider=None, periods=["20240331"], fetch=fake_fetch)
    n = store._connection.execute("SELECT count(*) FROM stock_fundamental").fetchone()[0]
    assert n == 1


def test_collect_period_failure_isolated_and_logged(store):
    def fake_fetch(provider, period, *, items, source):
        if period == "bad":
            raise FundamentalSourceError("boom")
        return build_fundamental_records(
            FakeFrame([_row("600519", roe=10.0)]), period, items=("roe",), source=source
        )

    result = collect_fundamentals(
        ["600519"], store, provider=None, periods=["20240331", "bad"], fetch=fake_fetch
    )
    assert result.status == "partial"
    log = store.get_ingestion_log()
    assert log[-1]["table_name"] == "stock_fundamental"
