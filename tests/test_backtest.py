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
    assert result.fee_rate == 0.001
    assert result.slippage_rate == 0.0005
    assert result.execution_price == "next_day_open"
    assert result.holding_period == "next_day_open_to_close"
    assert result.rebalance_rule == "daily_top_n_by_signal_date"
    assert result.trade_count == 2
    assert result.start_date == "2024-01-08"
    assert result.end_date == "2024-01-09"
    assert result.disclaimer == "仅用于研究，不构成投资建议；历史回测不代表未来表现"
    assert result.equity_curve[0]["signal_date"] == "2024-01-07"
    assert result.equity_curve[0]["trade_date"] == "2024-01-08"
    assert result.cumulative_return > 0
    assert result.annualized_return > result.cumulative_return
    assert result.max_drawdown == 0.0
    assert result.sharpe_ratio is not None
    assert result.sharpe_ratio > 0
    assert result.win_rate == 1.0
    assert result.turnover_rate == 0.0
    assert result.rejected_trades
    assert result.rejected_trades[-1]["reason"] == "missing_next_trade_date"


def test_top_n_backtest_validates_parameters() -> None:
    bars = generate_sample_bars(days=8)
    predictions = generate_historical_predictions(compute_features(bars))

    with pytest.raises(ValueError, match="top_n"):
        run_top_n_backtest(bars, predictions, top_n=0)

    with pytest.raises(ValueError, match="fee_rate"):
        run_top_n_backtest(bars, predictions, fee_rate=-0.1)

    with pytest.raises(ValueError, match="slippage_rate"):
        run_top_n_backtest(bars, predictions, slippage_rate=-0.1)


def test_top_n_backtest_slippage_reduces_returns() -> None:
    bars = generate_sample_bars(days=8)
    predictions = generate_historical_predictions(compute_features(bars))

    without_slippage = run_top_n_backtest(
        bars, predictions, top_n=2, fee_rate=0.001, slippage_rate=0.0
    )
    with_slippage = run_top_n_backtest(
        bars, predictions, top_n=2, fee_rate=0.001, slippage_rate=0.002
    )

    assert with_slippage.cumulative_return < without_slippage.cumulative_return


def test_top_n_backtest_records_missing_trade_bar_rejections() -> None:
    bars = generate_sample_bars(days=8)
    predictions = generate_historical_predictions(compute_features(bars))
    first_signal = predictions[0].trade_date
    first_trade_date = sorted({bar.trade_date for bar in bars if bar.trade_date > first_signal})[0]
    missing_symbol = predictions[0].symbol
    filtered_bars = [
        bar
        for bar in bars
        if not (bar.symbol == missing_symbol and bar.trade_date == first_trade_date)
    ]

    result = run_top_n_backtest(filtered_bars, predictions, top_n=2)

    assert any(
        row["symbol"] == missing_symbol
        and row["trade_date"] == first_trade_date.isoformat()
        and row["reason"] == "missing_trade_bar"
        for row in result.rejected_trades
    )
