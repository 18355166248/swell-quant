from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore


@dataclass(frozen=True)
class MomentumFactor(Factor):
    """价格动量：过去 ``lookback`` 个交易日的**后复权**收益率。

    用后复权收盘（hfq 视图）计算，除权日不产生假跌幅（见数据模块设计）。
    窗口内交易日不足 lookback+1 根的票记 None（历史不够，不硬算）。
    """

    lookback: int = 20

    @property
    def name(self) -> str:
        return f"momentum_{self.lookback}d"

    def compute(
        self, store: MarketStore, symbols: Sequence[str], as_of: date
    ) -> FactorValues:
        bars = store.get_bars_hfq(symbols, as_of, lookback=self.lookback + 1)
        by_symbol: dict[str, list[BarRecord]] = defaultdict(list)
        for bar in bars:  # 已按 (symbol, date) 升序
            by_symbol[bar.symbol].append(bar)

        result: FactorValues = {}
        for symbol in symbols:
            window = by_symbol.get(symbol, [])
            if len(window) < self.lookback + 1:
                result[symbol] = None
                continue
            start_close = window[0].close
            end_close = window[-1].close
            result[symbol] = (end_close / start_close - 1) if start_close else None
        return result
