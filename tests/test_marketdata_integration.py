"""端到端：不复权行情 + 台阶因子 → 合成 BarRecord → 落库 → as_of 读出。

证明 source 层与 store 层能咬合成一条完整管子，且后复权视图对“派生因子”
也算得对——这是数据模块行情主线的封顶验证。
"""

from datetime import date

import pytest

from swell_quant.marketdata import (
    MarketStore,
    build_bars_from_factor_steps,
)


def _raw(day, close):
    return {
        "日期": f"2026-01-{day:02d}",
        "开盘": close,
        "最高": close,
        "最低": close,
        "收盘": close,
        "成交量": 100,
        "成交额": close * 100,
    }


def test_source_to_store_roundtrip_with_dividend():
    # 不复权真实价：d3 除权后价格下台阶（10 → 8）。
    raw_rows = [_raw(1, 10.0), _raw(2, 10.0), _raw(3, 8.0), _raw(4, 8.0)]
    # 台阶因子：上市锚 1.0，d3 除权抬到 1.25。
    factor_steps = [
        {"date": "2026-01-01", "hfq_factor": 1.0},
        {"date": "2026-01-03", "hfq_factor": 1.25},
    ]

    bars = build_bars_from_factor_steps("600519", raw_rows, factor_steps, source="sina")

    with MarketStore(":memory:") as store:
        store.write_bars(bars)

        raw_out = store.get_bars(["600519"], as_of=date(2026, 1, 31), lookback=10)
        hfq_out = store.get_bars_hfq(["600519"], as_of=date(2026, 1, 31), lookback=10)

    # 事实表存不复权真实价，原样还原。
    assert [(b.date.day, b.close) for b in raw_out] == [(1, 10.0), (2, 10.0), (3, 8.0), (4, 8.0)]

    # 后复权视图 = raw * 派生因子；除权前后连续（10 → 10 → 10 → 10），无跳空。
    hfq_close = {b.date.day: b.close for b in hfq_out}
    assert hfq_close[1] == pytest.approx(10.0)
    assert hfq_close[2] == pytest.approx(10.0)
    assert hfq_close[3] == pytest.approx(10.0)  # 8.0 * 1.25
    assert hfq_close[4] == pytest.approx(10.0)  # 8.0 * 1.25
