from __future__ import annotations

from datetime import date
from typing import Any

from swell_quant.marketdata.frames import iter_rows, parse_date, value
from swell_quant.marketdata.records import UniverseMemberRecord
from swell_quant.marketdata.store import MarketStore


class UniverseSourceError(RuntimeError):
    pass


def fetch_index_constituents(index_code: str, provider: Any) -> list[tuple[str, date]]:
    """拉指数**当前**成分股及其**纳入日期**（``index_stock_cons``）。

    ``index_code`` 用不带前缀的 6 位指数代码，如沪深300 = "000300"、中证500 = "000905"。
    返回 ``(股票代码, 纳入日期)`` 列表。纳入日期每股各异（源提供），用于 as_of 排除
    当时尚未纳入的成分。数据源只给当前成分（退出的历史成分需靠快照积累，见 §7-B）。
    """

    frame = provider.index_stock_cons(symbol=index_code)
    seen: set[str] = set()
    members: list[tuple[str, date]] = []
    for row in iter_rows(frame):
        raw = value(row, "品种代码", "成分券代码", "symbol")
        code = str(raw).split(".")[0].strip().zfill(6)
        if not code or code in seen:
            continue
        inclusion = parse_date(value(row, "纳入日期", "date"))
        seen.add(code)
        members.append((code, inclusion))
    if not members:
        raise UniverseSourceError(f"指数 {index_code} 未返回成分股")
    return members


def snapshot_index_universe(
    store: MarketStore,
    index_code: str,
    provider: Any,
    snapshot_date: date,
    source: str = "index_stock_cons",
) -> int:
    """拉当前成分股（含纳入日期）并以 ``snapshot_date`` 落库，返回写入数量。

    定期调用即自建历史成分快照；配合 inclusion_date，as_of 查询可排除当时尚未纳入者。
    """

    members = fetch_index_constituents(index_code, provider)
    records = [
        UniverseMemberRecord(
            snapshot_date=snapshot_date,
            index_code=index_code,
            symbol=symbol,
            inclusion_date=inclusion_date,
            source=source,
        )
        for symbol, inclusion_date in members
    ]
    store.write_universe_members(records)
    return len(records)
