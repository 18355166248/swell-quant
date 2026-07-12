from datetime import date

import pytest

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.factors.evaluate import (
    ICSummary,
    PeriodIC,
    evaluate_factor_series,
    sample_as_of_dates,
)
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore


def _period(day, ic, rank_ic=None, n=10):
    return PeriodIC(
        as_of=date(2026, 1, day), ic=ic, rank_ic=rank_ic if rank_ic is not None else ic, n=n
    )


# ---- ICSummary aggregation ----


def test_summary_mean_std_ir_positive_rate():
    summary = ICSummary(per_period=(_period(1, 0.1), _period(2, 0.2), _period(3, 0.3)))
    stats = summary.ic
    assert stats.mean == pytest.approx(0.2)
    assert stats.std == pytest.approx(0.1)  # 样本标准差
    assert stats.ir == pytest.approx(2.0)  # 0.2 / 0.1
    assert stats.positive_rate == pytest.approx(1.0)
    assert stats.n == 3


def test_summary_positive_rate_counts_sign():
    summary = ICSummary(
        per_period=(_period(1, 0.2), _period(2, -0.1), _period(3, 0.1), _period(4, -0.3))
    )
    assert summary.ic.positive_rate == pytest.approx(0.5)


def test_summary_excludes_none_periods():
    summary = ICSummary(per_period=(_period(1, 0.1), _period(2, None), _period(3, 0.3)))
    assert summary.ic.n == 2  # None 期不计入
    assert summary.ic.mean == pytest.approx(0.2)


def test_summary_single_period_std_none():
    summary = ICSummary(per_period=(_period(1, 0.1),))
    assert summary.ic.std is None
    assert summary.ic.ir is None  # 无法算稳定性
    assert summary.ic.mean == pytest.approx(0.1)


def test_summary_empty():
    summary = ICSummary(per_period=())
    assert summary.ic.n == 0
    assert summary.ic.mean is None


# ---- evaluate_factor_series wiring ----


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


def test_evaluate_series_produces_period_per_date(store):
    # 三票几何增长，日收益率 a<b<c → 任意窗口的未来收益都同序，与因子(1<2<3)一致 → 每期 RankIC=1。
    rates = {"a": 0.0, "b": 0.01, "c": 0.02}
    for sym in ("a", "b", "c"):
        store.write_bars([_bar(sym, d, 10.0 * (1 + rates[sym]) ** d) for d in range(1, 8)])
    factor = FakeFactor({"a": 1.0, "b": 2.0, "c": 3.0})
    dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
    summary = evaluate_factor_series(factor, store, ["a", "b", "c"], dates, horizon=2)
    assert len(summary.per_period) == 3
    assert summary.rank_ic.mean == pytest.approx(1.0)  # 每期都同序


# ---- sample_as_of_dates ----


def test_sample_as_of_dates_uses_calendar_step(store):
    days = [date(2026, 1, d) for d in (5, 6, 7, 8, 9)]  # 5 个交易日
    store.write_trade_calendar(days)
    assert sample_as_of_dates(store, date(2026, 1, 1), date(2026, 1, 31), step=2) == [
        date(2026, 1, 5),
        date(2026, 1, 7),
        date(2026, 1, 9),
    ]
    # 非交易日不入选：step=1 返回全部交易日。
    assert sample_as_of_dates(store, date(2026, 1, 1), date(2026, 1, 31)) == days
