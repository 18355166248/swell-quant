from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from swell_quant.data.sample_data import PriceBar


@dataclass(frozen=True)
class LabelRow:
    symbol: str
    trade_date: date
    future_5d_return: float | None
    benchmark_5d_return: float | None
    outperform_benchmark_5d: int | None


def compute_labels(bars: list[PriceBar], horizon: int = 5) -> list[LabelRow]:
    if horizon <= 0:
        raise ValueError("horizon must be positive")

    by_symbol: dict[str, list[PriceBar]] = defaultdict(list)
    for bar in bars:
        by_symbol[bar.symbol].append(bar)

    rows: list[LabelRow] = []
    for symbol, symbol_bars in sorted(by_symbol.items()):
        ordered = sorted(symbol_bars, key=lambda item: item.trade_date)

        for index, bar in enumerate(ordered):
            target_index = index + horizon
            entry_index = index + 1
            if target_index >= len(ordered) or entry_index >= len(ordered):
                future_return = None
                benchmark_return = None
                outperform = None
            else:
                entry = ordered[entry_index]
                target = ordered[target_index]
                # 标签刻意使用 T+1 开盘到 T+horizon 收盘的未来持有期结果；它只能作为监督目标，
                # 不允许在同一日期的特征生成、填充或排序中被读取，避免和 T 日特征发生泄漏。
                future_return = target.close / entry.open - 1.0
                benchmark_return = target.benchmark_close / entry.benchmark_close - 1.0
                outperform = 1 if future_return > benchmark_return else 0

            rows.append(
                LabelRow(
                    symbol=symbol,
                    trade_date=bar.trade_date,
                    future_5d_return=future_return,
                    benchmark_5d_return=benchmark_return,
                    outperform_benchmark_5d=outperform,
                )
            )

    return rows


def write_labels_csv(path: Path, rows: list[LabelRow]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "symbol",
                "date",
                "future_5d_return",
                "benchmark_5d_return",
                "outperform_benchmark_5d",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "symbol": row.symbol,
                    "date": row.trade_date.isoformat(),
                    "future_5d_return": _format_optional(row.future_5d_return),
                    "benchmark_5d_return": _format_optional(row.benchmark_5d_return),
                    "outperform_benchmark_5d": ""
                    if row.outperform_benchmark_5d is None
                    else str(row.outperform_benchmark_5d),
                }
            )
    return path


def read_labels_csv(path: Path) -> list[LabelRow]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return [
            LabelRow(
                symbol=row["symbol"],
                trade_date=date.fromisoformat(row["date"]),
                future_5d_return=_parse_optional(row["future_5d_return"]),
                benchmark_5d_return=_parse_optional(row["benchmark_5d_return"]),
                outperform_benchmark_5d=_parse_optional_int(row["outperform_benchmark_5d"]),
            )
            for row in reader
        ]


def _format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"


def _parse_optional(value: str) -> float | None:
    return None if value == "" else float(value)


def _parse_optional_int(value: str) -> int | None:
    return None if value == "" else int(value)
