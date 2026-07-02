from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from math import sqrt
from pathlib import Path

from swell_quant.data.sample_data import PriceBar
from swell_quant.research.modeling import PredictionRow


@dataclass(frozen=True)
class BacktestResult:
    backtest_id: str
    model_version: str
    top_n: int
    fee_rate: float
    slippage_rate: float
    execution_price: str
    holding_period: str
    rebalance_rule: str
    trade_count: int
    start_date: str
    end_date: str
    cumulative_return: float
    annualized_return: float
    benchmark_return: float
    excess_return: float
    max_drawdown: float
    sharpe_ratio: float | None
    win_rate: float
    turnover_rate: float
    equity_curve: list[dict[str, str | float]]
    rejected_trades: list[dict[str, str | int]]
    disclaimer: str


def run_top_n_backtest(
    bars: list[PriceBar],
    predictions: list[PredictionRow],
    top_n: int = 2,
    fee_rate: float = 0.001,
    slippage_rate: float = 0.0005,
) -> BacktestResult:
    if top_n <= 0:
        raise ValueError("top_n must be positive")
    if fee_rate < 0:
        raise ValueError("fee_rate must not be negative")
    if slippage_rate < 0:
        raise ValueError("slippage_rate must not be negative")

    bars_by_symbol_date = {(bar.symbol, bar.trade_date): bar for bar in bars}
    dates = sorted({bar.trade_date for bar in bars})
    next_date_by_date = {current: nxt for current, nxt in zip(dates, dates[1:])}

    predictions_by_date: dict[date, list[PredictionRow]] = defaultdict(list)
    for prediction in predictions:
        predictions_by_date[prediction.trade_date].append(prediction)

    equity = 1.0
    benchmark_equity = 1.0
    curve: list[dict[str, str | float]] = []
    rejected_trades: list[dict[str, str | int]] = []
    portfolio_returns: list[float] = []
    selected_symbol_sets: list[set[str]] = []

    for signal_date in sorted(predictions_by_date):
        trade_date = next_date_by_date.get(signal_date)
        if trade_date is None:
            for prediction in predictions_by_date[signal_date]:
                rejected_trades.append(
                    _rejected_trade(prediction, signal_date, None, "missing_next_trade_date")
                )
            continue

        ranked = sorted(predictions_by_date[signal_date], key=lambda row: (row.rank, row.symbol))[
            :top_n
        ]
        period_returns: list[float] = []
        benchmark_returns: list[float] = []
        selected_symbols: set[str] = set()

        for prediction in ranked:
            signal_bar = bars_by_symbol_date.get((prediction.symbol, signal_date))
            trade_bar = bars_by_symbol_date.get((prediction.symbol, trade_date))
            if signal_bar is None:
                rejected_trades.append(
                    _rejected_trade(prediction, signal_date, trade_date, "missing_signal_bar")
                )
                continue
            if trade_bar is None:
                rejected_trades.append(
                    _rejected_trade(prediction, signal_date, trade_date, "missing_trade_bar")
                )
                continue

            # 回测严格使用 T 日信号、T+1 开盘成交到 T+1 收盘的收益；买入滑点只抬高入场价，
            # 不读取成交日之后的数据，保证和预测标签的 T+1 入场口径一致。
            executed_open = trade_bar.open * (1.0 + slippage_rate)
            gross_return = trade_bar.close / executed_open - 1.0
            period_returns.append(gross_return - fee_rate)
            benchmark_returns.append(trade_bar.benchmark_close / signal_bar.benchmark_close - 1.0)
            selected_symbols.add(prediction.symbol)

        if not period_returns:
            continue

        portfolio_return = sum(period_returns) / len(period_returns)
        benchmark_return = sum(benchmark_returns) / len(benchmark_returns)
        portfolio_returns.append(portfolio_return)
        selected_symbol_sets.append(selected_symbols)
        equity *= 1.0 + portfolio_return
        benchmark_equity *= 1.0 + benchmark_return
        curve.append(
            {
                "signal_date": signal_date.isoformat(),
                "trade_date": trade_date.isoformat(),
                "portfolio_return": round(portfolio_return, 8),
                "benchmark_return": round(benchmark_return, 8),
                "equity": round(equity, 8),
                "benchmark_equity": round(benchmark_equity, 8),
            }
        )

    if not curve:
        raise ValueError("no executable backtest trades")

    cumulative_return = equity - 1.0
    benchmark_total = benchmark_equity - 1.0
    # 这些指标只基于已发生的逐期收益和净值曲线，保持回测评估可复现且不引入未来信息。
    annualized_return = _annualized_return(equity, len(portfolio_returns))
    max_drawdown = _max_drawdown([float(row["equity"]) for row in curve])
    sharpe_ratio = _sharpe_ratio(portfolio_returns)
    win_rate = sum(1 for value in portfolio_returns if value > 0) / len(portfolio_returns)
    turnover_rate = _average_turnover(selected_symbol_sets)
    return BacktestResult(
        backtest_id="sample-topn-baseline",
        model_version=predictions[0].model_version if predictions else "unknown",
        top_n=top_n,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        execution_price="next_day_open",
        holding_period="next_day_open_to_close",
        rebalance_rule="daily_top_n_by_signal_date",
        trade_count=len(curve),
        start_date=str(curve[0]["trade_date"]),
        end_date=str(curve[-1]["trade_date"]),
        cumulative_return=cumulative_return,
        annualized_return=annualized_return,
        benchmark_return=benchmark_total,
        excess_return=cumulative_return - benchmark_total,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        win_rate=win_rate,
        turnover_rate=turnover_rate,
        equity_curve=curve,
        rejected_trades=rejected_trades,
        disclaimer="仅用于研究，不构成投资建议；历史回测不代表未来表现",
    )


def write_backtest_result(path: Path, result: BacktestResult) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def read_backtest_result(path: Path) -> BacktestResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BacktestResult(
        backtest_id=payload["backtest_id"],
        model_version=payload["model_version"],
        top_n=int(payload["top_n"]),
        fee_rate=float(payload.get("fee_rate", 0.001)),
        slippage_rate=float(payload.get("slippage_rate", 0.0)),
        execution_price=payload.get("execution_price", "next_day_open"),
        holding_period=payload.get("holding_period", "next_day_open_to_close"),
        rebalance_rule=payload.get("rebalance_rule", "daily_top_n_by_signal_date"),
        trade_count=int(payload["trade_count"]),
        start_date=payload["start_date"],
        end_date=payload["end_date"],
        cumulative_return=float(payload["cumulative_return"]),
        annualized_return=float(payload.get("annualized_return", payload["cumulative_return"])),
        benchmark_return=float(payload["benchmark_return"]),
        excess_return=float(payload["excess_return"]),
        max_drawdown=float(payload.get("max_drawdown", 0.0)),
        sharpe_ratio=(
            None if payload.get("sharpe_ratio") is None else float(payload.get("sharpe_ratio"))
        ),
        win_rate=float(payload.get("win_rate", 0.0)),
        turnover_rate=float(payload.get("turnover_rate", 0.0)),
        equity_curve=list(payload["equity_curve"]),
        rejected_trades=list(payload.get("rejected_trades", [])),
        disclaimer=payload["disclaimer"],
    )


def _rejected_trade(
    prediction: PredictionRow, signal_date: date, trade_date: date | None, reason: str
) -> dict[str, str | int]:
    return {
        "symbol": prediction.symbol,
        "rank": prediction.rank,
        "signal_date": signal_date.isoformat(),
        "trade_date": "-" if trade_date is None else trade_date.isoformat(),
        "reason": reason,
    }


def _annualized_return(final_equity: float, periods: int, periods_per_year: int = 252) -> float:
    if periods <= 0:
        return 0.0
    return final_equity ** (periods_per_year / periods) - 1.0


def _max_drawdown(equity_values: list[float]) -> float:
    peak = 1.0
    max_drawdown = 0.0
    for value in equity_values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = min(max_drawdown, value / peak - 1.0)
    return max_drawdown


def _sharpe_ratio(returns: list[float], periods_per_year: int = 252) -> float | None:
    if len(returns) < 2:
        return None
    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
    volatility = variance**0.5
    if volatility == 0:
        return None
    return mean_return / volatility * sqrt(periods_per_year)


def _average_turnover(selected_symbol_sets: list[set[str]]) -> float:
    if len(selected_symbol_sets) < 2:
        return 0.0
    turnovers: list[float] = []
    for previous, current in zip(selected_symbol_sets, selected_symbol_sets[1:]):
        if not previous and not current:
            turnovers.append(0.0)
            continue
        changed = len(previous.symmetric_difference(current))
        base = max(len(previous), len(current), 1)
        turnovers.append(changed / base)
    return sum(turnovers) / len(turnovers)
