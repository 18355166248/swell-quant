from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from swell_quant.marketdata.records import BarRecord


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

    def get_max_date(self, symbol: str, table: str = "stock_bar_1d") -> date | None:
        """库里该票最新到哪天，供增量采集算窗口。无数据返回 None。"""

        if table not in {"stock_bar_1d"}:
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
