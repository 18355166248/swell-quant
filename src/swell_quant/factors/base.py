from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date

from swell_quant.marketdata.store import MarketStore

# 截面因子值：symbol -> 值；数据不足记 None（保留该票、由预处理层决定如何处理缺失）。
FactorValues = dict[str, float | None]


class Factor(ABC):
    """截面因子的统一接口。

    ``compute(store, symbols, as_of)`` 在 as_of 当天、给定股票池上产出每票一个值。
    实现只允许经 store 的 as_of 接口取数（get_bars_hfq / get_valuations /
    get_fundamentals），从而不引入未来函数。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """因子名，用于列名与归因（如 "momentum_20d"）。"""

    @abstractmethod
    def compute(self, store: MarketStore, symbols: Sequence[str], as_of: date) -> FactorValues: ...
