from __future__ import annotations

from typing import Any

from swell_quant.marketdata.frames import iter_rows, parse_date, to_float, value
from swell_quant.marketdata.records import ValuationRecord


class ValuationSourceError(RuntimeError):
    pass


# 内部 item → 百度估值指标字符串。市销率(ps)在部分标的不可用，暂不纳入默认集。
ITEM_TO_BAIDU_INDICATOR = {
    "pe_ttm": "市盈率(TTM)",
    "pe": "市盈率(静)",
    "pb": "市净率",
    "total_mv": "总市值",
}

DEFAULT_ITEMS = ("pe_ttm", "pb", "total_mv")


def build_valuation_records(
    symbol: str,
    item: str,
    rows: Any,
    source: str,
) -> list[ValuationRecord]:
    """把某指标的 (date, value) 序列合成 ValuationRecord。value 缺失的日期跳过。"""

    records: list[ValuationRecord] = []
    for row in iter_rows(rows):
        raw_value = value(row, "value", "值")
        if raw_value is None or raw_value == "":
            continue
        records.append(
            ValuationRecord(
                symbol=symbol,
                date=parse_date(value(row, "date", "日期")),
                item=item,
                value=to_float(raw_value),
                source=source,
            )
        )
    return records


def fetch_valuations_baidu(
    symbol: str,
    provider: Any,
    items: tuple[str, ...] = DEFAULT_ITEMS,
    period: str = "近一年",
    source: str = "baidu",
) -> list[ValuationRecord]:
    """从**百度**拉每日估值（``stock_zh_valuation_baidu``），逐指标合并。

    百度接口一次只给一个指标的 (date, value) 序列，故按 ``items`` 逐个拉取。
    百度用**纯 6 位代码**（无 sh/sz 前缀）。东方财富估值接口被代理封禁，百度可用。
    """

    digits = symbol.split(".")[0].strip()[-6:]
    records: list[ValuationRecord] = []
    for item in items:
        indicator = ITEM_TO_BAIDU_INDICATOR.get(item)
        if indicator is None:
            raise ValuationSourceError(f"未知估值 item：{item}")
        frame = provider.stock_zh_valuation_baidu(
            symbol=digits, indicator=indicator, period=period
        )
        records.extend(build_valuation_records(symbol, item, frame, source))
    if not records:
        raise ValuationSourceError(f"{source} 返回 {symbol} 无可用估值")
    return records
