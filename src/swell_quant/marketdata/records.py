from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BarRecord:
    """一条标准日线记录：只存客观事实。

    OHLC 是**不复权真实价**；后复权价不入记录，由 adj_factor 派生
    （视图 close*adj_factor）。adj_factor 约定为**起点锚定的后复权累计因子**
    ——序列最早一天为 1.0、随除权向后递增。这样新分红只影响之后的因子，
    历史因子永不被改写（见 docs/data-module-decisions.md §7-A）。
    """

    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    adj_factor: float
    source: str


@dataclass(frozen=True)
class FundamentalRecord:
    """一条财务/基本面事实，双时间轴。

    - ``event_date``：数值所属报告期期末（如 2025-03-31 为一季报）。
    - ``knowledge_date``：该数值首次或**修正后**对外可知之日（公告日）。

    双时间轴是防**财务未来函数**的根：查询只认 ``knowledge_date <= as_of``
    的记录，且财报修正保留为同一 event_date、不同 knowledge_date 的多行
    （见 docs/data-module-decisions.md §4、§7-C）。
    """

    symbol: str
    event_date: date
    knowledge_date: date
    item: str
    value: float
    source: str


@dataclass(frozen=True)
class IndexBarRecord:
    """一条指数日线（基准用）。指数不做复权，只需收盘价即可算基准收益。"""

    index_code: str
    date: date
    close: float
    source: str


@dataclass(frozen=True)
class ValuationRecord:
    """一条每日估值观测（长表/EAV）。

    估值是每日观测的客观事实（如某日的 PE-TTM、PB、总市值），故只需单时间轴
    ``date``；PIT 语义与行情一致（只认 ``date <= as_of``）。用长表而非宽表，既与
    财务表一致，也贴合数据源“单指标一条序列”的真实形态（见 docs/data-module-decisions.md）。

    ``item`` 取值如 ``"pe_ttm" | "pe" | "pb" | "total_mv"``。
    """

    symbol: str
    date: date
    item: str
    value: float
    source: str
