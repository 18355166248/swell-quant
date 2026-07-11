from __future__ import annotations

from datetime import date
from typing import Any

from swell_quant.marketdata.frames import iter_rows, parse_date, value


def fetch_trade_calendar(
    provider: Any,
    start: date | None = None,
    end: date | None = None,
) -> list[date]:
    """从 AKShare 拉 A 股交易日历（``tool_trade_date_hist_sina``）。

    返回按日期升序的**交易日**列表（可选按 [start, end] 过滤）。交易日历是
    as_of/lookback 计数与“是否已最新”判定的基准（见 docs/data-module-decisions.md §7-D）。
    """

    frame = provider.tool_trade_date_hist_sina()
    days: list[date] = []
    for row in iter_rows(frame):
        day = parse_date(value(row, "trade_date", "trade_date_hist", "date"))
        if (start is None or day >= start) and (end is None or day <= end):
            days.append(day)
    return sorted(set(days))
