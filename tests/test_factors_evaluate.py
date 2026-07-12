from datetime import date

import pytest

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.factors.evaluate import (
    ICResult,
    evaluate_factor,
    forward_returns,
    information_coefficient,
    rank_ic,
)
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore


def _bar(symbol, day, close, adj_factor=1.0):
    return BarRecord(
        symbol=symbol,
        date=date(2026, 1, day),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100,
        amount=close * 100,
        adj_factor=adj_factor,
        source="test",
    )


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


# ---- forward_returns ----


def test_forward_return_over_horizon(store):
    store.write_bars([_bar("600519", d, 10.0 + d) for d in (1, 2, 3, 4, 5)])
    # as_of=d1, horizon=2 → 起 close(d1)=11, 终 close(d3)=13。
    fr = forward_returns(store, ["600519"], as_of=date(2026, 1, 1), horizon=2)
    assert fr["600519"] == pytest.approx(13.0 / 11.0 - 1)


def test_forward_return_uses_hfq(store):
    # 未来除权：raw 在 d3 跳空，但 hfq 连续。
    store.write_bars(
        [
            _bar("600519", 1, 10.0, adj_factor=1.0),
            _bar("600519", 2, 10.0, adj_factor=1.0),
            _bar("600519", 3, 8.0, adj_factor=1.25),  # hfq=10
        ]
    )
    fr = forward_returns(store, ["600519"], as_of=date(2026, 1, 1), horizon=2)
    assert fr["600519"] == pytest.approx(0.0)  # hfq 10 → 10


def test_forward_return_insufficient_future_is_none(store):
    store.write_bars([_bar("600519", 1, 10.0), _bar("600519", 2, 11.0)])
    fr = forward_returns(store, ["600519"], as_of=date(2026, 1, 1), horizon=5)
    assert fr["600519"] is None


# ---- IC / RankIC ----


def test_ic_perfect_positive():
    fv = {"a": 1.0, "b": 2.0, "c": 3.0}
    ret = {"a": 0.1, "b": 0.2, "c": 0.3}  # 完全正相关
    assert information_coefficient(fv, ret) == pytest.approx(1.0)


def test_ic_perfect_negative():
    fv = {"a": 1.0, "b": 2.0, "c": 3.0}
    ret = {"a": 0.3, "b": 0.2, "c": 0.1}
    assert information_coefficient(fv, ret) == pytest.approx(-1.0)


def test_rank_ic_monotonic_is_one():
    fv = {"a": 1.0, "b": 2.0, "c": 3.0}
    ret = {"a": 0.05, "b": 0.9, "c": 1.0}  # 非线性但同序 → RankIC=1
    assert rank_ic(fv, ret) == pytest.approx(1.0)
    assert information_coefficient(fv, ret) < 1.0  # 皮尔逊 < 1


def test_none_pairs_excluded():
    fv = {"a": 1.0, "b": 2.0, "c": 3.0, "d": None}
    ret = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4}
    assert information_coefficient(fv, ret) == pytest.approx(1.0)  # d 被排除，不影响


def test_too_few_points_is_none():
    assert information_coefficient({"a": 1.0}, {"a": 0.1}) is None


def test_no_dispersion_is_none():
    # 因子值全相同 → 方差 0 → 相关无定义。
    assert information_coefficient({"a": 5.0, "b": 5.0}, {"a": 0.1, "b": 0.2}) is None


# ---- evaluate_factor ----


class FakeFactor(Factor):
    def __init__(self, values):
        self._values = values

    @property
    def name(self):
        return "fake"

    def compute(self, store, symbols, as_of) -> FactorValues:
        return {s: self._values.get(s) for s in symbols}


def test_evaluate_factor_end_to_end(store):
    # 三票，因子值与未来收益同序 → RankIC 应为 1。
    for sym, base in [("a", 10.0), ("b", 20.0), ("c", 30.0)]:
        # a 未来涨最少、c 最多。
        growth = {"a": 0.0, "b": 0.05, "c": 0.10}[sym]
        store.write_bars(
            [_bar(sym, 1, base), _bar(sym, 2, base), _bar(sym, 3, base * (1 + growth))]
        )
    factor = FakeFactor({"a": 1.0, "b": 2.0, "c": 3.0})
    result = evaluate_factor(factor, store, ["a", "b", "c"], as_of=date(2026, 1, 1), horizon=2)
    assert isinstance(result, ICResult)
    assert result.n == 3
    assert result.rank_ic == pytest.approx(1.0)
    assert result.ic == pytest.approx(1.0)
