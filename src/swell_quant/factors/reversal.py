from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore


@dataclass(frozen=True)
class ReversalFactor(Factor):
    """短期反转：过去 ``lookback`` 个交易日**后复权收益率的相反数**。

    值越大 = 近期跌得越多 = 反转预期越强（买近期输家），方向与动量相反、与
    “值大者更优”的约定一致。A 股短周期常见显著反转效应。窗口不足记 None。
    """

    lookback: int = 5

    @property
    def name(self) -> str:
        return f"reversal_{self.lookback}d"

    def compute(self, store: MarketStore, symbols: Sequence[str], as_of: date) -> FactorValues:
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
            result[symbol] = -(end_close / start_close - 1) if start_close else None
        return result
