from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import date

from swell_quant.factors.base import Factor
from swell_quant.factors.evaluate import evaluate_factor_series, forward_returns
from swell_quant.factors.pipeline import FactorPipeline, FactorWeight
from swell_quant.marketdata.store import MarketStore
from swell_quant.portfolio.backtest import (
    BacktestResult,
    PeriodReturn,
    _benchmark,
    _turnover,
)
from swell_quant.portfolio.construct import equal_weight_top_n, portfolio_return


def train_ic_weights(
    factors: Sequence[Factor],
    store: MarketStore,
    symbols: Sequence[str],
    train_dates: Sequence[date],
    horizon: int,
) -> tuple[FactorWeight, ...]:
    """用训练期各因子的平均 RankIC 作为其权重。

    权重由**过去**数据决定，不含前视；负 IC 自动得负权重（方向自校正，
    如高波动 IC 为负 → 负权重 = 低波动暴露）。训练期无有效 IC 的因子权重记 0。
    """

    weights: list[FactorWeight] = []
    for factor in factors:
        summary = evaluate_factor_series(factor, store, symbols, train_dates, horizon)
        ic = summary.rank_ic.mean
        weights.append(FactorWeight(factor=factor, weight=ic if ic is not None else 0.0))
    return tuple(weights)


def walk_forward_backtest(
    factors: Sequence[Factor],
    store: MarketStore,
    symbols: Sequence[str],
    rebalance_dates: Sequence[date],
    *,
    train_size: int,
    top_n: int,
    horizon: int = 20,
    benchmark_index: str | None = None,
    equal_weight_benchmark: bool = False,
    cost_bps: float = 0.0,
) -> BacktestResult:
    """滚动样本外回测：每个调仓日用**前** ``train_size`` 期的 IC 定权重，再在当日选股。

    因子权重完全由历史训练窗口决定（IC 加权），故每期选股都是**样本外**——直接回答
    “这个 edge 是真的还是过拟合”。前 ``train_size`` 期用于起始训练、不产生持仓。
    基准同 backtest_composite：``equal_weight_benchmark=True`` 用等权全池（剥离等权 tilt）。
    """

    cost_rate = cost_bps / 10000.0

    # 性能：每个因子每期的 RankIC 只算一次（否则每个 OOS 期都会重算整个训练窗，O(期×窗)）。
    # 训练权重 = 训练窗内各期缓存 RankIC 的均值，与 train_ic_weights 等价、但快一个数量级。
    ic_cache: list[dict[date, float | None]] = []
    for factor in factors:
        summary = evaluate_factor_series(factor, store, symbols, rebalance_dates, horizon)
        ic_cache.append({p.as_of: p.rank_ic for p in summary.per_period})

    prev_weights: dict[str, float] = {}
    periods: list[PeriodReturn] = []
    for i in range(train_size, len(rebalance_dates)):
        train_dates = rebalance_dates[i - train_size : i]
        as_of = rebalance_dates[i]

        trained = []
        for factor, cache in zip(factors, ic_cache):
            ics = [cache[d] for d in train_dates if cache[d] is not None]
            trained.append(FactorWeight(factor=factor, weight=statistics.fmean(ics) if ics else 0.0))
        scores = FactorPipeline(weights=tuple(trained)).compute(store, symbols, as_of)
        weights = equal_weight_top_n(scores, top_n)

        rets = forward_returns(store, list(weights), as_of, horizon)
        period_ret = portfolio_return(weights, rets) if weights else None
        bench = _benchmark(store, symbols, as_of, horizon, benchmark_index, equal_weight_benchmark)
        cost = cost_rate * _turnover(prev_weights, weights)
        periods.append(
            PeriodReturn(
                as_of=as_of,
                ret=period_ret,
                n_holdings=len(weights),
                benchmark_ret=bench,
                cost=cost,
            )
        )
        prev_weights = weights
    return BacktestResult(periods=tuple(periods))
