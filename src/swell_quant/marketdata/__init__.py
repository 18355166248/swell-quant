"""marketdata: 新数据模块（source → store → as_of 服务）。

设计见 docs/data-module-decisions.md。旧 swell_quant.data / swell_quant.storage
是过渡期参考代码，本包一行不依赖它们。
"""

from swell_quant.marketdata.records import BarRecord, FundamentalRecord
from swell_quant.marketdata.adjust import apply_start_anchor, normalize_adj_factor
from swell_quant.marketdata.source_bars import (
    BarSourceError,
    build_bar_records,
    build_bars_from_factor_steps,
    fetch_bars,
)
from swell_quant.marketdata.store import MarketStore

__all__ = [
    "BarRecord",
    "BarSourceError",
    "FundamentalRecord",
    "MarketStore",
    "apply_start_anchor",
    "build_bar_records",
    "build_bars_from_factor_steps",
    "fetch_bars",
    "normalize_adj_factor",
]
