from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BarRecord:
    """一条标准日线记录：只存客观事实。

    OHLC 是**不复权真实价**；后复权价不入记录，由 adj_factor 派生
    （视图 close*adj_factor）。adj_factor 约定为**起点锚定的后复权累计因子**
    ——序列最早一天为 1.0、随除权向后递增。这样新分红只影响之后的因子，
    历史因子永不被改写（见 docs/data-module-decisions.md §7-A）。
    """

    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    adj_factor: float
    source: str
