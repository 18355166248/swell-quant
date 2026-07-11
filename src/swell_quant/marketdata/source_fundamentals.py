from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

from swell_quant.marketdata.frames import iter_rows
from swell_quant.marketdata.records import FundamentalRecord


class FundamentalSourceError(RuntimeError):
    pass


# 东财业绩报表列名 → 内部 item。ROE/同比均为百分数原值（如 10.57 表示 10.57%）。
YJBB_ITEM_COLUMNS = {
    "eps": "每股收益",
    "revenue_yoy": "营业总收入-同比增长",
    "net_profit": "净利润-净利润",
    "net_profit_yoy": "净利润-同比增长",
    "roe": "净资产收益率",
}

DEFAULT_ITEMS = ("roe", "net_profit_yoy", "revenue_yoy")

# 东财业绩报表的“最新公告日期”是公司最近一次公告日、非本行报告期的原始公告日，
# 用作 knowledge_date 会破坏 PIT（见 docs/data-module-decisions.md §7-C）。故不采用它，
# 改用“报告期末 + 法定披露截止日”做保守估计（只会更晚、不泄露未来），source 标注为估计。
YJBB_SOURCE = "yjbb_em_est"

_SYMBOL_COLUMN = "股票代码"


def statutory_disclosure_date(event_date: date) -> date:
    """报告期末 → A股法定披露截止日（knowledge_date 的保守估计）。

    Q1→4/30、半年报→8/31、Q3→10/31、年报→次年4/30。非标准期末兜底为期末+120天。
    这是**保守**估计：真实公告通常更早，用截止日可确保不引入未来函数。
    """

    month, day = event_date.month, event_date.day
    year = event_date.year
    if (month, day) == (3, 31):
        return date(year, 4, 30)
    if (month, day) == (6, 30):
        return date(year, 8, 31)
    if (month, day) == (9, 30):
        return date(year, 10, 31)
    if (month, day) == (12, 31):
        return date(year + 1, 4, 30)
    return event_date + timedelta(days=120)


def build_fundamental_records(
    frame: Any,
    period: str,
    items: tuple[str, ...] = DEFAULT_ITEMS,
    source: str = YJBB_SOURCE,
) -> list[FundamentalRecord]:
    """把业绩报表帧合成 FundamentalRecord。event_date=报告期末，knowledge_date=法定截止日。"""

    event_date = datetime.strptime(period, "%Y%m%d").date()
    knowledge_date = statutory_disclosure_date(event_date)

    records: list[FundamentalRecord] = []
    for row in iter_rows(frame):
        symbol = _clean_symbol(row.get(_SYMBOL_COLUMN))
        if symbol is None:
            continue
        for item in items:
            column = YJBB_ITEM_COLUMNS.get(item)
            if column is None:
                raise FundamentalSourceError(f"未知 item：{item}")
            value = row.get(column)
            if not _is_number(value):
                continue
            records.append(
                FundamentalRecord(
                    symbol=symbol,
                    event_date=event_date,
                    knowledge_date=knowledge_date,
                    item=item,
                    value=float(value),
                    source=source,
                )
            )
    return records


def fetch_fundamentals(
    provider: Any,
    period: str,
    items: tuple[str, ...] = DEFAULT_ITEMS,
    source: str = YJBB_SOURCE,
) -> list[FundamentalRecord]:
    """从东财业绩报表（``stock_yjbb_em``）拉某报告期全市场的财务，合成 FundamentalRecord。

    一次调用返回全 A 股该期数据（高效），由采集层按股票池过滤。``period`` 形如 "20240331"。
    """

    frame = provider.stock_yjbb_em(date=period)
    records = build_fundamental_records(frame, period, items, source)
    if not records:
        raise FundamentalSourceError(f"业绩报表 {period} 无可用财务数据")
    return records


def _clean_symbol(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_number(value: Any) -> bool:
    if value is None:
        return False
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False
