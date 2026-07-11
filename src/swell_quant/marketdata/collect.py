from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.source_bars import BarSourceError, fetch_bars_sina
from swell_quant.marketdata.store import MarketStore

# fetch 契约：fetch(symbol, start_date, end_date, provider) -> list[BarRecord]
BarFetch = Callable[[str, str, str, Any], list[BarRecord]]


@dataclass(frozen=True)
class SymbolCollectResult:
    symbol: str
    rows: int
    status: str  # "ok" | "skipped" | "failed"
    reason: str | None = None


@dataclass(frozen=True)
class CollectionResult:
    batch_id: str
    results: tuple[SymbolCollectResult, ...]

    @property
    def total_rows(self) -> int:
        return sum(r.rows for r in self.results)

    @property
    def succeeded(self) -> tuple[str, ...]:
        return tuple(r.symbol for r in self.results if r.status == "ok")

    @property
    def failed(self) -> tuple[SymbolCollectResult, ...]:
        return tuple(r for r in self.results if r.status == "failed")

    @property
    def status(self) -> str:
        if self.failed and len(self.failed) == len(self.results):
            return "failed"
        if self.failed:
            return "partial"
        return "ok"


def collect_bars(
    symbols: Sequence[str],
    store: MarketStore,
    provider: Any,
    *,
    default_start: str,
    end_date: str,
    source: str = "sina",
    fetch: BarFetch = fetch_bars_sina,
    now: datetime | None = None,
) -> CollectionResult:
    """采集股票池日线到 store：**增量 + 单票失败隔离 + 批次审计**。

    每只票用 ``get_max_date`` 决定增量窗口：库里没有则从 ``default_start`` 起，
    有则只补 ``max_date+1 .. end_date``（后复权因子上市日锚定，历史不受新分红
    影响，故增量安全，见 §7-A）。已是最新则跳过、不发网络请求。单只失败记录
    原因并继续其它标的；整批写一条 ingestion_log 审计。
    """

    started_at = now or datetime.now()
    batch_id = started_at.strftime("%Y%m%dT%H%M%S%f")
    end_dt = _parse_yyyymmdd(end_date)

    # 有交易日历时，用 <= end_date 的最近交易日作为“已最新”判据，精确跳过空尾窗；
    # 没有日历则退回按日历日 end_date 判断（配合空响应兜底）。见 §7-D。
    calendar_last = store.latest_trading_day(end_dt) if store.has_trade_calendar() else None
    effective_end = calendar_last or end_dt

    results: list[SymbolCollectResult] = []
    for symbol in symbols:
        try:
            results.append(
                _collect_one(
                    symbol, store, provider, default_start, end_date,
                    end_dt, effective_end, source, fetch,
                )
            )
        except Exception as error:  # noqa: BLE001 - 单票失败应记录并继续采集其它标的。
            results.append(SymbolCollectResult(symbol=symbol, rows=0, status="failed", reason=str(error)))

    result = CollectionResult(batch_id=batch_id, results=tuple(results))
    failures = "; ".join(f"{r.symbol}: {r.reason}" for r in result.failed[:5])
    store.record_ingestion(
        batch_id=batch_id,
        table_name="stock_bar_1d",
        source=source,
        started_at=started_at,
        finished_at=now or datetime.now(),
        row_count=result.total_rows,
        status=result.status,
        message=failures,
    )
    return result


def _collect_one(
    symbol: str,
    store: MarketStore,
    provider: Any,
    default_start: str,
    end_date: str,
    end_dt: date,
    effective_end: date,
    source: str,
    fetch: BarFetch,
) -> SymbolCollectResult:
    max_date = store.get_max_date(symbol)
    incremental = max_date is not None
    if not incremental:
        start_date = default_start
    elif max_date >= effective_end:
        # 已到最近交易日（或日历日 end），无需网络请求。
        return SymbolCollectResult(symbol=symbol, rows=0, status="skipped")
    else:
        start_date = _to_yyyymmdd(max_date + timedelta(days=1))

    try:
        bars = fetch(symbol, start_date, end_date, provider)
    except BarSourceError:
        # 增量尾窗常落在非交易日（周末/假期），源返回空属正常，不算失败。
        # 缺 trade_calendar 时无法预判交易日，故以“空响应=已最新”兜底（见 §7-D）。
        if incremental:
            return SymbolCollectResult(symbol=symbol, rows=0, status="skipped")
        raise

    # 源的日期过滤有时不精确：空窗口会带回窗口外的最近一行。必须钳在 end_date 内，
    # 保证“采到 end_date 为止”可复现。
    bars = [bar for bar in bars if bar.date <= end_dt]
    if incremental:
        # 增量只保留真正的新交易日；幂等 upsert 虽能兜底，但过滤后 rows 才等于真正新增。
        bars = [bar for bar in bars if bar.date > max_date]
    if not bars:
        return SymbolCollectResult(symbol=symbol, rows=0, status="skipped")

    store.write_bars(bars)
    return SymbolCollectResult(symbol=symbol, rows=len(bars), status="ok")


def _to_yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _parse_yyyymmdd(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()
