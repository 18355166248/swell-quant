import pytest

from swell_quant.data.sample_data import generate_sample_bars
from swell_quant.research.backtest import run_top_n_backtest
from swell_quant.research.features import compute_features
from swell_quant.research.modeling import generate_historical_predictions


def test_top_n_backtest_uses_next_day_open_execution() -> None:
    bars = generate_sample_bars(days=8)
    predictions = generate_historical_predictions(compute_features(bars))

    result = run_top_n_backtest(bars, predictions, top_n=2, fee_rate=0.001)

    assert result.backtest_id == "sample-topn-baseline"
    assert result.top_n == 2
    assert result.trade_count == 2
    assert result.start_date == "2024-01-08"
    assert result.end_date == "2024-01-09"
    assert result.disclaimer == "仅用于研究，不构成投资建议；历史回测不代表未来表现"
    assert result.equity_curve[0]["signal_date"] == "2024-01-07"
    assert result.equity_curve[0]["trade_date"] == "2024-01-08"
    assert result.cumulative_return > 0


def test_top_n_backtest_validates_parameters() -> None:
    bars = generate_sample_bars(days=8)
    predictions = generate_historical_predictions(compute_features(bars))

    with pytest.raises(ValueError, match="top_n"):
        run_top_n_backtest(bars, predictions, top_n=0)

    with pytest.raises(ValueError, match="fee_rate"):
        run_top_n_backtest(bars, predictions, fee_rate=-0.1)
