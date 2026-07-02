from __future__ import annotations

import csv
import math
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
    volatility_5d: float | None
    rsi_6: float | None
    macd_dif: float | None
    macd_signal: float | None
    macd_hist: float | None
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
        returns: list[float] = []
        ema_12: float | None = None
        ema_26: float | None = None
        macd_signal: float | None = None

        for bar in ordered:
            # 因子计算只读取当前行之前已经积累的历史序列，避免在特征阶段偷看未来价格。
            previous_close = closes[-1] if closes else None
            previous_volume = volumes[-1] if volumes else None

            return_1d = (bar.close / previous_close - 1.0) if previous_close else None
            if return_1d is not None:
                returns.append(return_1d)
            momentum_5d = (bar.close / closes[-5] - 1.0) if len(closes) >= 5 else None
            ma_5 = (sum(closes[-4:]) + bar.close) / 5 if len(closes) >= 4 else None
            volatility_5d = _rolling_volatility(returns[-5:]) if len(returns) >= 5 else None
            rsi_6 = _rsi(returns[-6:]) if len(returns) >= 6 else None
            ema_12 = _ema(bar.close, ema_12, span=12)
            ema_26 = _ema(bar.close, ema_26, span=26)
            macd_dif = ema_12 - ema_26
            macd_signal = _ema(macd_dif, macd_signal, span=9)
            macd_hist = macd_dif - macd_signal
            volume_change_1d = (bar.volume / previous_volume - 1.0) if previous_volume else None

            rows.append(
                FeatureRow(
                    symbol=symbol,
                    trade_date=bar.trade_date,
                    close=bar.close,
                    return_1d=return_1d,
                    momentum_5d=momentum_5d,
                    ma_5=ma_5,
                    volatility_5d=volatility_5d,
                    rsi_6=rsi_6,
                    macd_dif=macd_dif,
                    macd_signal=macd_signal,
                    macd_hist=macd_hist,
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
                "volatility_5d",
                "rsi_6",
                "macd_dif",
                "macd_signal",
                "macd_hist",
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
                    "volatility_5d": _format_optional(row.volatility_5d),
                    "rsi_6": _format_optional(row.rsi_6),
                    "macd_dif": _format_optional(row.macd_dif),
                    "macd_signal": _format_optional(row.macd_signal),
                    "macd_hist": _format_optional(row.macd_hist),
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
                volatility_5d=_parse_optional(row["volatility_5d"]),
                rsi_6=_parse_optional(row["rsi_6"]),
                macd_dif=_parse_optional(row["macd_dif"]),
                macd_signal=_parse_optional(row["macd_signal"]),
                macd_hist=_parse_optional(row["macd_hist"]),
                volume_change_1d=_parse_optional(row["volume_change_1d"]),
            )
            for row in reader
        ]


def _rolling_volatility(values: list[float]) -> float:
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _rsi(values: list[float]) -> float:
    gains = [max(value, 0.0) for value in values]
    losses = [abs(min(value, 0.0)) for value in values]
    average_gain = sum(gains) / len(gains)
    average_loss = sum(losses) / len(losses)
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def _ema(value: float, previous: float | None, span: int) -> float:
    alpha = 2.0 / (span + 1)
    return value if previous is None else alpha * value + (1.0 - alpha) * previous


def _format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"


def _parse_optional(value: str) -> float | None:
    return None if value == "" else float(value)
