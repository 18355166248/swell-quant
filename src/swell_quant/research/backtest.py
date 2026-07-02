from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from swell_quant.data.sample_data import PriceBar
from swell_quant.research.modeling import PredictionRow


@dataclass(frozen=True)
class BacktestResult:
    backtest_id: str
    model_version: str
    top_n: int
    trade_count: int
    start_date: str
    end_date: str
    cumulative_return: float
    benchmark_return: float
    excess_return: float
    equity_curve: list[dict[str, str | float]]
    disclaimer: str


def run_top_n_backtest(
    bars: list[PriceBar],
    predictions: list[PredictionRow],
    top_n: int = 2,
    fee_rate: float = 0.001,
) -> BacktestResult:
    if top_n <= 0:
        raise ValueError("top_n must be positive")
    if fee_rate < 0:
        raise ValueError("fee_rate must not be negative")

    bars_by_symbol_date = {(bar.symbol, bar.trade_date): bar for bar in bars}
    dates = sorted({bar.trade_date for bar in bars})
    next_date_by_date = {current: nxt for current, nxt in zip(dates, dates[1:])}

    predictions_by_date: dict[date, list[PredictionRow]] = defaultdict(list)
    for prediction in predictions:
        predictions_by_date[prediction.trade_date].append(prediction)

    equity = 1.0
    benchmark_equity = 1.0
    curve: list[dict[str, str | float]] = []

    for signal_date in sorted(predictions_by_date):
        trade_date = next_date_by_date.get(signal_date)
        if trade_date is None:
            continue

        ranked = sorted(predictions_by_date[signal_date], key=lambda row: (row.rank, row.symbol))[:top_n]
        period_returns: list[float] = []
        benchmark_returns: list[float] = []

        for prediction in ranked:
            signal_bar = bars_by_symbol_date.get((prediction.symbol, signal_date))
            trade_bar = bars_by_symbol_date.get((prediction.symbol, trade_date))
            if signal_bar is None or trade_bar is None:
                continue

            # 回测严格使用 T 日信号、T+1 开盘成交到 T+1 收盘的收益，避免使用成交日之后的数据。
            gross_return = trade_bar.close / trade_bar.open - 1.0
            period_returns.append(gross_return - fee_rate)
            benchmark_returns.append(trade_bar.benchmark_close / signal_bar.benchmark_close - 1.0)

        if not period_returns:
            continue

        portfolio_return = sum(period_returns) / len(period_returns)
        benchmark_return = sum(benchmark_returns) / len(benchmark_returns)
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
    return BacktestResult(
        backtest_id="sample-topn-baseline",
        model_version=predictions[0].model_version if predictions else "unknown",
        top_n=top_n,
        trade_count=len(curve),
        start_date=str(curve[0]["trade_date"]),
        end_date=str(curve[-1]["trade_date"]),
        cumulative_return=cumulative_return,
        benchmark_return=benchmark_total,
        excess_return=cumulative_return - benchmark_total,
        equity_curve=curve,
        disclaimer="仅用于研究，不构成投资建议；历史回测不代表未来表现",
    )


def write_backtest_result(path: Path, result: BacktestResult) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_backtest_result(path: Path) -> BacktestResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BacktestResult(
        backtest_id=payload["backtest_id"],
        model_version=payload["model_version"],
        top_n=int(payload["top_n"]),
        trade_count=int(payload["trade_count"]),
        start_date=payload["start_date"],
        end_date=payload["end_date"],
        cumulative_return=float(payload["cumulative_return"]),
        benchmark_return=float(payload["benchmark_return"]),
        excess_return=float(payload["excess_return"]),
        equity_curve=list(payload["equity_curve"]),
        disclaimer=payload["disclaimer"],
    )
