from datetime import date

import pytest

from swell_quant.factors.quality import QualityFactor
from swell_quant.marketdata.records import FundamentalRecord
from swell_quant.marketdata.store import MarketStore


def _fund(symbol, event, knowledge, item, value):
    return FundamentalRecord(
        symbol=symbol, event_date=date(*event), knowledge_date=date(*knowledge),
        item=item, value=value, source="test",
    )


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_name():
    assert QualityFactor(item="roe").name == "quality_roe"


def test_reads_latest_roe(store):
    store.write_fundamentals([_fund("600519", (2024, 3, 31), (2024, 4, 30), "roe", 10.5)])
    values = QualityFactor(item="roe").compute(store, ["600519"], as_of=date(2024, 12, 31))
    assert values["600519"] == pytest.approx(10.5)


def test_pit_hides_not_yet_disclosed(store):
    # Q1 ROE 于法定披露日 4/30 才可知。
    store.write_fundamentals([_fund("600519", (2024, 3, 31), (2024, 4, 30), "roe", 10.5)])
    before = QualityFactor("roe").compute(store, ["600519"], as_of=date(2024, 4, 1))
    after = QualityFactor("roe").compute(store, ["600519"], as_of=date(2024, 5, 1))
    assert before["600519"] is None  # 披露前不可见
    assert after["600519"] == pytest.approx(10.5)


def test_uses_latest_reported_period(store):
    store.write_fundamentals([
        _fund("600519", (2024, 3, 31), (2024, 4, 30), "roe", 10.0),
        _fund("600519", (2024, 6, 30), (2024, 8, 31), "roe", 22.0),
    ])
    # as_of 9/1 → 最新报告期是半年报。
    values = QualityFactor("roe").compute(store, ["600519"], as_of=date(2024, 9, 1))
    assert values["600519"] == pytest.approx(22.0)


def test_missing_and_item_selection(store):
    store.write_fundamentals([
        _fund("600519", (2024, 3, 31), (2024, 4, 30), "roe", 10.0),
        _fund("600519", (2024, 3, 31), (2024, 4, 30), "net_profit_yoy", 15.0),
    ])
    values = QualityFactor("net_profit_yoy").compute(
        store, ["600519", "000001"], as_of=date(2024, 12, 31)
    )
    assert values["600519"] == pytest.approx(15.0)
    assert values["000001"] is None
