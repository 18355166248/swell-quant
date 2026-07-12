from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import date

from swell_quant.factors.base import Factor
from swell_quant.factors.evaluate import evaluate_factor, evaluate_factor_series, forward_returns
from swell_quant.factors.pipeline import FactorPipeline, FactorWeight
from swell_quant.marketdata.store import MarketStore
from swell_quant.portfolio.backtest import (
    BacktestResult,
    PeriodReturn,
    _benchmark,
    _resolve_symbols,
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
    universe_index: str | None = None,
) -> BacktestResult:
    """滚动样本外回测：每个调仓日用**前** ``train_size`` 期的 IC 定权重，再在当日选股。

    因子权重完全由历史训练窗口决定（IC 加权），故每期选股都是**样本外**——直接回答
    “这个 edge 是真的还是过拟合”。前 ``train_size`` 期用于起始训练、不产生持仓。
    基准同 backtest_composite：``equal_weight_benchmark=True`` 用等权全池（剥离等权 tilt）。
    ``universe_index`` 非空时按调仓日动态取当时成分（抗幸存者偏差）；IC、选股、基准均用
    当日动态池。
    """

    cost_rate = cost_bps / 10000.0

    # 各调仓日的选股域（动态池则按日解析一次，复用）。
    universe_by_date = {
        d: _resolve_symbols(store, symbols, universe_index, d) for d in rebalance_dates
    }

    # 性能：每个因子每期的 RankIC 只算一次（否则每个 OOS 期都会重算整个训练窗，O(期×窗)）。
    # 训练权重 = 训练窗内各期缓存 RankIC 的均值。IC 在当日动态池上评估。
    ic_cache: list[dict[date, float | None]] = [{} for _ in factors]
    for as_of in rebalance_dates:
        syms = universe_by_date[as_of]
        for factor_index, factor in enumerate(factors):
            ic_cache[factor_index][as_of] = evaluate_factor(
                factor, store, syms, as_of, horizon
            ).rank_ic

    prev_weights: dict[str, float] = {}
    periods: list[PeriodReturn] = []
    for i in range(train_size, len(rebalance_dates)):
        train_dates = rebalance_dates[i - train_size : i]
        as_of = rebalance_dates[i]
        syms = universe_by_date[as_of]

        trained = []
        for factor, cache in zip(factors, ic_cache):
            ics = [cache[d] for d in train_dates if cache[d] is not None]
            trained.append(
                FactorWeight(factor=factor, weight=statistics.fmean(ics) if ics else 0.0)
            )
        scores = FactorPipeline(weights=tuple(trained)).compute(store, syms, as_of)
        weights = equal_weight_top_n(scores, top_n)

        rets = forward_returns(store, list(weights), as_of, horizon)
        period_ret = portfolio_return(weights, rets) if weights else None
        bench = _benchmark(store, syms, as_of, horizon, benchmark_index, equal_weight_benchmark)
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
