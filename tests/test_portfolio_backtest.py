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
    return tuple(
        PeriodReturn(as_of=date(2026, 1, i + 1), ret=r, n_holdings=3) for i, r in enumerate(rets)
    )


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
        symbol=symbol,
        date=date(2026, 1, day),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100,
        amount=close * 100,
        adj_factor=1.0,
        source="test",
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
    result = backtest_composite(
        pipe, store, ["a", "b", "c"], [date(2026, 1, 1)], top_n=1, horizon=2
    )
    assert result.periods[0].n_holdings == 1
    # 持有 c 两日：(1.05^3)/(1.05^1) - 1 = 1.05^2 - 1
    assert result.periods[0].ret == pytest.approx(1.05**2 - 1)


def test_backtest_multiple_rebalances(store):
    for sym, rate in [("a", 0.0), ("b", 0.03)]:
        store.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 8)])
    pipe = FactorPipeline(weights=(FactorWeight(FakeFactor({"a": 1.0, "b": 2.0})),))
    result = backtest_composite(
        pipe, store, ["a", "b"], [date(2026, 1, 1), date(2026, 1, 3)], top_n=1, horizon=2
    )
    assert len(result.periods) == 2
    assert all(p.ret is not None for p in result.periods)  # 两期都买到 b、都有收益


# ---- benchmark-relative ----


def test_period_excess():
    from swell_quant.portfolio.backtest import PeriodReturn as PR

    assert PR(
        as_of=date(2026, 1, 1), ret=0.10, n_holdings=3, benchmark_ret=0.04
    ).excess == pytest.approx(0.06)
    assert PR(as_of=date(2026, 1, 1), ret=0.10, n_holdings=3).excess is None  # 无基准


def test_benchmark_metrics():
    periods = (
        PeriodReturn(date(2026, 1, 1), 0.10, 3, benchmark_ret=0.05),  # 超额 +0.05
        PeriodReturn(date(2026, 1, 2), -0.02, 3, benchmark_ret=0.01),  # 超额 -0.03
        PeriodReturn(date(2026, 1, 3), 0.08, 3, benchmark_ret=0.02),  # 超额 +0.06
    )
    r = BacktestResult(periods=periods)
    excess = [0.05, -0.03, 0.06]
    assert r.excess_mean == pytest.approx(statistics.fmean(excess))
    assert r.excess_hit_rate == pytest.approx(2 / 3)
    assert r.information_ratio == pytest.approx(statistics.fmean(excess) / statistics.stdev(excess))
    assert r.benchmark_total_return == pytest.approx(1.05 * 1.01 * 1.02 - 1)


# ---- transaction costs ----


def test_net_ret_and_metrics_use_net():
    p = PeriodReturn(date(2026, 1, 1), ret=0.10, n_holdings=3, cost=0.02)
    assert p.net_ret == pytest.approx(0.08)
    result = BacktestResult(periods=(p,))
    assert result.total_return == pytest.approx(0.08)  # 用净收益
    assert result.total_cost == pytest.approx(0.02)


def test_excess_uses_net_ret():
    p = PeriodReturn(date(2026, 1, 1), ret=0.10, n_holdings=3, benchmark_ret=0.05, cost=0.02)
    assert p.excess == pytest.approx(0.08 - 0.05)  # (0.10-0.02) - 0.05


def test_cost_charged_on_turnover(store):
    # 两期分别持有不同的单只票 → 第2期换手=2.0（卖旧买新）。
    for sym, rate in [("a", 0.02), ("b", 0.04)]:
        store.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 8)])

    # 因子让第1期选 a、第2期选 b。
    class SwitchFactor(Factor):
        @property
        def name(self):
            return "switch"

        def compute(self, store, symbols, as_of):
            first = as_of == date(2026, 1, 1)
            return {"a": (2.0 if first else 1.0), "b": (1.0 if first else 2.0)}

    pipe = FactorPipeline(weights=(FactorWeight(SwitchFactor()),))
    result = backtest_composite(
        pipe,
        store,
        ["a", "b"],
        [date(2026, 1, 1), date(2026, 1, 3)],
        top_n=1,
        horizon=2,
        cost_bps=10,
    )
    # 第1期建仓：换手 1.0 → cost 0.001；第2期全换：换手 2.0 → cost 0.002。
    assert result.periods[0].cost == pytest.approx(0.001)
    assert result.periods[1].cost == pytest.approx(0.002)


def test_no_turnover_no_cost(store):
    # 两期都持有同一只票 → 第2期换手 0 → 无成本。
    store.write_bars([_bar("a", d, 10.0 * 1.01**d) for d in range(1, 8)])
    store.write_bars([_bar("b", d, 10.0) for d in range(1, 8)])
    pipe = FactorPipeline(weights=(FactorWeight(FakeFactor({"a": 2.0, "b": 1.0})),))
    result = backtest_composite(
        pipe,
        store,
        ["a", "b"],
        [date(2026, 1, 1), date(2026, 1, 3)],
        top_n=1,
        horizon=2,
        cost_bps=10,
    )
    assert result.periods[0].cost == pytest.approx(0.001)  # 建仓
    assert result.periods[1].cost == pytest.approx(0.0)  # 未换仓


def test_cost_zero_preserves_gross(store):
    store.write_bars([_bar("a", d, 10.0 * 1.05**d) for d in range(1, 6)])
    pipe = FactorPipeline(weights=(FactorWeight(FakeFactor({"a": 1.0})),))
    result = backtest_composite(pipe, store, ["a"], [date(2026, 1, 1)], top_n=1, horizon=2)
    assert result.periods[0].cost == 0.0
    assert result.periods[0].net_ret == result.periods[0].ret


# ---- equal-weight universe benchmark ----


def test_equal_weight_universe_return_is_mean(store):
    from swell_quant.portfolio.backtest import equal_weight_universe_return

    # 三票 2 日收益 (1+r)^2-1，等权全池 = 三者均值。
    for sym, rate in [("a", 0.0), ("b", 0.05), ("c", 0.10)]:
        store.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 5)])
    ew = equal_weight_universe_return(store, ["a", "b", "c"], date(2026, 1, 1), horizon=2)
    expected = statistics.fmean([(1 + r) ** 2 - 1 for r in (0.0, 0.05, 0.10)])
    assert ew == pytest.approx(expected)


def test_backtest_equal_weight_benchmark_isolates_selection(store):
    # top1 选到最强的 c；等权全池基准 = 三票均值 → 超额 = c 收益 - 均值 > 0。
    for sym, rate in [("a", 0.0), ("b", 0.05), ("c", 0.10)]:
        store.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 5)])
    pipe = FactorPipeline(weights=(FactorWeight(FakeFactor({"a": 1.0, "b": 2.0, "c": 3.0})),))
    result = backtest_composite(
        pipe,
        store,
        ["a", "b", "c"],
        [date(2026, 1, 1)],
        top_n=1,
        horizon=2,
        equal_weight_benchmark=True,
    )
    p = result.periods[0]
    c_ret = (1.10) ** 2 - 1
    ew = statistics.fmean([(1 + r) ** 2 - 1 for r in (0.0, 0.05, 0.10)])
    assert p.benchmark_ret == pytest.approx(ew)
    assert p.excess == pytest.approx(c_ret - ew)
    assert p.excess > 0  # 选股确实带来超额


def test_no_skill_selection_has_zero_excess_vs_equal_weight(store):
    # top_n = 全池 → 组合==等权全池 → 相对等权基准超额恒为 0（剥离选股后无 tilt）。
    for sym, rate in [("a", 0.0), ("b", 0.05), ("c", 0.10)]:
        store.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 5)])
    pipe = FactorPipeline(weights=(FactorWeight(FakeFactor({"a": 1.0, "b": 2.0, "c": 3.0})),))
    result = backtest_composite(
        pipe,
        store,
        ["a", "b", "c"],
        [date(2026, 1, 1)],
        top_n=3,
        horizon=2,
        equal_weight_benchmark=True,
    )
    assert result.periods[0].excess == pytest.approx(0.0)


def test_backtest_with_benchmark_index(store):
    for sym, rate in [("a", 0.0), ("b", 0.03)]:
        store.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 6)])
    # 基准指数：温和上涨。
    from swell_quant.marketdata.records import IndexBarRecord

    store.write_index_bars(
        [
            IndexBarRecord(
                index_code="sh000300",
                date=date(2026, 1, d),
                close=100.0 * (1 + 0.01) ** d,
                source="t",
            )
            for d in range(1, 6)
        ]
    )
    pipe = FactorPipeline(weights=(FactorWeight(FakeFactor({"a": 1.0, "b": 2.0})),))
    result = backtest_composite(
        pipe, store, ["a", "b"], [date(2026, 1, 1)], top_n=1, horizon=2, benchmark_index="sh000300"
    )
    p = result.periods[0]
    assert p.benchmark_ret == pytest.approx(1.01**2 - 1)  # 基准 2 日收益
    assert p.excess == pytest.approx(p.ret - p.benchmark_ret)
