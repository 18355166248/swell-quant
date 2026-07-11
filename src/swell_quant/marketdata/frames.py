from __future__ import annotations

from datetime import date, datetime
from typing import Any


def iter_rows(frame: Any) -> list[dict[str, Any]]:
    """把 pandas DataFrame 或 list[dict] 统一成 list[dict]，隔离数据源的帧类型。"""

    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        return frame.to_dict("records")
    return list(frame)


def value(row: dict[str, Any], *keys: str) -> Any:
    """按候选键取值（兼容中/英文列名，如 "日期"/"date"）。"""

    for key in keys:
        if key in row:
            return row[key]
    raise KeyError(f"行缺少字段 {keys!r}：{sorted(row)}")


def to_float(value: Any) -> float:
    return float(value)


def parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
