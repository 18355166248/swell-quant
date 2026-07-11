from __future__ import annotations

from typing import Any

from swell_quant.marketdata.frames import iter_rows, parse_date, to_float, value
from swell_quant.marketdata.records import IndexBarRecord


class IndexSourceError(RuntimeError):
    pass


def build_index_bars(
    index_code: str, rows: Any, source: str
) -> list[IndexBarRecord]:
    """把 (date, close) 序列合成 IndexBarRecord，按日期升序。"""

    records: list[IndexBarRecord] = []
    for row in iter_rows(rows):
        records.append(
            IndexBarRecord(
                index_code=index_code,
                date=parse_date(value(row, "date", "日期")),
                close=to_float(value(row, "close", "收盘")),
                source=source,
            )
        )
    records.sort(key=lambda bar: bar.date)
    return records


def fetch_index_bars_sina(
    index_code: str,
    provider: Any,
    source: str = "sina",
) -> list[IndexBarRecord]:
    """从**新浪**拉指数日线（``stock_zh_index_daily``）。

    ``index_code`` 用新浪格式，如沪深300 = "sh000300"、中证500 = "sh000905"。
    该接口返回全历史，调用方按需截取。
    """

    frame = provider.stock_zh_index_daily(symbol=index_code)
    records = build_index_bars(index_code, frame, source)
    if not records:
        raise IndexSourceError(f"{source} 返回指数 {index_code} 无数据")
    return records
