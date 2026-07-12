from datetime import date

import pytest

from swell_quant.factors import ValueFactor
from swell_quant.marketdata.records import ValuationRecord
from swell_quant.marketdata.store import MarketStore


def _val(symbol, day, item, value):
    return ValuationRecord(
        symbol=symbol, date=date(2026, 1, day), item=item, value=value, source="test"
    )


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_name():
    assert ValueFactor(item="pb").name == "value_pb"


def test_inverts_pe_to_earnings_yield(store):
    store.write_valuations([_val("600519", 1, "pe_ttm", 20.0)])
    values = ValueFactor(item="pe_ttm").compute(store, ["600519"], as_of=date(2026, 1, 31))
    assert values["600519"] == pytest.approx(1 / 20.0)


def test_invert_false_returns_raw(store):
    store.write_valuations([_val("600519", 1, "pb", 5.0)])
    values = ValueFactor(item="pb", invert=False).compute(
        store, ["600519"], as_of=date(2026, 1, 31)
    )
    assert values["600519"] == pytest.approx(5.0)


def test_negative_pe_is_none(store):
    # 亏损股 PE<0，倒数含义不干净 → None，不污染排序。
    store.write_valuations([_val("600519", 1, "pe_ttm", -12.0)])
    values = ValueFactor(item="pe_ttm").compute(store, ["600519"], as_of=date(2026, 1, 31))
    assert values["600519"] is None


def test_missing_symbol_is_none(store):
    store.write_valuations([_val("600519", 1, "pe_ttm", 20.0)])
    values = ValueFactor(item="pe_ttm").compute(
        store, ["600519", "000001"], as_of=date(2026, 1, 31)
    )
    assert values["600519"] == pytest.approx(1 / 20.0)
    assert values["000001"] is None


def test_uses_latest_value_as_of(store):
    store.write_valuations([_val("600519", d, "pe_ttm", 10.0 + d) for d in (1, 2, 3)])
    # as_of=d2 → 用 d2 的 PE=12，不看 d3。
    values = ValueFactor(item="pe_ttm").compute(store, ["600519"], as_of=date(2026, 1, 2))
    assert values["600519"] == pytest.approx(1 / 12.0)


def test_selects_correct_item(store):
    store.write_valuations([_val("600519", 1, "pe_ttm", 20.0), _val("600519", 1, "pb", 5.0)])
    pb = ValueFactor(item="pb").compute(store, ["600519"], as_of=date(2026, 1, 31))
    assert pb["600519"] == pytest.approx(1 / 5.0)
