"""portfolio: 组合构建与回测（综合打分 → Top-N 持仓 → 收益曲线）。"""

from swell_quant.portfolio.construct import equal_weight_top_n, portfolio_return
from swell_quant.portfolio.backtest import (
    BacktestResult,
    PeriodReturn,
    backtest_composite,
    benchmark_return,
)
from swell_quant.portfolio.walkforward import train_ic_weights, walk_forward_backtest

__all__ = [
    "BacktestResult",
    "PeriodReturn",
    "backtest_composite",
    "benchmark_return",
    "equal_weight_top_n",
    "portfolio_return",
    "train_ic_weights",
    "walk_forward_backtest",
]
