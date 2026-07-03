from pathlib import Path

import pytest

from swell_quant.data.akshare_data import (
    AkshareDependencyError,
    collect_akshare_price_bars,
    fetch_akshare_price_bars,
    resolve_akshare_symbols,
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
    def __init__(self) -> None:
        self.index_symbols: list[str] = []

    def index_stock_cons(self, symbol: str) -> FakeFrame:
        self.index_symbols.append(symbol)
        rows_by_symbol = {
            "000300": [
                {"品种代码": "600000", "交易所": "上海证券交易所"},
                {"品种代码": "000001", "交易所": "深圳证券交易所"},
            ],
            "000905": [
                {"成分券代码": "600000", "交易所": "SH"},
                {"成分券代码": "300001", "交易所": "SZ"},
            ],
        }
        return FakeFrame(rows_by_symbol[symbol])

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


class PartiallyFailingAkshare(FakeAkshare):
    def stock_zh_a_hist(
        self, symbol: str, period: str, start_date: str, end_date: str, adjust: str
    ) -> FakeFrame:
        if symbol == "600000":
            raise RuntimeError("temporary upstream error")
        return super().stock_zh_a_hist(symbol, period, start_date, end_date, adjust)


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


def test_collect_akshare_price_bars_records_symbol_failures() -> None:
    result = collect_akshare_price_bars(
        symbols=("000001.SZ", "600000.SH"),
        start_date="20240102",
        end_date="20240103",
        provider=PartiallyFailingAkshare(),
    )

    assert len(result.bars) == 2
    assert result.requested_symbols == ("000001.SZ", "600000.SH")
    assert result.succeeded_symbols == ("000001.SZ",)
    assert len(result.failed_symbols) == 1
    assert result.failed_symbols[0].symbol == "600000.SH"
    assert "temporary upstream error" in result.failed_symbols[0].reason


def test_collect_akshare_price_bars_reports_all_failures_when_no_bars() -> None:
    class FailingAkshare(FakeAkshare):
        def stock_zh_a_hist(
            self, symbol: str, period: str, start_date: str, end_date: str, adjust: str
        ) -> FakeFrame:
            raise RuntimeError(f"blocked {symbol}")

    with pytest.raises(ValueError, match="000001.SZ: blocked 000001"):
        collect_akshare_price_bars(
            symbols=("000001.SZ", "600000.SH"),
            start_date="20240102",
            end_date="20240103",
            provider=FailingAkshare(),
        )


def test_resolve_akshare_symbols_fetches_csi800_components() -> None:
    provider = FakeAkshare()

    symbols = resolve_akshare_symbols(
        universe_mode="csi800",
        manual_symbols=(),
        provider=provider,
    )

    assert provider.index_symbols == ["000300", "000905"]
    assert symbols == ("600000.SH", "000001.SZ", "300001.SZ")


def test_resolve_akshare_symbols_keeps_manual_symbols() -> None:
    symbols = resolve_akshare_symbols(
        universe_mode="manual",
        manual_symbols=("000001.SZ", "600000.SH"),
        provider=FakeAkshare(),
    )

    assert symbols == ("000001.SZ", "600000.SH")


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
