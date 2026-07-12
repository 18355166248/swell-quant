from datetime import date, datetime

import pytest

from swell_quant.marketdata.collect import collect_bars
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.source_bars import BarSourceError
from swell_quant.marketdata.store import MarketStore


def _bar(symbol, day, close=10.0):
    return BarRecord(
        symbol=symbol,
        date=date(2026, 1, day),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100,
        amount=close * 100,
        adj_factor=1.0,
        source="fake",
    )


class FakeFetch:
    """记录每次调用的 (symbol, start, end)，并按预设返回 bars 或抛错。"""

    def __init__(self, bars_by_symbol=None, raise_for=None):
        self.bars_by_symbol = bars_by_symbol or {}
        self.raise_for = raise_for or set()
        self.calls = []

    def __call__(self, symbol, start_date, end_date, provider):
        self.calls.append((symbol, start_date, end_date))
        if symbol in self.raise_for:
            raise RuntimeError("boom")
        return list(self.bars_by_symbol.get(symbol, []))


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


NOW = datetime(2026, 2, 1, 9, 0, 0)


def test_first_collect_uses_default_start(store):
    fetch = FakeFetch(bars_by_symbol={"600519": [_bar("600519", 1), _bar("600519", 2)]})
    result = collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=fetch,
        now=NOW,
    )
    assert fetch.calls == [("600519", "20260101", "20260131")]  # 无数据 → 默认起点
    assert result.total_rows == 2
    assert result.succeeded == ("600519",)
    assert store.get_max_date("600519") == date(2026, 1, 2)


def test_incremental_fetches_from_day_after_max(store):
    store.write_bars([_bar("600519", 1), _bar("600519", 2)])  # 库里已到 1/2
    fetch = FakeFetch(bars_by_symbol={"600519": [_bar("600519", 3)]})
    collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=fetch,
        now=NOW,
    )
    # 增量窗口从 max_date+1 = 1/3 起，不重拉历史。
    assert fetch.calls == [("600519", "20260103", "20260131")]
    assert store.get_max_date("600519") == date(2026, 1, 3)


def test_skips_when_already_current(store):
    store.write_bars([_bar("600519", 31)])  # 已到 end_date
    fetch = FakeFetch()
    result = collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=fetch,
        now=NOW,
    )
    assert fetch.calls == []  # 不发网络请求
    assert result.results[0].status == "skipped"


def test_per_symbol_failure_is_isolated(store):
    fetch = FakeFetch(
        bars_by_symbol={"600519": [_bar("600519", 1)], "000001": [_bar("000001", 1)]},
        raise_for={"000002"},
    )
    result = collect_bars(
        ["600519", "000002", "000001"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=fetch,
        now=NOW,
    )
    assert result.status == "partial"
    assert result.succeeded == ("600519", "000001")  # 其它票不受影响
    assert [f.symbol for f in result.failed] == ["000002"]
    assert "boom" in result.failed[0].reason


def test_all_failed_status(store):
    fetch = FakeFetch(raise_for={"600519"})
    result = collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=fetch,
        now=NOW,
    )
    assert result.status == "failed"


def test_ingestion_log_recorded(store):
    fetch = FakeFetch(
        bars_by_symbol={"600519": [_bar("600519", 1), _bar("600519", 2)]},
        raise_for={"000002"},
    )
    result = collect_bars(
        ["600519", "000002"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=fetch,
        now=NOW,
    )
    log = store.get_ingestion_log()
    assert len(log) == 1
    entry = log[0]
    assert entry["batch_id"] == result.batch_id
    assert entry["table_name"] == "stock_bar_1d"
    assert entry["source"] == "sina"
    assert entry["row_count"] == 2
    assert entry["status"] == "partial"
    assert "000002" in entry["message"]


def test_incremental_empty_response_is_skipped_not_failed(store):
    # 增量尾窗落在非交易日：源抛 BarSourceError（空响应）应归为 skipped。
    store.write_bars([_bar("600519", 28)])  # max_date=1/28，end=1/31（含周末尾窗）

    class RaisingFetch:
        def __init__(self):
            self.calls = 0

        def __call__(self, symbol, start_date, end_date, provider):
            self.calls += 1
            raise BarSourceError("空窗口")

    fetch = RaisingFetch()
    result = collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=fetch,
        now=NOW,
    )
    assert fetch.calls == 1  # 确实尝试了增量拉取
    assert result.results[0].status == "skipped"  # 但空响应不算失败
    assert result.status == "ok"


def test_incremental_first_time_empty_still_fails(store):
    # 首次采集（库里无该票）遇空响应仍应是真失败，不能被误判为已最新。
    class RaisingFetch:
        def __call__(self, symbol, start_date, end_date, provider):
            raise BarSourceError("该票无数据")

    result = collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=RaisingFetch(),
        now=NOW,
    )
    assert result.results[0].status == "failed"


def test_incremental_filters_stale_rows(store):
    # 源把已存的陈旧行也带回来（日期过滤不精确）：只应计入真正新增的行。
    store.write_bars([_bar("600519", 1), _bar("600519", 2)])  # max_date=1/2
    fetch = FakeFetch(
        bars_by_symbol={"600519": [_bar("600519", 2), _bar("600519", 3)]}  # 含陈旧的 1/2
    )
    result = collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=fetch,
        now=NOW,
    )
    assert result.results[0].rows == 1  # 只有 1/3 是新增
    assert store.get_max_date("600519") == date(2026, 1, 3)


def test_clamps_rows_beyond_end_date(store):
    # 源在空窗口时返回窗口外的最近一行（1/31 之后的 2/5）：必须被钳掉。
    fetch = FakeFetch(bars_by_symbol={"600519": [_bar("600519", 3), _bar("600519", 5)]})
    # end_date=1/3 → 只有 1/3 在范围内，1/5 应被钳除。
    result = collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260103",
        fetch=fetch,
        now=NOW,
    )
    assert result.results[0].rows == 1
    assert store.get_max_date("600519") == date(2026, 1, 3)


def test_calendar_makes_skip_precise_without_fetch(store):
    # 库里已到 1/28（最近交易日），end=1/31 但 1/29-31 无交易日。
    # 有交易日历时应精确判定“已最新”并**根本不发请求**，而非靠空响应兜底。
    store.write_bars([_bar("600519", 28)])
    store.write_trade_calendar([date(2026, 1, d) for d in (27, 28)])  # 1/28 是最近交易日
    fetch = FakeFetch()
    result = collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260131",
        fetch=fetch,
        now=NOW,
    )
    assert fetch.calls == []  # 关键：日历让我们免了这次无谓网络请求
    assert result.results[0].status == "skipped"


def test_end_to_end_incremental_is_idempotent(store):
    # 第一次采全量，第二次已最新 → 跳过；两次后行数不变。
    fetch = FakeFetch(bars_by_symbol={"600519": [_bar("600519", d) for d in (1, 2, 3)]})
    collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260103",
        fetch=fetch,
        now=NOW,
    )
    second = collect_bars(
        ["600519"],
        store,
        provider=None,
        default_start="20260101",
        end_date="20260103",
        fetch=fetch,
        now=NOW,
    )
    assert second.results[0].status == "skipped"
    bars = store.get_bars(["600519"], as_of=date(2026, 1, 31), lookback=10)
    assert len(bars) == 3
