from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from swell_quant.marketdata.records import BarRecord


def normalize_adj_factor(factors: Sequence[float]) -> list[float]:
    """把任意锚定的复权因子序列归一化为“起点锚定”（首元素 = 1.0）。

    输入 ``factors`` 须按日期**升序**排列（factors[0] 是最早一天）。
    返回 ``f[t] = factors[t] / factors[0]``。

    这是 7-A 的核心：数据源给的因子可能是“末点锚定”（最新一天 = 1.0，
    每逢新分红就把全部历史重新缩放）。而因子之间的**比值**是锚定无关的
    客观量，除以起点因子即得起点锚定序列——它对“未来追加新分红”不变，
    因此可安全落库、支持增量采集。
    """

    if not factors:
        return []
    anchor = factors[0]
    if anchor == 0:
        raise ValueError("adj_factor 起点为 0，无法归一化（数据源异常）")
    return [factor / anchor for factor in factors]


def apply_start_anchor(bars: Sequence[BarRecord]) -> list[BarRecord]:
    """把一只股票的日线按日期升序排好，并将 adj_factor 归一化为起点锚定。

    要求 ``bars`` 同属一个 symbol。返回新的 BarRecord 列表（不改原对象）。
    增量采集时，起点必须是**全历史起点**——调用方须把库中已存的最早一段
    一并传入，或复用已存的起点因子做锚，切勿以“当前批次首行”当起点
    （见 docs/data-module-decisions.md §7-A）。
    """

    if not bars:
        return []
    symbols = {bar.symbol for bar in bars}
    if len(symbols) != 1:
        raise ValueError(f"apply_start_anchor 只接受单一 symbol，收到：{sorted(symbols)}")

    ordered = sorted(bars, key=lambda bar: bar.date)
    normalized = normalize_adj_factor([bar.adj_factor for bar in ordered])
    return [replace(bar, adj_factor=factor) for bar, factor in zip(ordered, normalized)]
