from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from swell_quant.marketdata.records import (
    BarRecord,
    FundamentalRecord,
    IndexBarRecord,
    UniverseMemberRecord,
    ValuationRecord,
)


# 事实表列顺序，写入与读出共用，避免两处漂移。
_BAR_COLUMNS = (
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "adj_factor",
    "source",
)

_CREATE_BAR_TABLE = """
CREATE TABLE IF NOT EXISTS stock_bar_1d (
    symbol VARCHAR,
    date DATE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT,
    amount DOUBLE,
    adj_factor DOUBLE,
    source VARCHAR,
    PRIMARY KEY (symbol, date)
)
"""

# 后复权价 = 视图派生（close*adj_factor…）；只有 raw 价与 adj_factor 是存储的事实。
# 视图保留 adj_factor/source，方便上层知道用了哪个因子、来自哪个源。
_CREATE_BAR_HFQ_VIEW = """
CREATE OR REPLACE VIEW stock_bar_1d_hfq AS
SELECT
    symbol,
    date,
    open * adj_factor AS open,
    high * adj_factor AS high,
    low * adj_factor AS low,
    close * adj_factor AS close,
    volume,
    amount,
    adj_factor,
    source
FROM stock_bar_1d
"""

_UPSERT_BARS = """
INSERT INTO stock_bar_1d (symbol, date, open, high, low, close, volume, amount, adj_factor, source)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (symbol, date) DO UPDATE SET
    open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    volume = excluded.volume,
    amount = excluded.amount,
    adj_factor = excluded.adj_factor,
    source = excluded.source
"""

# 财务：双时间轴，PK 含 knowledge_date → 同一报告期的原始与修正各占一行、都保留。
_CREATE_FUNDAMENTAL_TABLE = """
CREATE TABLE IF NOT EXISTS stock_fundamental (
    symbol VARCHAR,
    event_date DATE,
    knowledge_date DATE,
    item VARCHAR,
    value DOUBLE,
    source VARCHAR,
    PRIMARY KEY (symbol, event_date, knowledge_date, item)
)
"""

_FUNDAMENTAL_COLUMNS = ("symbol", "event_date", "knowledge_date", "item", "value", "source")

_UPSERT_FUNDAMENTALS = """
INSERT INTO stock_fundamental (symbol, event_date, knowledge_date, item, value, source)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (symbol, event_date, knowledge_date, item) DO UPDATE SET
    value = excluded.value,
    source = excluded.source
"""


# 指数日线（基准）：只存收盘价，PK (index_code, date)。
_CREATE_INDEX_BAR_TABLE = """
CREATE TABLE IF NOT EXISTS index_bar (
    index_code VARCHAR,
    date DATE,
    close DOUBLE,
    source VARCHAR,
    PRIMARY KEY (index_code, date)
)
"""

_UPSERT_INDEX_BARS = """
INSERT INTO index_bar (index_code, date, close, source)
VALUES (?, ?, ?, ?)
ON CONFLICT (index_code, date) DO UPDATE SET
    close = excluded.close,
    source = excluded.source
"""


# 估值：每日观测，长表/EAV，单时间轴（date）。PK (symbol, date, item)。
_CREATE_VALUATION_TABLE = """
CREATE TABLE IF NOT EXISTS stock_valuation (
    symbol VARCHAR,
    date DATE,
    item VARCHAR,
    value DOUBLE,
    source VARCHAR,
    PRIMARY KEY (symbol, date, item)
)
"""

_VALUATION_COLUMNS = ("symbol", "date", "item", "value", "source")

_UPSERT_VALUATIONS = """
INSERT INTO stock_valuation (symbol, date, item, value, source)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (symbol, date, item) DO UPDATE SET
    value = excluded.value,
    source = excluded.source
"""


# 成分股快照：按快照日落库当前成分，随时间自建历史（抗幸存者偏差，§7-B）。
_CREATE_UNIVERSE_MEMBER_TABLE = """
CREATE TABLE IF NOT EXISTS universe_member (
    snapshot_date DATE,
    index_code VARCHAR,
    symbol VARCHAR,
    source VARCHAR,
    PRIMARY KEY (snapshot_date, index_code, symbol)
)
"""

_UPSERT_UNIVERSE_MEMBERS = """
INSERT INTO universe_member (snapshot_date, index_code, symbol, source)
VALUES (?, ?, ?, ?)
ON CONFLICT (snapshot_date, index_code, symbol) DO UPDATE SET
    source = excluded.source
"""


# 交易日历：只存交易日（is_open=True）；不在表中的日期即非交易日（假定日历覆盖区间）。
_CREATE_TRADE_CALENDAR = """
CREATE TABLE IF NOT EXISTS trade_calendar (
    date DATE,
    is_open BOOLEAN,
    PRIMARY KEY (date)
)
"""

_UPSERT_CALENDAR = """
INSERT INTO trade_calendar (date, is_open) VALUES (?, ?)
ON CONFLICT (date) DO UPDATE SET is_open = excluded.is_open
"""


# 采集审计：每批次一行，记录源/时间/行数/成败，任何数据可追溯到哪次采集。
_CREATE_INGESTION_LOG = """
CREATE TABLE IF NOT EXISTS ingestion_log (
    batch_id VARCHAR,
    table_name VARCHAR,
    source VARCHAR,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    row_count BIGINT,
    status VARCHAR,
    message VARCHAR
)
"""

_INGESTION_LOG_COLUMNS = (
    "batch_id",
    "table_name",
    "source",
    "started_at",
    "finished_at",
    "row_count",
    "status",
    "message",
)


class MarketStore:
    """行情数据的 Repository：干净读写 API，裸 SQL 不外泄到上层。

    引擎为 DuckDB（列存、单文件、零运维）；测试传 ``:memory:`` 即秒级、
    不依赖文件与网络。设计见 docs/data-module-decisions.md。
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        import duckdb

        self._connection = duckdb.connect(str(path))
        self._connection.execute(_CREATE_BAR_TABLE)
        self._connection.execute(_CREATE_BAR_HFQ_VIEW)
        self._connection.execute(_CREATE_FUNDAMENTAL_TABLE)
        self._connection.execute(_CREATE_VALUATION_TABLE)
        self._connection.execute(_CREATE_INDEX_BAR_TABLE)
        self._connection.execute(_CREATE_UNIVERSE_MEMBER_TABLE)
        self._connection.execute(_CREATE_TRADE_CALENDAR)
        self._connection.execute(_CREATE_INGESTION_LOG)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> MarketStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def write_bars(self, records: Sequence[BarRecord]) -> None:
        """幂等写入：按 (symbol, date) 冲突则更新。重复灌同一批，行数不增、值被覆盖。"""

        if not records:
            return
        rows = [
            (
                record.symbol,
                record.date,
                record.open,
                record.high,
                record.low,
                record.close,
                record.volume,
                record.amount,
                record.adj_factor,
                record.source,
            )
            for record in records
        ]
        self._connection.executemany(_UPSERT_BARS, rows)

    def get_bars(
        self, symbols: Sequence[str], as_of: date, lookback: int
    ) -> list[BarRecord]:
        """as_of 查询：每只票取 date <= as_of 的最近 ``lookback`` 条，按日期升序返回。

        这是存储层的灵魂——只给出 as_of 当天“已知”的数据，杜绝行情未来函数。
        """

        return self._query_bars("stock_bar_1d", symbols, as_of, lookback)

    def get_bars_hfq(
        self, symbols: Sequence[str], as_of: date, lookback: int
    ) -> list[BarRecord]:
        """同 get_bars，但价格为后复权（读视图，派生自 raw 价 * adj_factor）。"""

        return self._query_bars("stock_bar_1d_hfq", symbols, as_of, lookback)

    def write_valuations(self, records: Sequence[ValuationRecord]) -> None:
        """幂等写入每日估值（长表）。"""

        if not records:
            return
        rows = [
            (record.symbol, record.date, record.item, record.value, record.source)
            for record in records
        ]
        self._connection.executemany(_UPSERT_VALUATIONS, rows)

    def get_valuations(
        self, symbols: Sequence[str], as_of: date, lookback: int = 1
    ) -> list[ValuationRecord]:
        """as_of 查询：每个 (symbol, item) 取 date <= as_of 的最近 ``lookback`` 条，升序返回。"""

        if not symbols or lookback <= 0:
            return []
        placeholders = ", ".join("?" for _ in symbols)
        query = f"""
        SELECT {", ".join(_VALUATION_COLUMNS)} FROM (
            SELECT {", ".join(_VALUATION_COLUMNS)},
                   ROW_NUMBER() OVER (PARTITION BY symbol, item ORDER BY date DESC) AS rn
            FROM stock_valuation
            WHERE symbol IN ({placeholders}) AND date <= ?
        )
        WHERE rn <= ?
        ORDER BY symbol, item, date
        """
        params: list[Any] = [*symbols, as_of, lookback]
        rows = self._connection.execute(query, params).fetchall()
        return [_row_to_valuation(row) for row in rows]

    def write_fundamentals(self, records: Sequence[FundamentalRecord]) -> None:
        """幂等写入财务事实。财报修正是**新的一行**（不同 knowledge_date），历史保留。"""

        if not records:
            return
        rows = [
            (
                record.symbol,
                record.event_date,
                record.knowledge_date,
                record.item,
                record.value,
                record.source,
            )
            for record in records
        ]
        self._connection.executemany(_UPSERT_FUNDAMENTALS, rows)

    def get_fundamentals(
        self, symbols: Sequence[str], as_of: date
    ) -> list[FundamentalRecord]:
        """point-in-time 查询：只认 as_of 当天已公告的数据，杜绝财务未来函数。

        对每只票的每个 item，取 ``knowledge_date <= as_of`` 中 event_date 最新的
        报告期、再取其 knowledge_date 最新的一条（即当时能看到的最新修正）。
        """

        if not symbols:
            return []
        placeholders = ", ".join("?" for _ in symbols)
        query = f"""
        SELECT {", ".join(_FUNDAMENTAL_COLUMNS)} FROM (
            SELECT {", ".join(_FUNDAMENTAL_COLUMNS)},
                   ROW_NUMBER() OVER (
                       PARTITION BY symbol, item
                       ORDER BY event_date DESC, knowledge_date DESC
                   ) AS rn
            FROM stock_fundamental
            WHERE symbol IN ({placeholders}) AND knowledge_date <= ?
        )
        WHERE rn = 1
        ORDER BY symbol, item
        """
        params: list[Any] = [*symbols, as_of]
        rows = self._connection.execute(query, params).fetchall()
        return [_row_to_fundamental(row) for row in rows]

    def write_trade_calendar(self, trading_days: Sequence[date]) -> None:
        """幂等写入交易日历（只存交易日）。"""

        if not trading_days:
            return
        self._connection.executemany(_UPSERT_CALENDAR, [(day, True) for day in trading_days])

    def has_trade_calendar(self) -> bool:
        return bool(
            self._connection.execute("SELECT count(*) FROM trade_calendar").fetchone()[0]
        )

    def is_trading_day(self, day: date) -> bool:
        row = self._connection.execute(
            "SELECT is_open FROM trade_calendar WHERE date = ?", [day]
        ).fetchone()
        return bool(row and row[0])

    def latest_trading_day(self, on_or_before: date) -> date | None:
        """<= on_or_before 的最近交易日；日历为空或无更早交易日则 None。"""

        row = self._connection.execute(
            "SELECT max(date) FROM trade_calendar WHERE date <= ? AND is_open", [on_or_before]
        ).fetchone()
        return row[0] if row else None

    def trading_days(self, start: date, end: date) -> list[date]:
        """[start, end] 闭区间内的交易日，升序。"""

        rows = self._connection.execute(
            "SELECT date FROM trade_calendar WHERE date >= ? AND date <= ? AND is_open "
            "ORDER BY date",
            [start, end],
        ).fetchall()
        return [row[0] for row in rows]

    def record_ingestion(
        self,
        *,
        batch_id: str,
        table_name: str,
        source: str,
        started_at: datetime,
        finished_at: datetime,
        row_count: int,
        status: str,
        message: str = "",
    ) -> None:
        """写一条采集审计。批次审计只增不改，是数据可追溯与可复现的凭据。"""

        self._connection.execute(
            f"INSERT INTO ingestion_log ({', '.join(_INGESTION_LOG_COLUMNS)}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [batch_id, table_name, source, started_at, finished_at, row_count, status, message],
        )

    def get_ingestion_log(self) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            f"SELECT {', '.join(_INGESTION_LOG_COLUMNS)} FROM ingestion_log ORDER BY started_at"
        ).fetchall()
        return [dict(zip(_INGESTION_LOG_COLUMNS, row)) for row in rows]

    def get_bars_hfq_forward(
        self, symbols: Sequence[str], start: date, horizon: int
    ) -> list[BarRecord]:
        """研究/评估用**前视**查询：每票取 date >= start 的最早 ``horizon``+1 根后复权行情。

        ⚠️ 这是有意的“看向未来”查询，仅用于计算**已实现**的未来收益（如 IC 评估），
        **绝不可**用于因子计算——因子只能走 as_of 接口。返回按 (symbol, date) 升序。
        """

        if not symbols or horizon <= 0:
            return []
        placeholders = ", ".join("?" for _ in symbols)
        query = f"""
        SELECT {", ".join(_BAR_COLUMNS)} FROM (
            SELECT {", ".join(_BAR_COLUMNS)},
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date ASC) AS rn
            FROM stock_bar_1d_hfq
            WHERE symbol IN ({placeholders}) AND date >= ?
        )
        WHERE rn <= ?
        ORDER BY symbol, date
        """
        params: list[Any] = [*symbols, start, horizon + 1]
        rows = self._connection.execute(query, params).fetchall()
        return [_row_to_bar(row) for row in rows]

    def write_universe_members(self, records: Sequence[UniverseMemberRecord]) -> None:
        """幂等写入成分股快照。"""

        if not records:
            return
        rows = [(r.snapshot_date, r.index_code, r.symbol, r.source) for r in records]
        self._connection.executemany(_UPSERT_UNIVERSE_MEMBERS, rows)

    def get_universe(self, index_code: str, as_of: date) -> list[str]:
        """as_of 当天可知的成分股：取 snapshot_date <= as_of 的**最近一次**快照，升序返回。

        用最近历史快照近似当时成分，比“永远用今天的成分”更抗幸存者偏差（§7-B）。
        as_of 早于任何快照则返回空。
        """

        query = """
        SELECT symbol FROM universe_member
        WHERE index_code = ? AND snapshot_date = (
            SELECT max(snapshot_date) FROM universe_member
            WHERE index_code = ? AND snapshot_date <= ?
        )
        ORDER BY symbol
        """
        rows = self._connection.execute(query, [index_code, index_code, as_of]).fetchall()
        return [row[0] for row in rows]

    def write_index_bars(self, records: Sequence[IndexBarRecord]) -> None:
        """幂等写入指数日线。"""

        if not records:
            return
        rows = [(r.index_code, r.date, r.close, r.source) for r in records]
        self._connection.executemany(_UPSERT_INDEX_BARS, rows)

    def get_index_bar_forward(
        self, index_code: str, start: date, horizon: int
    ) -> list[IndexBarRecord]:
        """研究/评估用**前视**查询：取该指数 date >= start 的最早 ``horizon``+1 根，升序。

        用于算基准在持有期的已实现收益。与个股前视查询同理，不用于因子计算。
        """

        if horizon <= 0:
            return []
        query = """
        SELECT index_code, date, close, source FROM (
            SELECT index_code, date, close, source,
                   ROW_NUMBER() OVER (ORDER BY date ASC) AS rn
            FROM index_bar
            WHERE index_code = ? AND date >= ?
        )
        WHERE rn <= ?
        ORDER BY date
        """
        rows = self._connection.execute(query, [index_code, start, horizon + 1]).fetchall()
        return [
            IndexBarRecord(index_code=row[0], date=row[1], close=row[2], source=row[3])
            for row in rows
        ]

    def get_max_date(self, symbol: str, table: str = "stock_bar_1d") -> date | None:
        """库里该票最新到哪天，供增量采集算窗口。无数据返回 None。"""

        if table not in {"stock_bar_1d", "stock_valuation"}:
            raise ValueError(f"不支持的表：{table}")
        result = self._connection.execute(
            f"SELECT max(date) FROM {table} WHERE symbol = ?", [symbol]
        ).fetchone()
        return result[0] if result else None

    def _query_bars(
        self, table: str, symbols: Sequence[str], as_of: date, lookback: int
    ) -> list[BarRecord]:
        if table not in {"stock_bar_1d", "stock_bar_1d_hfq"}:
            raise ValueError(f"不支持的表：{table}")
        if not symbols or lookback <= 0:
            return []
        placeholders = ", ".join("?" for _ in symbols)
        # 按 symbol 分区、日期倒序编号，取每票最近 lookback 条；外层再按日期升序还原。
        query = f"""
        SELECT {", ".join(_BAR_COLUMNS)} FROM (
            SELECT {", ".join(_BAR_COLUMNS)},
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
            FROM {table}
            WHERE symbol IN ({placeholders}) AND date <= ?
        )
        WHERE rn <= ?
        ORDER BY symbol, date
        """
        params: list[Any] = [*symbols, as_of, lookback]
        rows = self._connection.execute(query, params).fetchall()
        return [_row_to_bar(row) for row in rows]


def _row_to_valuation(row: tuple[Any, ...]) -> ValuationRecord:
    return ValuationRecord(
        symbol=row[0],
        date=row[1],
        item=row[2],
        value=row[3],
        source=row[4],
    )


def _row_to_fundamental(row: tuple[Any, ...]) -> FundamentalRecord:
    return FundamentalRecord(
        symbol=row[0],
        event_date=row[1],
        knowledge_date=row[2],
        item=row[3],
        value=row[4],
        source=row[5],
    )


def _row_to_bar(row: tuple[Any, ...]) -> BarRecord:
    return BarRecord(
        symbol=row[0],
        date=row[1],
        open=row[2],
        high=row[3],
        low=row[4],
        close=row[5],
        volume=int(row[6]),
        amount=row[7],
        adj_factor=row[8],
        source=row[9],
    )
