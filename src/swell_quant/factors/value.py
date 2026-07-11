from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.marketdata.store import MarketStore


@dataclass(frozen=True)
class ValueFactor(Factor):
    """价值因子：取某估值指标的**倒数**（如 1/PE_ttm = 盈利收益率、1/PB = 账面价格比）。

    取倒数使方向统一为“值越大 = 越便宜 = 越好”，与动量等因子同向，便于后续组合。
    只用 as_of 当天已知的最新估值（``get_valuations`` lookback=1）。

    亏损股 PE ≤ 0 的倒数在经济含义上不干净，这里记 None、交由预处理层决定如何处理，
    不硬塞一个会污染排序的负值。``invert=False`` 时直接取原始比率。
    """

    item: str = "pe_ttm"
    invert: bool = True

    @property
    def name(self) -> str:
        return f"value_{self.item}"

    def compute(
        self, store: MarketStore, symbols: Sequence[str], as_of: date
    ) -> FactorValues:
        records = store.get_valuations(symbols, as_of, lookback=1)
        latest = {rec.symbol: rec.value for rec in records if rec.item == self.item}

        result: FactorValues = {}
        for symbol in symbols:
            raw = latest.get(symbol)
            if raw is None:
                result[symbol] = None
            elif self.invert:
                result[symbol] = (1.0 / raw) if raw > 0 else None
            else:
                result[symbol] = raw
        return result
