from datetime import date
from pathlib import Path

from swell_quant.data.quality import read_quality_report, validate_price_bars, write_quality_report
from swell_quant.data.sample_data import PriceBar, generate_sample_bars


def test_validate_price_bars_passes_sample_data() -> None:
    report = validate_price_bars(generate_sample_bars(days=20))

    assert report.passed
    assert report.row_count == 60
    assert report.symbol_count == 3
    assert report.issue_count == 0


def test_validate_price_bars_finds_duplicate_and_invalid_rows() -> None:
    valid = PriceBar(
        symbol="000001.SZ",
        trade_date=date(2024, 1, 2),
        open=10.0,
        high=11.0,
        low=9.0,
        close=10.5,
        volume=100,
        benchmark_close=1000.0,
    )
    invalid = PriceBar(
        symbol="000001.SZ",
        trade_date=date(2024, 1, 2),
        open=12.0,
        high=11.0,
        low=9.0,
        close=-1.0,
        volume=-100,
        benchmark_close=0.0,
    )

    report = validate_price_bars([valid, invalid])
    codes = {issue.code for issue in report.issues}

    assert not report.passed
    assert "duplicate_symbol_date" in codes
    assert "non_positive_price" in codes
    assert "invalid_ohlc_range" in codes
    assert "negative_volume" in codes
    assert "invalid_benchmark" in codes


def test_quality_report_json_round_trip(tmp_path: Path) -> None:
    report = validate_price_bars(generate_sample_bars(days=2))
    path = write_quality_report(tmp_path / "quality.json", report)

    loaded = read_quality_report(path)

    assert loaded == report
