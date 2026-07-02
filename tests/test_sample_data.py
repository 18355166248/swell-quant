from pathlib import Path

from swell_quant.data.sample_data import (
    build_price_data_metadata,
    ensure_sample_prices,
    generate_sample_bars,
    read_price_data_metadata,
    read_price_bars_csv,
    write_price_data_metadata,
)


def test_generate_sample_bars_has_expected_shape() -> None:
    bars = generate_sample_bars(days=20)

    assert len(bars) == 60
    assert {bar.symbol for bar in bars} == {"000300.SH", "000905.SH", "000001.SZ"}


def test_sample_price_csv_round_trip(tmp_path: Path) -> None:
    path = ensure_sample_prices(tmp_path / "prices.csv", days=3)
    bars = read_price_bars_csv(path)

    assert len(bars) == 9
    assert bars[0].symbol == "000300.SH"
    assert bars[0].close == 10.0


def test_price_data_metadata_round_trip(tmp_path: Path) -> None:
    metadata = build_price_data_metadata(
        data_source="akshare",
        symbols=("000001.SZ", "600000.SH"),
        start_date="20240102",
        end_date="20240229",
        benchmark="sh000906",
    )
    path = write_price_data_metadata(tmp_path / "data_source.json", metadata)

    loaded = read_price_data_metadata(path)

    assert loaded["data_source"] == "akshare"
    assert loaded["symbols"] == ["000001.SZ", "600000.SH"]
    assert loaded["benchmark"] == "sh000906"
    assert loaded["universe"] == "akshare_custom"
    assert loaded["benchmark_same_source"] is False
    assert "自定义股票池" in loaded["benchmark_note"]
    assert loaded["updated_at"]
