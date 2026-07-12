from datetime import date

import pytest

from swell_quant.factors.reversal import ReversalFactor
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore


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


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_name():
    assert ReversalFactor(lookback=5).name == "reversal_5d"


def test_reversal_is_negative_of_return(store):
    # lookback=2：涨了的票 → 负分（不买）；跌了的票 → 正分（买）。
    store.write_bars([_bar("up", d, c) for d, c in [(1, 10.0), (2, 11.0), (3, 12.0)]])
    store.write_bars([_bar("down", d, c) for d, c in [(1, 12.0), (2, 11.0), (3, 9.6)]])
    values = ReversalFactor(lookback=2).compute(store, ["up", "down"], as_of=date(2026, 1, 3))
    assert values["up"] == pytest.approx(-(12.0 / 10.0 - 1))  # 负
    assert values["down"] == pytest.approx(-(9.6 / 12.0 - 1))  # 正
    assert values["down"] > 0 > values["up"]


def test_insufficient_history_none(store):
    store.write_bars([_bar("a", 1, 10.0), _bar("a", 2, 11.0)])
    assert ReversalFactor(lookback=2).compute(store, ["a"], as_of=date(2026, 1, 2))["a"] is None


def test_as_of_excludes_future(store):
    store.write_bars([_bar("a", d, 10.0 + d) for d in (1, 2, 3, 4, 5)])
    values = ReversalFactor(lookback=2).compute(store, ["a"], as_of=date(2026, 1, 3))
    assert values["a"] == pytest.approx(-(13.0 / 11.0 - 1))  # 用 d1..d3
