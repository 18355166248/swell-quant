from swell_quant.data.sample_data import generate_sample_bars
from swell_quant.research.features import compute_features


def test_features_use_only_current_and_past_rows() -> None:
    bars = generate_sample_bars(days=6)
    features = [row for row in compute_features(bars) if row.symbol == "000300.SH"]

    assert features[0].return_1d is None
    assert features[0].momentum_5d is None
    assert features[3].ma_5 is None

    expected_return_1d = bars[1].close / bars[0].close - 1.0
    expected_ma_5 = sum(bar.close for bar in bars[:5]) / 5
    expected_momentum_5d = bars[5].close / bars[0].close - 1.0

    assert features[1].return_1d == expected_return_1d
    assert features[4].ma_5 == expected_ma_5
    assert features[5].momentum_5d == expected_momentum_5d
