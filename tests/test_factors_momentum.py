from datetime import date

import pytest

from swell_quant.factors import MomentumFactor
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


def test_name():
    assert MomentumFactor(lookback=5).name == "momentum_5d"


def test_momentum_uses_hfq_return_over_window(store):
    # lookback=2 → 需要 3 根：d1..d3。收益 = close[d3]/close[d1] - 1。
    store.write_bars([_bar("600519", 1, 10.0), _bar("600519", 2, 11.0), _bar("600519", 3, 12.0)])
    values = MomentumFactor(lookback=2).compute(store, ["600519"], as_of=date(2026, 1, 3))
    assert values["600519"] == pytest.approx(12.0 / 10.0 - 1)


def test_momentum_uses_adjusted_close_not_raw(store):
    # raw 收盘在 d3 除权跳空(12→9.6)，但因子抬到 1.25 → hfq 连续。
    # hfq: d1=10, d3=9.6*1.25=12 → 动量按后复权算，不受除权干扰。
    store.write_bars([
        _bar("600519", 1, 10.0, adj_factor=1.0),
        _bar("600519", 2, 11.0, adj_factor=1.0),
        _bar("600519", 3, 9.6, adj_factor=1.25),
    ])
    values = MomentumFactor(lookback=2).compute(store, ["600519"], as_of=date(2026, 1, 3))
    assert values["600519"] == pytest.approx(12.0 / 10.0 - 1)


def test_insufficient_history_is_none(store):
    store.write_bars([_bar("600519", 1, 10.0), _bar("600519", 2, 11.0)])  # 只有 2 根
    values = MomentumFactor(lookback=2).compute(store, ["600519"], as_of=date(2026, 1, 2))
    assert values["600519"] is None


def test_as_of_excludes_future_bars(store):
    store.write_bars([_bar("600519", d, 10.0 + d) for d in (1, 2, 3, 4, 5)])
    # as_of=d3，lookback=2 → 用 d1..d3，不看 d4/d5。
    values = MomentumFactor(lookback=2).compute(store, ["600519"], as_of=date(2026, 1, 3))
    assert values["600519"] == pytest.approx(13.0 / 11.0 - 1)


def test_cross_section_multiple_symbols(store):
    store.write_bars(
        [_bar("600519", d, 10.0 + d) for d in (1, 2, 3)]
        + [_bar("000001", d, 20.0) for d in (1, 2, 3)]  # 无涨跌 → 0
        + [_bar("300750", 3, 5.0)]  # 历史不足 → None
    )
    values = MomentumFactor(lookback=2).compute(
        store, ["600519", "000001", "300750"], as_of=date(2026, 1, 3)
    )
    assert values["600519"] == pytest.approx(13.0 / 11.0 - 1)
    assert values["000001"] == pytest.approx(0.0)
    assert values["300750"] is None
