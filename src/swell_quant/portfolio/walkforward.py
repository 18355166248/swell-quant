from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from swell_quant.factors.base import Factor
from swell_quant.factors.evaluate import evaluate_factor_series, forward_returns
from swell_quant.factors.pipeline import FactorPipeline, FactorWeight
from swell_quant.marketdata.store import MarketStore
from swell_quant.portfolio.backtest import (
    BacktestResult,
    PeriodReturn,
    _turnover,
    benchmark_return,
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
    cost_bps: float = 0.0,
) -> BacktestResult:
    """滚动样本外回测：每个调仓日用**前** ``train_size`` 期的 IC 定权重，再在当日选股。

    因子权重完全由历史训练窗口决定（IC 加权），故每期选股都是**样本外**——直接回答
    “这个 edge 是真的还是过拟合”。前 ``train_size`` 期用于起始训练、不产生持仓。
    """

    cost_rate = cost_bps / 10000.0
    prev_weights: dict[str, float] = {}
    periods: list[PeriodReturn] = []
    for i in range(train_size, len(rebalance_dates)):
        train_dates = rebalance_dates[i - train_size : i]
        as_of = rebalance_dates[i]

        trained = train_ic_weights(factors, store, symbols, train_dates, horizon)
        scores = FactorPipeline(weights=trained).compute(store, symbols, as_of)
        weights = equal_weight_top_n(scores, top_n)

        rets = forward_returns(store, list(weights), as_of, horizon)
        period_ret = portfolio_return(weights, rets) if weights else None
        bench = (
            benchmark_return(store, benchmark_index, as_of, horizon)
            if benchmark_index
            else None
        )
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
