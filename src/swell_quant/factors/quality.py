from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.marketdata.store import MarketStore


@dataclass(frozen=True)
class QualityFactor(Factor):
    """质量/成长因子：取某财务 item（如 ROE、净利润同比）在 as_of 的**最新已披露值**。

    走 ``get_fundamentals`` 的 point-in-time 查询——只认 ``knowledge_date <= as_of`` 的
    数据，且取最新报告期，因此**不含财务未来函数**。缺失记 None。

    ``item`` 如 ``"roe" | "net_profit_yoy" | "revenue_yoy"``。数值越大 = 越优（同向）。
    """

    item: str = "roe"

    @property
    def name(self) -> str:
        return f"quality_{self.item}"

    def compute(
        self, store: MarketStore, symbols: Sequence[str], as_of: date
    ) -> FactorValues:
        records = store.get_fundamentals(symbols, as_of)
        latest = {rec.symbol: rec.value for rec in records if rec.item == self.item}
        return {symbol: latest.get(symbol) for symbol in symbols}
