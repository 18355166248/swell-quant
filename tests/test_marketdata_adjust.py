from datetime import date

import pytest

from swell_quant.marketdata import BarRecord, apply_start_anchor, normalize_adj_factor


def _bar(day: int, adj_factor: float, symbol: str = "600519") -> BarRecord:
    # 只关心 adj_factor 归一化，OHLC 用占位值即可。
    return BarRecord(
        symbol=symbol,
        date=date(2026, 1, day),
        open=10.0,
        high=10.0,
        low=10.0,
        close=10.0,
        volume=100,
        amount=1000.0,
        adj_factor=adj_factor,
        source="test",
    )


def test_normalize_makes_first_factor_one():
    assert normalize_adj_factor([2.0, 2.0, 2.5]) == [1.0, 1.0, 1.25]


def test_normalize_empty_is_empty():
    assert normalize_adj_factor([]) == []


def test_normalize_zero_anchor_raises():
    with pytest.raises(ValueError):
        normalize_adj_factor([0.0, 1.0])


def test_start_anchor_orders_by_date_and_normalizes():
    bars = [_bar(3, 2.5), _bar(1, 2.0), _bar(2, 2.0)]  # 乱序输入
    result = apply_start_anchor(bars)
    assert [b.date.day for b in result] == [1, 2, 3]
    assert [b.adj_factor for b in result] == [1.0, 1.0, 1.25]


def test_start_anchor_rejects_mixed_symbols():
    with pytest.raises(ValueError):
        apply_start_anchor([_bar(1, 1.0, "600519"), _bar(2, 1.0, "000001")])


def test_future_dividend_does_not_rewrite_history():
    """7-A 的核心不变性：追加“未来新分红”后，历史日的 adj_factor 不变。

    数据源给的是**末点锚定**因子（最新一天 = 1.0），这正是危险来源：
    - 批次1（截到 d3，尚无分红）：末点锚定 = [1, 1, 1]
    - 批次2（截到 d5，d4 除权、后复权步进 1.25）：末点锚定把全部历史缩小
      为 [0.8, 0.8, 0.8, 1.0, 1.0]

    若直接存末点锚定，d1~d3 会从 1.0 被改写成 0.8 —— 破坏 PIT。
    经起点锚定归一化后，两批在共同历史 d1~d3 上的因子必须完全一致。
    """
    batch1 = apply_start_anchor([_bar(1, 1.0), _bar(2, 1.0), _bar(3, 1.0)])
    batch2 = apply_start_anchor(
        [_bar(1, 0.8), _bar(2, 0.8), _bar(3, 0.8), _bar(4, 1.0), _bar(5, 1.0)]
    )

    hist1 = {b.date: b.adj_factor for b in batch1}
    hist2 = {b.date: b.adj_factor for b in batch2}
    for day in (1, 2, 3):
        assert hist1[date(2026, 1, day)] == pytest.approx(hist2[date(2026, 1, day)])

    # 并且这些历史因子是 1.0（未受未来分红影响），而分红后的 d4/d5 抬升为 1.25。
    assert hist2[date(2026, 1, 1)] == pytest.approx(1.0)
    assert hist2[date(2026, 1, 4)] == pytest.approx(1.25)
    assert hist2[date(2026, 1, 5)] == pytest.approx(1.25)
