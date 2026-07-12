from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from swell_quant.factors.evaluate import forward_returns
from swell_quant.factors.pipeline import FactorPipeline
from swell_quant.marketdata.store import MarketStore
from swell_quant.portfolio.construct import equal_weight_top_n, portfolio_return
from swell_quant.portfolio.stats import annualize_return, annualize_sharpe


@dataclass(frozen=True)
class PeriodReturn:
    as_of: date
    ret: float | None  # 毛收益（未扣成本）
    n_holdings: int
    benchmark_ret: float | None = None
    cost: float = 0.0  # 本期交易成本 = 换手率 × 费率

    @property
    def net_ret(self) -> float | None:
        """净收益 = 毛收益 - 交易成本。"""

        return None if self.ret is None else self.ret - self.cost

    @property
    def excess(self) -> float | None:
        """组合**净**超额收益 = 净收益 - 基准收益（任一缺失则 None）。"""

        if self.net_ret is None or self.benchmark_ret is None:
            return None
        return self.net_ret - self.benchmark_ret


@dataclass(frozen=True)
class BacktestResult:
    """非重叠调仓回测结果：每期组合收益 + 净值曲线 + 汇总指标。"""

    periods: tuple[PeriodReturn, ...]

    def _valid(self) -> list[float]:
        return [p.net_ret for p in self.periods if p.net_ret is not None]

    @property
    def equity_curve(self) -> list[tuple[date, float]]:
        """从 1.0 开始逐期复利的**净**净值序列（扣成本，只计有效期）。"""

        curve: list[tuple[date, float]] = []
        equity = 1.0
        for period in self.periods:
            if period.net_ret is None:
                continue
            equity *= 1.0 + period.net_ret
            curve.append((period.as_of, equity))
        return curve

    @property
    def total_cost(self) -> float:
        """全程累计交易成本（各期成本之和）。"""

        return sum(p.cost for p in self.periods if p.ret is not None)

    @property
    def total_return(self) -> float | None:
        rets = self._valid()
        if not rets:
            return None
        equity = 1.0
        for ret in rets:
            equity *= 1.0 + ret
        return equity - 1.0

    @property
    def mean_return(self) -> float | None:
        rets = self._valid()
        return statistics.fmean(rets) if rets else None

    @property
    def volatility(self) -> float | None:
        rets = self._valid()
        return statistics.stdev(rets) if len(rets) >= 2 else None

    @property
    def sharpe(self) -> float | None:
        """每期夏普（均值/波动，无风险利率取 0，未年化）。"""

        mean, vol = self.mean_return, self.volatility
        return (mean / vol) if (vol is not None and vol != 0) else None

    @property
    def hit_rate(self) -> float | None:
        rets = self._valid()
        return sum(1 for r in rets if r > 0) / len(rets) if rets else None

    def annualized_return(self, periods_per_year: float) -> float | None:
        """年化收益。``periods_per_year`` = 252 / horizon（非重叠调仓的每年期数）。"""

        return annualize_return(self.total_return, len(self._valid()), periods_per_year)

    def annualized_sharpe(self, periods_per_year: float) -> float | None:
        """年化夏普 = 每期夏普 × sqrt(每年期数)。"""

        return annualize_sharpe(self.sharpe, periods_per_year)

    def _valid_excess(self) -> list[float]:
        return [p.excess for p in self.periods if p.excess is not None]

    @property
    def benchmark_total_return(self) -> float | None:
        rets = [p.benchmark_ret for p in self.periods if p.benchmark_ret is not None]
        if not rets:
            return None
        equity = 1.0
        for ret in rets:
            equity *= 1.0 + ret
        return equity - 1.0

    @property
    def excess_mean(self) -> float | None:
        ex = self._valid_excess()
        return statistics.fmean(ex) if ex else None

    @property
    def information_ratio(self) -> float | None:
        """信息比率 = 平均超额收益 / 超额收益波动（每期，未年化）。基准相对表现的核心指标。"""

        ex = self._valid_excess()
        if len(ex) < 2:
            return None
        vol = statistics.stdev(ex)
        return (statistics.fmean(ex) / vol) if vol != 0 else None

    @property
    def excess_hit_rate(self) -> float | None:
        """跑赢基准的期数占比。"""

        ex = self._valid_excess()
        return sum(1 for e in ex if e > 0) / len(ex) if ex else None

    @property
    def max_drawdown(self) -> float | None:
        """净值曲线的最大回撤（负值或 0）。"""

        curve = self.equity_curve
        if not curve:
            return None
        peak = curve[0][1]
        worst = 0.0
        for _, equity in curve:
            peak = max(peak, equity)
            worst = min(worst, equity / peak - 1.0)
        return worst


def benchmark_return(
    store: MarketStore, index_code: str, as_of: date, horizon: int
) -> float | None:
    """基准指数在 [as_of, as_of+horizon] 的收益（前视，用于回测对照）。前视根数不足则 None。"""

    bars = store.get_index_bar_forward(index_code, as_of, horizon)
    if len(bars) < horizon + 1:
        return None
    start_close = bars[0].close
    return (bars[-1].close / start_close - 1) if start_close else None


def equal_weight_universe_return(
    store: MarketStore, symbols: Sequence[str], as_of: date, horizon: int
) -> float | None:
    """**等权持有全池**在持有期的收益 = 池内各票未来收益的均值。

    作为对照基准，它与因子组合**同池、同为等权**，故组合相对它的超额只能来自
    因子选股，剥离了“等权 vs 市值加权”的结构性 tilt（见 docs 结论）。无可用收益则 None。
    """

    rets = forward_returns(store, symbols, as_of, horizon)
    present = [r for r in rets.values() if r is not None]
    return statistics.fmean(present) if present else None


def _benchmark(
    store: MarketStore,
    symbols: Sequence[str],
    as_of: date,
    horizon: int,
    benchmark_index: str | None,
    equal_weight_benchmark: bool,
) -> float | None:
    if equal_weight_benchmark:
        return equal_weight_universe_return(store, symbols, as_of, horizon)
    if benchmark_index:
        return benchmark_return(store, benchmark_index, as_of, horizon)
    return None


def _turnover(prev: dict[str, float], new: dict[str, float]) -> float:
    """单边换手率 = Σ|w_new - w_prev|（并集）。首期 prev 为空 → 等于建仓的 Σw_new。"""

    return sum(abs(new.get(s, 0.0) - prev.get(s, 0.0)) for s in set(prev) | set(new))


def backtest_composite(
    pipeline: FactorPipeline,
    store: MarketStore,
    symbols: Sequence[str],
    rebalance_dates: Sequence[date],
    top_n: int,
    horizon: int = 20,
    benchmark_index: str | None = None,
    equal_weight_benchmark: bool = False,
    cost_bps: float = 0.0,
) -> BacktestResult:
    """在每个调仓日：综合打分 → Top-N 等权 → 持有 horizon 日 → 记录组合收益。

    ``rebalance_dates`` 应按 horizon 间隔取（非重叠持有），一般用
    ``sample_as_of_dates(store, ..., step=horizon)`` 生成，避免持有期重叠。
    基准二选一：``equal_weight_benchmark=True`` 用**等权全池**（剥离等权 tilt，纯看因子
    选股超额）；否则 ``benchmark_index``（如 "sh000300"，市值加权指数）。
    ``cost_bps`` 为单边费率（基点）：每期成本 = 换手率 × cost_bps/10000，从毛收益扣除。
    """

    cost_rate = cost_bps / 10000.0
    prev_weights: dict[str, float] = {}
    periods: list[PeriodReturn] = []
    for as_of in rebalance_dates:
        scores = pipeline.compute(store, symbols, as_of)
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
        # 建仓后即持有到期末再换仓；下期以本期权重为基准算换手。
        prev_weights = weights
    return BacktestResult(periods=tuple(periods))
