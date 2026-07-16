"""service: CLI / HTTP API / 未来 MCP tool 共享的研究服务层。

所有入口都应经由这里调用研究内核（factors / portfolio），保证同一套参数校验
与结果口径。本模块不依赖 fastapi：参数错误统一抛 ``ValueError``，由各入口
自行翻译（HTTP 400 / CLI 退出码）。
"""

from __future__ import annotations

from datetime import date

from swell_quant.factors import (
    FactorPipeline,
    FactorWeight,
    MomentumFactor,
    QualityFactor,
    ReversalFactor,
    ValueFactor,
    VolatilityFactor,
    evaluate_factor_series,
    sample_as_of_dates,
)
from swell_quant.factors.base import Factor
from swell_quant.marketdata.store import MarketStore
from swell_quant.portfolio import backtest_composite

# 因子目录：看板与 CLI 从这里渲染可选因子。lookback 用于价量因子，item 用于财务/估值因子。
FACTOR_CATALOG = [
    {"name": "momentum", "label": "动量", "param": "lookback", "default": 20},
    {"name": "reversal", "label": "短期反转", "param": "lookback", "default": 5},
    {"name": "volatility", "label": "波动率(低波给负权重)", "param": "lookback", "default": 20},
    {"name": "value", "label": "价值(1/估值)", "param": "item", "default": "pe_ttm"},
    {"name": "quality", "label": "质量/成长", "param": "item", "default": "roe"},
]

# 所有对外研究产物统一携带的免责声明（金融合规要求）。
RESEARCH_NOTE = "仅用于研究，不构成投资建议"


def build_factor(name: str, lookback: int | None = None, item: str | None = None) -> Factor:
    if name == "momentum":
        return MomentumFactor(lookback or 20)
    if name == "reversal":
        return ReversalFactor(lookback or 5)
    if name == "volatility":
        return VolatilityFactor(lookback or 20)
    if name == "value":
        return ValueFactor(item or "pe_ttm")
    if name == "quality":
        return QualityFactor(item or "roe")
    raise ValueError(f"未知因子：{name}")


def run_factor_ic(
    store: MarketStore,
    *,
    name: str,
    start: date,
    end: date,
    lookback: int | None = None,
    item: str | None = None,
    step: int = 20,
    horizon: int = 20,
    universe_index: str = "000300",
) -> dict:
    """单因子多期 RankIC 评估。日期采样与股票池均走 as_of 接口，无未来函数。"""

    factor = build_factor(name, lookback=lookback, item=item)
    dates = sample_as_of_dates(store, start, end, step=step)
    as_of_pool = store.get_universe(universe_index, end, approximate_from_latest=True)
    summary = evaluate_factor_series(factor, store, as_of_pool, dates, horizon=horizon)
    stats = summary.rank_ic
    return {
        "factor": factor.name,
        "rank_ic": {
            "mean": stats.mean,
            "ir": stats.ir,
            "positive_rate": stats.positive_rate,
            "n": stats.n,
        },
        "note": RESEARCH_NOTE,
    }


def run_backtest(
    store: MarketStore,
    *,
    factors: list[dict],
    start: date,
    end: date,
    step: int = 20,
    horizon: int = 20,
    top_n: int = 50,
    cost_bps: float = 10.0,
    benchmark: str = "equal_weight",
    benchmark_index: str = "sh000300",
    universe_index: str | None = "000300",
) -> dict:
    """多因子组合回测。``factors`` 为 [{name, lookback?, item?, weight?}, ...]。

    基准二选一：equal_weight（等权全池，剥离等权 tilt）或 index（市值加权指数）。
    """

    weights = tuple(
        FactorWeight(
            build_factor(s["name"], lookback=s.get("lookback"), item=s.get("item")),
            s.get("weight", 1.0),
        )
        for s in factors
    )
    pipeline = FactorPipeline(weights=weights)
    dates = sample_as_of_dates(store, start, end, step=step)
    if len(dates) < 2:
        raise ValueError("日期区间内交易日不足")
    result = backtest_composite(
        pipeline,
        store,
        [],
        dates,
        top_n=top_n,
        horizon=horizon,
        universe_index=universe_index,
        benchmark_index=benchmark_index if benchmark == "index" else None,
        equal_weight_benchmark=benchmark == "equal_weight",
        cost_bps=cost_bps,
    )
    ppy = 252 / horizon
    curve = [{"date": str(d), "equity": round(e, 6)} for d, e in result.equity_curve]
    return {
        "periods": len(result.periods),
        "metrics": {
            "total_return": result.total_return,
            "annualized_return": result.annualized_return(ppy),
            "annualized_sharpe": result.annualized_sharpe(ppy),
            "information_ratio": result.information_ratio,
            "excess_hit_rate": result.excess_hit_rate,
            "benchmark_total_return": result.benchmark_total_return,
            "max_drawdown": result.max_drawdown,
            "total_cost": result.total_cost,
        },
        "equity_curve": curve,
        "note": RESEARCH_NOTE,
    }
