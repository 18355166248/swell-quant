from pathlib import Path

import pytest

from swell_quant.data.akshare_data import (
    AkshareDependencyError,
    fetch_akshare_price_bars,
    write_akshare_prices_csv,
)
from swell_quant.data.sample_data import read_price_bars_csv


class FakeFrame:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def to_dict(self, orient: str) -> list[dict]:
        assert orient == "records"
        return self.rows


class FakeAkshare:
    def stock_zh_index_daily(self, symbol: str) -> FakeFrame:
        assert symbol == "sh000906"
        return FakeFrame(
            [
                {"date": "2024-01-02", "close": 1000.0},
                {"date": "2024-01-03", "close": 1001.5},
            ]
        )

    def stock_zh_a_hist(
        self, symbol: str, period: str, start_date: str, end_date: str, adjust: str
    ) -> FakeFrame:
        assert symbol == "000001"
        assert period == "daily"
        assert start_date == "20240102"
        assert end_date == "20240103"
        assert adjust == "qfq"
        return FakeFrame(
            [
                {
                    "日期": "2024-01-02",
                    "开盘": 10.0,
                    "最高": 10.5,
                    "最低": 9.8,
                    "收盘": 10.2,
                    "成交量": 12345,
                },
                {
                    "日期": "2024-01-03",
                    "开盘": 10.2,
                    "最高": 10.7,
                    "最低": 10.1,
                    "收盘": 10.6,
                    "成交量": 23456,
                },
            ]
        )


def test_fetch_akshare_price_bars_maps_daily_rows() -> None:
    bars = fetch_akshare_price_bars(
        symbols=("000001.SZ",),
        start_date="20240102",
        end_date="20240103",
        provider=FakeAkshare(),
    )

    assert len(bars) == 2
    assert bars[0].symbol == "000001.SZ"
    assert bars[0].trade_date.isoformat() == "2024-01-02"
    assert bars[0].close == 10.2
    assert bars[0].benchmark_close == 1000.0
    assert bars[1].volume == 23456


def test_write_akshare_prices_csv_uses_standard_price_contract(tmp_path: Path) -> None:
    path = write_akshare_prices_csv(
        tmp_path / "prices.csv",
        symbols=("000001.SZ",),
        start_date="20240102",
        end_date="20240103",
        provider=FakeAkshare(),
    )

    loaded = read_price_bars_csv(path)

    assert len(loaded) == 2
    assert loaded[1].benchmark_close == 1001.5


def test_fetch_akshare_price_bars_requires_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    import swell_quant.data.akshare_data as akshare_data

    def fail_import(_name: str) -> None:
        raise ImportError("missing")

    monkeypatch.setattr(akshare_data.importlib, "import_module", fail_import)

    with pytest.raises(AkshareDependencyError, match="DATA_SOURCE=akshare"):
        fetch_akshare_price_bars(
            symbols=("000001.SZ",),
            start_date="20240102",
            end_date="20240103",
        )
