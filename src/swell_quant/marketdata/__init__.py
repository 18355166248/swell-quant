"""marketdata: 新数据模块（source → store → as_of 服务）。

设计见 docs/data-module-decisions.md。旧 swell_quant.data / swell_quant.storage
是过渡期参考代码，本包一行不依赖它们。
"""

from swell_quant.marketdata.records import (
    BarRecord,
    FundamentalRecord,
    IndexBarRecord,
    ValuationRecord,
)
from swell_quant.marketdata.adjust import apply_start_anchor, normalize_adj_factor
from swell_quant.marketdata.source_bars import (
    BarSourceError,
    build_bar_records,
    build_bars_from_factor_steps,
    fetch_bars,
    fetch_bars_sina,
    sina_symbol,
)
from swell_quant.marketdata.source_calendar import fetch_trade_calendar
from swell_quant.marketdata.source_fundamentals import fetch_fundamentals
from swell_quant.marketdata.source_index import fetch_index_bars_sina
from swell_quant.marketdata.source_valuation import fetch_valuations_baidu
from swell_quant.marketdata.store import MarketStore
from swell_quant.marketdata.collect import (
    CollectionResult,
    SymbolCollectResult,
    collect_bars,
    collect_fundamentals,
    collect_valuations,
)

__all__ = [
    "BarRecord",
    "BarSourceError",
    "CollectionResult",
    "FundamentalRecord",
    "IndexBarRecord",
    "MarketStore",
    "SymbolCollectResult",
    "ValuationRecord",
    "apply_start_anchor",
    "build_bar_records",
    "build_bars_from_factor_steps",
    "collect_bars",
    "collect_fundamentals",
    "collect_valuations",
    "fetch_bars",
    "fetch_bars_sina",
    "fetch_fundamentals",
    "fetch_index_bars_sina",
    "fetch_trade_calendar",
    "fetch_valuations_baidu",
    "normalize_adj_factor",
    "sina_symbol",
]
