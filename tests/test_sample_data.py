from pathlib import Path

from swell_quant.data.sample_data import ensure_sample_prices, generate_sample_bars, read_price_bars_csv


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
