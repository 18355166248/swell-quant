import statistics
from datetime import date

import pytest

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.factors.pipeline import FactorPipeline, FactorWeight
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore
from swell_quant.portfolio.backtest import BacktestResult, PeriodReturn, backtest_composite


# ---- BacktestResult metrics ----

def _periods(*rets):
    return tuple(PeriodReturn(as_of=date(2026, 1, i + 1), ret=r, n_holdings=3) for i, r in enumerate(rets))


def test_equity_curve_and_total_return():
    result = BacktestResult(periods=_periods(0.1, -0.05, 0.2))
    curve = result.equity_curve
    assert curve[-1][1] == pytest.approx(1.1 * 0.95 * 1.2)
    assert result.total_return == pytest.approx(1.1 * 0.95 * 1.2 - 1)


def test_metrics_hit_rate_vol_sharpe():
    result = BacktestResult(periods=_periods(0.1, -0.05, 0.2))
    assert result.hit_rate == pytest.approx(2 / 3)
    assert result.volatility == pytest.approx(statistics.stdev([0.1, -0.05, 0.2]))
    assert result.sharpe == pytest.approx(result.mean_return / result.volatility)


def test_max_drawdown():
    # 净值 1.1 → 0.88 → ... 回撤从峰值 1.1 到 0.88*... 计算最大回撤。
    result = BacktestResult(periods=_periods(0.1, -0.2, 0.05))
    # equity: 1.1, 0.88, 0.924；峰值 1.1，谷 0.88 → dd = 0.88/1.1 - 1 = -0.2
    assert result.max_drawdown == pytest.approx(-0.2)


def test_none_periods_excluded_from_metrics():
    result = BacktestResult(periods=_periods(0.1, None, 0.2))
    assert len(result.equity_curve) == 2
    assert result.total_return == pytest.approx(1.1 * 1.2 - 1)


def test_empty_metrics_are_none():
    result = BacktestResult(periods=_periods(None, None))
    assert result.total_return is None
    assert result.max_drawdown is None
    assert result.sharpe is None


# ---- backtest_composite end to end ----

def _bar(symbol, day, close):
    return BarRecord(
        symbol=symbol, date=date(2026, 1, day), open=close, high=close, low=close,
        close=close, volume=100, amount=close * 100, adj_factor=1.0, source="test",
    )


class FakeFactor(Factor):
    def __init__(self, values):
        self._values = values

    @property
    def name(self):
        return "fake"

    def compute(self, store, symbols, as_of) -> FactorValues:
        return {s: self._values.get(s) for s in symbols}


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_backtest_selects_top_and_measures_forward_return(store):
    # 因子分 c>b>a。未来 2 日：c 涨 10%，b 涨 5%，a 跌。top_n=1 → 应只买 c、拿 c 的收益。
    store.write_bars([_bar("a", d, 10.0 * (1 - 0.01) ** d) for d in range(1, 6)])
    store.write_bars([_bar("b", d, 10.0 * (1 + 0.025) ** d) for d in range(1, 6)])
    store.write_bars([_bar("c", d, 10.0 * (1 + 0.05) ** d) for d in range(1, 6)])
    pipe = FactorPipeline(weights=(FactorWeight(FakeFactor({"a": 1.0, "b": 2.0, "c": 3.0})),))
    result = backtest_composite(pipe, store, ["a", "b", "c"], [date(2026, 1, 1)], top_n=1, horizon=2)
    assert result.periods[0].n_holdings == 1
    # 持有 c 两日：(1.05^3)/(1.05^1) - 1 = 1.05^2 - 1
    assert result.periods[0].ret == pytest.approx(1.05 ** 2 - 1)


def test_backtest_multiple_rebalances(store):
    for sym, rate in [("a", 0.0), ("b", 0.03)]:
        store.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 8)])
    pipe = FactorPipeline(weights=(FactorWeight(FakeFactor({"a": 1.0, "b": 2.0})),))
    result = backtest_composite(pipe, store, ["a", "b"], [date(2026, 1, 1), date(2026, 1, 3)], top_n=1, horizon=2)
    assert len(result.periods) == 2
    assert all(p.ret is not None for p in result.periods)  # 两期都买到 b、都有收益


# ---- benchmark-relative ----

def test_period_excess():
    from swell_quant.portfolio.backtest import PeriodReturn as PR
    assert PR(as_of=date(2026, 1, 1), ret=0.10, n_holdings=3, benchmark_ret=0.04).excess == pytest.approx(0.06)
    assert PR(as_of=date(2026, 1, 1), ret=0.10, n_holdings=3).excess is None  # 无基准


def test_benchmark_metrics():
    periods = (
        PeriodReturn(date(2026, 1, 1), 0.10, 3, benchmark_ret=0.05),   # 超额 +0.05
        PeriodReturn(date(2026, 1, 2), -0.02, 3, benchmark_ret=0.01),  # 超额 -0.03
        PeriodReturn(date(2026, 1, 3), 0.08, 3, benchmark_ret=0.02),   # 超额 +0.06
    )
    r = BacktestResult(periods=periods)
    excess = [0.05, -0.03, 0.06]
    assert r.excess_mean == pytest.approx(statistics.fmean(excess))
    assert r.excess_hit_rate == pytest.approx(2 / 3)
    assert r.information_ratio == pytest.approx(statistics.fmean(excess) / statistics.stdev(excess))
    assert r.benchmark_total_return == pytest.approx(1.05 * 1.01 * 1.02 - 1)


def test_backtest_with_benchmark_index(store):
    for sym, rate in [("a", 0.0), ("b", 0.03)]:
        store.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 6)])
    # 基准指数：温和上涨。
    from swell_quant.marketdata.records import IndexBarRecord
    store.write_index_bars([
        IndexBarRecord(index_code="sh000300", date=date(2026, 1, d), close=100.0 * (1 + 0.01) ** d, source="t")
        for d in range(1, 6)
    ])
    pipe = FactorPipeline(weights=(FactorWeight(FakeFactor({"a": 1.0, "b": 2.0})),))
    result = backtest_composite(
        pipe, store, ["a", "b"], [date(2026, 1, 1)], top_n=1, horizon=2, benchmark_index="sh000300"
    )
    p = result.periods[0]
    assert p.benchmark_ret == pytest.approx(1.01 ** 2 - 1)  # 基准 2 日收益
    assert p.excess == pytest.approx(p.ret - p.benchmark_ret)
