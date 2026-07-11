from __future__ import annotations

from swell_quant.factors.base import FactorValues
from swell_quant.factors.pipeline import CompositeResult


def equal_weight_top_n(result: CompositeResult, n: int) -> dict[str, float]:
    """按综合分取前 ``n`` 名等权。不足 n 只则按实际数量等权；无可选票返回空。"""

    top = result.ranking()[:n]
    if not top:
        return {}
    weight = 1.0 / len(top)
    return {symbol: weight for symbol, _ in top}


def portfolio_return(weights: dict[str, float], returns: FactorValues) -> float | None:
    """组合在持有期的收益 = 各持仓收益按权重加权。

    某持仓收益缺失（None）时，按“**可用权重**重归一化”——只在有收益的持仓上分配权重，
    避免把缺失当 0 收益而系统性拉低组合表现。全部缺失或空组合返回 None。
    """

    total = 0.0
    used_weight = 0.0
    for symbol, weight in weights.items():
        ret = returns.get(symbol)
        if ret is not None:
            total += weight * ret
            used_weight += weight
    if used_weight == 0:
        return None
    return total / used_weight
