import pytest

from swell_quant.data.sample_data import generate_sample_bars
from swell_quant.research.features import compute_features


def test_features_use_only_current_and_past_rows() -> None:
    bars = generate_sample_bars(days=7)
    features = [row for row in compute_features(bars) if row.symbol == "000300.SH"]

    assert features[0].return_1d is None
    assert features[0].momentum_5d is None
    assert features[3].ma_5 is None
    assert features[4].volatility_5d is None
    assert features[5].rsi_6 is None

    expected_return_1d = bars[1].close / bars[0].close - 1.0
    expected_ma_5 = sum(bar.close for bar in bars[:5]) / 5
    expected_momentum_5d = bars[5].close / bars[0].close - 1.0

    assert features[1].return_1d == pytest.approx(expected_return_1d)
    assert features[4].ma_5 == pytest.approx(expected_ma_5)
    assert features[5].momentum_5d == pytest.approx(expected_momentum_5d)
    assert features[5].volatility_5d is not None
    assert features[6].rsi_6 == 100.0
    assert features[0].macd_dif == 0.0
    assert features[6].macd_hist is not None
