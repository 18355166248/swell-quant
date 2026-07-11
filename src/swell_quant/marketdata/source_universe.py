from __future__ import annotations

from datetime import date
from typing import Any

from swell_quant.marketdata.frames import iter_rows, value
from swell_quant.marketdata.records import UniverseMemberRecord
from swell_quant.marketdata.store import MarketStore


class UniverseSourceError(RuntimeError):
    pass


def fetch_index_constituents(index_code: str, provider: Any) -> list[str]:
    """拉指数**当前**成分股代码（``index_stock_cons``）。

    ``index_code`` 用不带前缀的 6 位指数代码，如沪深300 = "000300"、中证500 = "000905"。
    返回 6 位股票代码列表。数据源只给当前成分（历史需靠快照积累，见 §7-B）。
    """

    frame = provider.index_stock_cons(symbol=index_code)
    symbols: list[str] = []
    for row in iter_rows(frame):
        raw = value(row, "品种代码", "成分券代码", "symbol")
        code = str(raw).split(".")[0].strip().zfill(6)
        if code and code not in symbols:
            symbols.append(code)
    if not symbols:
        raise UniverseSourceError(f"指数 {index_code} 未返回成分股")
    return symbols


def snapshot_index_universe(
    store: MarketStore,
    index_code: str,
    provider: Any,
    snapshot_date: date,
    source: str = "index_stock_cons",
) -> int:
    """拉当前成分股并以 ``snapshot_date`` 落库，返回写入数量。定期调用即自建历史成分。"""

    symbols = fetch_index_constituents(index_code, provider)
    records = [
        UniverseMemberRecord(
            snapshot_date=snapshot_date, index_code=index_code, symbol=symbol, source=source
        )
        for symbol in symbols
    ]
    store.write_universe_members(records)
    return len(records)
