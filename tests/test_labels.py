import pytest

from swell_quant.data.sample_data import generate_sample_bars
from swell_quant.research.labels import compute_labels


def test_labels_use_future_horizon_as_target_only() -> None:
    bars = generate_sample_bars(days=7)
    symbol_bars = [bar for bar in bars if bar.symbol == "000300.SH"]
    labels = [row for row in compute_labels(bars, horizon=5) if row.symbol == "000300.SH"]

    expected_return = symbol_bars[5].close / symbol_bars[0].close - 1.0
    expected_benchmark = symbol_bars[5].benchmark_close / symbol_bars[0].benchmark_close - 1.0

    assert labels[0].future_5d_return == expected_return
    assert labels[0].benchmark_5d_return == expected_benchmark
    assert labels[0].outperform_benchmark_5d in (0, 1)

    assert labels[2].future_5d_return is None
    assert labels[-1].outperform_benchmark_5d is None


def test_labels_reject_non_positive_horizon() -> None:
    with pytest.raises(ValueError, match="horizon"):
        compute_labels(generate_sample_bars(days=7), horizon=0)
