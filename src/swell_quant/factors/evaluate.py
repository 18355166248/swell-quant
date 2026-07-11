from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore


@dataclass(frozen=True)
class ICResult:
    """单个截面的因子评估结果。

    - ``ic``：因子值与未来收益的皮尔逊相关（线性预测力）。
    - ``rank_ic``：斯皮尔曼（秩）相关，更稳健、抗异常值，是因子选股常看的主指标。
    - ``n``：参与计算的有效样本数（因子值与未来收益都非缺失）。
    ``n<2`` 或截面无离散度时 ic/rank_ic 记 None。
    """

    ic: float | None
    rank_ic: float | None
    n: int


def forward_returns(
    store: MarketStore, symbols: Sequence[str], as_of: date, horizon: int
) -> FactorValues:
    """每票在 ``as_of`` 之后 ``horizon`` 个交易日的**后复权**收益率。

    用 hfq 前视查询：以 date >= as_of 的首根为起点、第 horizon+1 根为终点，
    收益 = 终/起 - 1。前视根数不足的票记 None。
    """

    bars = store.get_bars_hfq_forward(symbols, as_of, horizon)
    by_symbol: dict[str, list[BarRecord]] = defaultdict(list)
    for bar in bars:  # 已按 (symbol, date) 升序
        by_symbol[bar.symbol].append(bar)

    result: FactorValues = {}
    for symbol in symbols:
        window = by_symbol.get(symbol, [])
        if len(window) < horizon + 1:
            result[symbol] = None
            continue
        start_close = window[0].close
        end_close = window[-1].close
        result[symbol] = (end_close / start_close - 1) if start_close else None
    return result


def _aligned(
    factor_values: FactorValues, returns: FactorValues
) -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    for symbol, fv in factor_values.items():
        rv = returns.get(symbol)
        if fv is not None and rv is not None:
            xs.append(fv)
            ys.append(rv)
    return xs, ys


def _correlation(xs: list[float], ys: list[float], method: str) -> float | None:
    if len(xs) < 2:
        return None
    try:
        if method == "ranked":
            return statistics.correlation(xs, ys, method="ranked")
        return statistics.correlation(xs, ys)
    except statistics.StatisticsError:
        # 截面无离散度（方差为 0）等 → 相关无定义。
        return None


def information_coefficient(
    factor_values: FactorValues, returns: FactorValues
) -> float | None:
    """皮尔逊 IC。"""

    xs, ys = _aligned(factor_values, returns)
    return _correlation(xs, ys, method="linear")


def rank_ic(factor_values: FactorValues, returns: FactorValues) -> float | None:
    """斯皮尔曼（秩）IC。"""

    xs, ys = _aligned(factor_values, returns)
    return _correlation(xs, ys, method="ranked")


def evaluate_factor(
    factor: Factor,
    store: MarketStore,
    symbols: Sequence[str],
    as_of: date,
    horizon: int = 20,
) -> ICResult:
    """在单个截面评估因子：算因子值与未来 horizon 日收益的 IC / RankIC。"""

    factor_values = factor.compute(store, symbols, as_of)
    returns = forward_returns(store, symbols, as_of, horizon)
    xs, _ = _aligned(factor_values, returns)
    return ICResult(
        ic=information_coefficient(factor_values, returns),
        rank_ic=rank_ic(factor_values, returns),
        n=len(xs),
    )
