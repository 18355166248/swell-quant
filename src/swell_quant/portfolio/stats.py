from __future__ import annotations

import math

# 年化工具（从旧 research/backtest.py 抢救、重新理解后移植）。
# 本回测按 horizon 交易日非重叠调仓，故每年期数 periods_per_year = 252 / horizon。


def annualize_return(
    total_return: float | None, n_periods: int, periods_per_year: float
) -> float | None:
    """把 n 期累计收益年化：``(1+total)^(每年期数/期数) - 1``。

    n_periods<=0 返回 None；若净值已归零/为负（total<=-1）返回 -1.0（本金亏尽）。
    """

    if total_return is None or n_periods <= 0:
        return None
    final_equity = 1.0 + total_return
    if final_equity <= 0:
        return -1.0
    return final_equity ** (periods_per_year / n_periods) - 1.0


def annualize_sharpe(
    per_period_sharpe: float | None, periods_per_year: float
) -> float | None:
    """把每期夏普年化：``sharpe * sqrt(每年期数)``（无风险利率取 0）。"""

    if per_period_sharpe is None:
        return None
    return per_period_sharpe * math.sqrt(periods_per_year)
