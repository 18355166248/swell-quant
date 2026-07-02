from __future__ import annotations

import importlib
from datetime import date, datetime
from pathlib import Path
from typing import Any

from swell_quant.data.sample_data import PriceBar, write_price_bars_csv


class AkshareDependencyError(RuntimeError):
    pass


def fetch_akshare_price_bars(
    symbols: tuple[str, ...],
    start_date: str,
    end_date: str,
    benchmark_symbol: str = "sh000906",
    provider: Any | None = None,
) -> list[PriceBar]:
    akshare = provider or _load_akshare()
    benchmark_by_date = _fetch_benchmark_close(
        akshare, benchmark_symbol, start_date=start_date, end_date=end_date
    )
    bars: list[PriceBar] = []
    for symbol in symbols:
        frame = akshare.stock_zh_a_hist(
            symbol=_akshare_stock_symbol(symbol),
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        for row in _iter_rows(frame):
            trade_date = _parse_trade_date(_value(row, "日期", "date"))
            benchmark_close = benchmark_by_date.get(trade_date)
            if benchmark_close is None:
                continue
            # AKShare 返回前复权日频行情；这里只做字段标准化和基准对齐，不在采集层计算因子或标签。
            bars.append(
                PriceBar(
                    symbol=symbol,
                    trade_date=trade_date,
                    open=float(_value(row, "开盘", "open")),
                    high=float(_value(row, "最高", "high")),
                    low=float(_value(row, "最低", "low")),
                    close=float(_value(row, "收盘", "close")),
                    volume=int(float(_value(row, "成交量", "volume"))),
                    benchmark_close=benchmark_close,
                )
            )
    if not bars:
        raise ValueError("akshare returned no price bars after benchmark alignment")
    return sorted(bars, key=lambda bar: (bar.trade_date, bar.symbol))


def write_akshare_prices_csv(
    path: Path,
    symbols: tuple[str, ...],
    start_date: str,
    end_date: str,
    benchmark_symbol: str = "sh000906",
    provider: Any | None = None,
) -> Path:
    bars = fetch_akshare_price_bars(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        benchmark_symbol=benchmark_symbol,
        provider=provider,
    )
    return write_price_bars_csv(path, bars)


def _load_akshare() -> Any:
    try:
        return importlib.import_module("akshare")
    except ImportError as error:
        raise AkshareDependencyError(
            'DATA_SOURCE=akshare requires optional dependency: python3 -m pip install -e ".[data]"'
        ) from error


def _fetch_benchmark_close(
    provider: Any, benchmark_symbol: str, start_date: str, end_date: str
) -> dict[date, float]:
    frame = provider.stock_zh_index_daily(symbol=benchmark_symbol)
    start = datetime.strptime(start_date, "%Y%m%d").date()
    end = datetime.strptime(end_date, "%Y%m%d").date()
    closes: dict[date, float] = {}
    for row in _iter_rows(frame):
        trade_date = _parse_trade_date(_value(row, "date", "日期"))
        if start <= trade_date <= end:
            closes[trade_date] = float(_value(row, "close", "收盘"))
    if not closes:
        raise ValueError(f"akshare returned no benchmark rows for {benchmark_symbol}")
    return closes


def _iter_rows(frame: Any) -> list[dict[str, Any]]:
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict("records"))
    return list(frame)


def _value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    raise KeyError(f"missing expected AKShare field; expected one of {keys}")


def _parse_trade_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _akshare_stock_symbol(symbol: str) -> str:
    return symbol.split(".")[0]
