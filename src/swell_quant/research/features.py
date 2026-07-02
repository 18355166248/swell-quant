from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from swell_quant.data.sample_data import PriceBar


@dataclass(frozen=True)
class FeatureRow:
    symbol: str
    trade_date: date
    close: float
    return_1d: float | None
    momentum_5d: float | None
    ma_5: float | None
    volume_change_1d: float | None


def compute_features(bars: list[PriceBar]) -> list[FeatureRow]:
    by_symbol: dict[str, list[PriceBar]] = defaultdict(list)
    for bar in bars:
        by_symbol[bar.symbol].append(bar)

    rows: list[FeatureRow] = []
    for symbol, symbol_bars in sorted(by_symbol.items()):
        ordered = sorted(symbol_bars, key=lambda item: item.trade_date)
        closes: list[float] = []
        volumes: list[int] = []

        for bar in ordered:
            # 因子计算只读取当前行之前已经积累的历史序列，避免在特征阶段偷看未来价格。
            previous_close = closes[-1] if closes else None
            previous_volume = volumes[-1] if volumes else None

            return_1d = (bar.close / previous_close - 1.0) if previous_close else None
            momentum_5d = (bar.close / closes[-5] - 1.0) if len(closes) >= 5 else None
            ma_5 = (sum(closes[-4:]) + bar.close) / 5 if len(closes) >= 4 else None
            volume_change_1d = (bar.volume / previous_volume - 1.0) if previous_volume else None

            rows.append(
                FeatureRow(
                    symbol=symbol,
                    trade_date=bar.trade_date,
                    close=bar.close,
                    return_1d=return_1d,
                    momentum_5d=momentum_5d,
                    ma_5=ma_5,
                    volume_change_1d=volume_change_1d,
                )
            )
            closes.append(bar.close)
            volumes.append(bar.volume)

    return rows


def write_features_csv(path: Path, rows: list[FeatureRow]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "symbol",
                "date",
                "close",
                "return_1d",
                "momentum_5d",
                "ma_5",
                "volume_change_1d",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "symbol": row.symbol,
                    "date": row.trade_date.isoformat(),
                    "close": f"{row.close:.4f}",
                    "return_1d": _format_optional(row.return_1d),
                    "momentum_5d": _format_optional(row.momentum_5d),
                    "ma_5": _format_optional(row.ma_5),
                    "volume_change_1d": _format_optional(row.volume_change_1d),
                }
            )
    return path


def read_features_csv(path: Path) -> list[FeatureRow]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return [
            FeatureRow(
                symbol=row["symbol"],
                trade_date=date.fromisoformat(row["date"]),
                close=float(row["close"]),
                return_1d=_parse_optional(row["return_1d"]),
                momentum_5d=_parse_optional(row["momentum_5d"]),
                ma_5=_parse_optional(row["ma_5"]),
                volume_change_1d=_parse_optional(row["volume_change_1d"]),
            )
            for row in reader
        ]


def _format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"


def _parse_optional(value: str) -> float | None:
    return None if value == "" else float(value)
