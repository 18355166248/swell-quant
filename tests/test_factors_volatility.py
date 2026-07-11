import statistics
from datetime import date

import pytest

from swell_quant.factors.volatility import VolatilityFactor
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore


def _bar(symbol, day, close, adj_factor=1.0):
    return BarRecord(
        symbol=symbol, date=date(2026, 1, day), open=close, high=close, low=close,
        close=close, volume=100, amount=close * 100, adj_factor=adj_factor, source="test",
    )


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_name():
    assert VolatilityFactor(lookback=10).name == "volatility_10d"


def test_volatility_is_stdev_of_daily_returns(store):
    closes = [100.0, 110.0, 99.0, 108.9]  # 收益: +0.1, -0.1, +0.1
    store.write_bars([_bar("600519", i + 1, c) for i, c in enumerate(closes)])
    values = VolatilityFactor(lookback=3).compute(store, ["600519"], as_of=date(2026, 1, 4))
    expected = statistics.stdev([0.1, -0.1, 0.1])
    assert values["600519"] == pytest.approx(expected)


def test_flat_prices_zero_volatility(store):
    store.write_bars([_bar("600519", d, 10.0) for d in (1, 2, 3)])
    values = VolatilityFactor(lookback=2).compute(store, ["600519"], as_of=date(2026, 1, 3))
    assert values["600519"] == pytest.approx(0.0)


def test_uses_hfq_not_raw(store):
    # 除权日 raw 跳空会制造巨大假收益；hfq 连续 → 波动应为 0。
    store.write_bars([
        _bar("600519", 1, 10.0, adj_factor=1.0),
        _bar("600519", 2, 10.0, adj_factor=1.0),
        _bar("600519", 3, 8.0, adj_factor=1.25),  # hfq=10
    ])
    values = VolatilityFactor(lookback=2).compute(store, ["600519"], as_of=date(2026, 1, 3))
    assert values["600519"] == pytest.approx(0.0)


def test_insufficient_history_is_none(store):
    store.write_bars([_bar("600519", 1, 10.0), _bar("600519", 2, 11.0)])  # 仅 1 个收益
    values = VolatilityFactor(lookback=5).compute(store, ["600519"], as_of=date(2026, 1, 2))
    assert values["600519"] is None


def test_cross_section(store):
    # a 波动大、b 波动小。
    store.write_bars([_bar("a", 1, 100.0), _bar("a", 2, 120.0), _bar("a", 3, 100.0)])
    store.write_bars([_bar("b", 1, 100.0), _bar("b", 2, 101.0), _bar("b", 3, 100.0)])
    values = VolatilityFactor(lookback=2).compute(store, ["a", "b"], as_of=date(2026, 1, 3))
    assert values["a"] > values["b"]
