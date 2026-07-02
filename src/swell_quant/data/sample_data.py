from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    benchmark_close: float


SAMPLE_SYMBOLS = ("000300.SH", "000905.SH", "000001.SZ")


def generate_sample_bars(days: int = 20) -> list[PriceBar]:
    start = date(2024, 1, 2)
    bars: list[PriceBar] = []

    for symbol_index, symbol in enumerate(SAMPLE_SYMBOLS):
        base_price = 10.0 + symbol_index * 4.0
        base_volume = 1_000_000 + symbol_index * 250_000
        for day_index in range(days):
            trade_date = start + timedelta(days=day_index)
            close = round(base_price + day_index * (0.11 + symbol_index * 0.03), 4)
            open_price = round(close * 0.995, 4)
            high = round(close * 1.012, 4)
            low = round(close * 0.988, 4)
            benchmark_close = round(1000.0 + day_index * 1.6, 4)
            bars.append(
                PriceBar(
                    symbol=symbol,
                    trade_date=trade_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=base_volume + day_index * 10_000,
                    benchmark_close=benchmark_close,
                )
            )

    return bars


def write_price_bars_csv(path: Path, bars: list[PriceBar]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "symbol",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "benchmark_close",
            ],
        )
        writer.writeheader()
        for bar in bars:
            writer.writerow(
                {
                    "symbol": bar.symbol,
                    "date": bar.trade_date.isoformat(),
                    "open": f"{bar.open:.4f}",
                    "high": f"{bar.high:.4f}",
                    "low": f"{bar.low:.4f}",
                    "close": f"{bar.close:.4f}",
                    "volume": str(bar.volume),
                    "benchmark_close": f"{bar.benchmark_close:.4f}",
                }
            )
    return path


def read_price_bars_csv(path: Path) -> list[PriceBar]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return [
            PriceBar(
                symbol=row["symbol"],
                trade_date=date.fromisoformat(row["date"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                benchmark_close=float(row["benchmark_close"]),
            )
            for row in reader
        ]


def ensure_sample_prices(path: Path, days: int = 20) -> Path:
    bars = generate_sample_bars(days=days)
    return write_price_bars_csv(path, bars)
