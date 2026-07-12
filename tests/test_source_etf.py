from datetime import date

import pytest

from swell_quant.marketdata.source_etf import EtfSourceError, etf_sina_symbol, fetch_etf_bars_sina


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        return self.rows


class FakeProvider:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def fund_etf_hist_sina(self, symbol):
        self.calls.append(symbol)
        return FakeFrame(self.rows)


def test_symbol_prefix():
    assert etf_sina_symbol("513260") == "sh513260"
    assert etf_sina_symbol("159915") == "sz159915"
    with pytest.raises(ValueError):
        etf_sina_symbol("300750")


def test_fetch_sorts_and_maps():
    provider = FakeProvider(
        [
            {"date": "2022-01-03", "close": 1.02},
            {"date": "2022-01-01", "close": 1.00},
        ]
    )
    series = fetch_etf_bars_sina("513260", provider)
    assert provider.calls == ["sh513260"]
    assert series == [(date(2022, 1, 1), 1.00), (date(2022, 1, 3), 1.02)]


def test_fetch_empty_raises():
    with pytest.raises(EtfSourceError):
        fetch_etf_bars_sina("513260", FakeProvider([]))
