from datetime import date

import pytest

from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.source_bars import (
    BarSourceError,
    build_bar_records,
    build_bars_from_factor_steps,
    fetch_bars,
)


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


class FakeAkshare:
    """按 adjust 参数返回不同的行情帧，模拟真实 stock_zh_a_hist。"""

    def __init__(self, raw_rows, hfq_rows):
        self.raw_rows = raw_rows
        self.hfq_rows = hfq_rows
        self.calls = []

    def stock_zh_a_hist(self, symbol, period, start_date, end_date, adjust):
        self.calls.append(adjust)
        return FakeFrame(self.hfq_rows if adjust == "hfq" else self.raw_rows)


def _raw(day, close, open_=None):
    return {
        "日期": f"2026-01-0{day}",
        "开盘": open_ if open_ is not None else close,
        "最高": close,
        "最低": close,
        "收盘": close,
        "成交量": 100,
        "成交额": 1000.0,
    }


def test_build_stores_raw_price_and_derived_factor():
    # 不复权收盘 10；后复权收盘 12 → 因子 1.2。存的价必须是不复权的 10。
    raw = [_raw(1, 10.0, open_=9.5)]
    hfq = [_raw(1, 12.0)]
    [bar] = build_bar_records("600519", raw, hfq, source="akshare")
    assert bar == BarRecord(
        symbol="600519",
        date=date(2026, 1, 1),
        open=9.5,
        high=10.0,
        low=10.0,
        close=10.0,
        volume=100,
        amount=1000.0,
        adj_factor=1.2,
        source="akshare",
    )


def test_factor_is_listing_anchored_and_immune_to_future_dividend():
    """7-A 对真实来源形态的核对：hfq/raw 比值天生免疫未来分红。

    不复权价是客观事实、永不变。除权日 d3 后 hfq 抬升：
    - d1,d2 无分红：hfq==raw → 因子 1.0
    - d3 起：hfq = raw*1.25 → 因子 1.25
    历史 d1,d2 的因子恒为 1.0，不因 d3 的分红被改写。
    """
    raw = [_raw(1, 10.0), _raw(2, 10.0), _raw(3, 8.0)]
    hfq = [_raw(1, 10.0), _raw(2, 10.0), _raw(3, 10.0)]  # d3 后复权抬升
    bars = build_bar_records("600519", raw, hfq, source="akshare")
    factors = {b.date.day: b.adj_factor for b in bars}
    assert factors[1] == pytest.approx(1.0)
    assert factors[2] == pytest.approx(1.0)
    assert factors[3] == pytest.approx(1.25)


def test_rows_without_hfq_alignment_are_skipped():
    raw = [_raw(1, 10.0), _raw(2, 10.0)]
    hfq = [_raw(1, 10.0)]  # d2 缺后复权对齐
    bars = build_bar_records("600519", raw, hfq, source="akshare")
    assert [b.date.day for b in bars] == [1]


def test_fetch_bars_calls_both_adjust_modes():
    fake = FakeAkshare(raw_rows=[_raw(1, 10.0)], hfq_rows=[_raw(1, 11.0)])
    bars = fetch_bars("600519", "20260101", "20260131", provider=fake)
    assert fake.calls == ["", "hfq"]
    assert bars[0].adj_factor == pytest.approx(1.1)
    assert bars[0].close == 10.0


def test_fetch_bars_empty_raises():
    fake = FakeAkshare(raw_rows=[], hfq_rows=[])
    with pytest.raises(BarSourceError):
        fetch_bars("600519", "20260101", "20260131", provider=fake)


def _step(day, factor):
    return {"date": f"2026-01-0{day}", "hfq_factor": factor}


def test_factor_steps_forward_fill():
    """稀疏台阶因子前向填充：除权前用旧因子，除权日起用新因子。"""
    raw = [_raw(1, 10.0), _raw(2, 10.0), _raw(3, 8.0), _raw(4, 8.0)]
    # 台阶：上市锚 1.0，d3 除权抬到 1.25。d2、d4 无台阶，靠前向填充。
    steps = [_step(1, 1.0), _step(3, 1.25)]
    bars = build_bars_from_factor_steps("600519", raw, steps, source="sina")
    factors = {b.date.day: b.adj_factor for b in bars}
    assert factors == {1: 1.0, 2: 1.0, 3: 1.25, 4: 1.25}
    # 存的仍是不复权价
    assert {b.date.day: b.close for b in bars} == {1: 10.0, 2: 10.0, 3: 8.0, 4: 8.0}


def test_factor_steps_exact_no_division_noise():
    """台阶因子直接取用高精度值，不经相除 → 幂等 upsert 安全。"""
    raw = [_raw(1, 1685.01)]
    steps = [_step(1, 8.0718393241)]
    [bar] = build_bars_from_factor_steps("600519", raw, steps, source="sina")
    assert bar.adj_factor == 8.0718393241  # 精确保留，无浮点相除


def test_factor_steps_empty_raises():
    with pytest.raises(BarSourceError):
        build_bars_from_factor_steps("600519", [_raw(1, 10.0)], [], source="sina")


def test_trade_day_before_first_step_is_skipped():
    # 交易日早于任何因子台阶（异常数据），跳过而非写脏因子。
    raw = [_raw(1, 10.0), _raw(2, 10.0)]
    steps = [_step(2, 1.0)]
    bars = build_bars_from_factor_steps("600519", raw, steps, source="sina")
    assert [b.date.day for b in bars] == [2]
