from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from swell_quant.factors.evaluate import forward_returns
from swell_quant.factors.pipeline import FactorPipeline
from swell_quant.marketdata.store import MarketStore
from swell_quant.portfolio.construct import equal_weight_top_n, portfolio_return


@dataclass(frozen=True)
class PeriodReturn:
    as_of: date
    ret: float | None
    n_holdings: int
    benchmark_ret: float | None = None

    @property
    def excess(self) -> float | None:
        """组合超额收益 = 组合收益 - 基准收益（任一缺失则 None）。"""

        if self.ret is None or self.benchmark_ret is None:
            return None
        return self.ret - self.benchmark_ret


@dataclass(frozen=True)
class BacktestResult:
    """非重叠调仓回测结果：每期组合收益 + 净值曲线 + 汇总指标。"""

    periods: tuple[PeriodReturn, ...]

    def _valid(self) -> list[float]:
        return [p.ret for p in self.periods if p.ret is not None]

    @property
    def equity_curve(self) -> list[tuple[date, float]]:
        """从 1.0 开始逐期复利的净值序列（只计有效期）。"""

        curve: list[tuple[date, float]] = []
        equity = 1.0
        for period in self.periods:
            if period.ret is None:
                continue
            equity *= 1.0 + period.ret
            curve.append((period.as_of, equity))
        return curve

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


def backtest_composite(
    pipeline: FactorPipeline,
    store: MarketStore,
    symbols: Sequence[str],
    rebalance_dates: Sequence[date],
    top_n: int,
    horizon: int = 20,
    benchmark_index: str | None = None,
) -> BacktestResult:
    """在每个调仓日：综合打分 → Top-N 等权 → 持有 horizon 日 → 记录组合收益。

    ``rebalance_dates`` 应按 horizon 间隔取（非重叠持有），一般用
    ``sample_as_of_dates(store, ..., step=horizon)`` 生成，避免持有期重叠。
    传 ``benchmark_index``（如 "sh000300"）则同时记录基准收益，可算超额/信息比率。
    """

    periods: list[PeriodReturn] = []
    for as_of in rebalance_dates:
        scores = pipeline.compute(store, symbols, as_of)
        weights = equal_weight_top_n(scores, top_n)
        rets = forward_returns(store, list(weights), as_of, horizon)
        period_ret = portfolio_return(weights, rets) if weights else None
        bench = (
            benchmark_return(store, benchmark_index, as_of, horizon)
            if benchmark_index
            else None
        )
        periods.append(
            PeriodReturn(
                as_of=as_of, ret=period_ret, n_holdings=len(weights), benchmark_ret=bench
            )
        )
    return BacktestResult(periods=tuple(periods))
