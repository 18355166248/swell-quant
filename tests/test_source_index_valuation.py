from datetime import date

import pytest

from swell_quant.marketdata.source_index_valuation import (
    IndexValuationSourceError,
    fetch_index_valuation_danjuan,
)

# 2020-07-27 与 2020-08-03 的东八区时间戳（毫秒）。
TS1 = 1595779200000  # 2020-07-27 08:00 CST
TS2 = 1596384000000


def _payload(points):
    return {"data": {"index_eva_pe_growths": points}}


def test_fetch_parses_and_sorts():
    got = {}

    def fake_get(url):
        got["url"] = url
        return _payload([{"pe": 44.15, "ts": TS2}, {"pe": 42.29, "ts": TS1}])  # 乱序

    series = fetch_index_valuation_danjuan("HKHSTECH", http_get=fake_get)
    assert "HKHSTECH" in got["url"] and "pe_history" in got["url"]
    assert series == [(date(2020, 7, 27), 42.29), (date(2020, 8, 3), 44.15)]


def test_skips_null_pe():
    series = fetch_index_valuation_danjuan(
        "HKHSTECH",
        http_get=lambda _u: _payload([{"pe": None, "ts": TS1}, {"pe": 42.29, "ts": TS2}]),
    )
    assert len(series) == 1


def test_bad_structure_raises():
    with pytest.raises(IndexValuationSourceError):
        fetch_index_valuation_danjuan("HKHSTECH", http_get=lambda _u: {"oops": 1})


def test_empty_raises():
    with pytest.raises(IndexValuationSourceError):
        fetch_index_valuation_danjuan("HKHSTECH", http_get=lambda _u: _payload([]))
