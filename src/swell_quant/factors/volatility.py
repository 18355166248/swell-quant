from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore


@dataclass(frozen=True)
class VolatilityFactor(Factor):
    """波动率：过去 ``lookback`` 个交易日**后复权日收益率**的样本标准差。

    这是一个**测量值**（数值越大 = 越波动），方向不内置：低波动异象下“低波动更好”，
    组合时给负权重即可（见 FactorPipeline）。用后复权收益，除权日不产生假收益。
    窗口内日收益不足 2 个（bar < 3 根）的票记 None。
    """

    lookback: int = 20

    @property
    def name(self) -> str:
        return f"volatility_{self.lookback}d"

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
            returns = _daily_returns(window)
            result[symbol] = statistics.stdev(returns) if len(returns) >= 2 else None
        return result


def _daily_returns(bars: list[BarRecord]) -> list[float]:
    returns: list[float] = []
    for prev, curr in zip(bars, bars[1:]):
        if prev.close:
            returns.append(curr.close / prev.close - 1)
    return returns
