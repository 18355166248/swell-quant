import math
from datetime import date

import pytest

from swell_quant.portfolio.backtest import BacktestResult, PeriodReturn
from swell_quant.portfolio.stats import annualize_return, annualize_sharpe


def test_annualize_return_compounds():
    # 6 期翻倍(total=1.0)、每年 12 期 → 2^(12/6)-1 = 3.0。
    assert annualize_return(1.0, 6, 12) == pytest.approx(3.0)


def test_annualize_return_guards():
    assert annualize_return(None, 6, 12) is None
    assert annualize_return(0.5, 0, 12) is None
    assert annualize_return(-1.0, 6, 12) == -1.0  # 本金亏尽


def test_annualize_sharpe_scales_by_sqrt():
    assert annualize_sharpe(0.5, 12) == pytest.approx(0.5 * math.sqrt(12))
    assert annualize_sharpe(None, 12) is None


def test_backtest_result_annualized_methods():
    periods = tuple(
        PeriodReturn(as_of=date(2026, 1, i + 1), ret=r, n_holdings=3)
        for i, r in enumerate([0.1, -0.05, 0.2])
    )
    result = BacktestResult(periods=periods)
    # 年化收益应与直接用 total_return 年化一致。
    assert result.annualized_return(12) == pytest.approx(
        annualize_return(result.total_return, 3, 12)
    )
    assert result.annualized_sharpe(12) == pytest.approx(result.sharpe * math.sqrt(12))


def test_annualized_none_when_empty():
    result = BacktestResult(periods=(PeriodReturn(date(2026, 1, 1), None, 0),))
    assert result.annualized_return(12) is None
    assert result.annualized_sharpe(12) is None
