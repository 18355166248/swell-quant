from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from swell_quant.marketdata.records import BarRecord, FundamentalRecord, ValuationRecord
from swell_quant.marketdata.source_bars import BarSourceError, fetch_bars_sina
from swell_quant.marketdata.source_fundamentals import (
    FundamentalSourceError,
    fetch_fundamentals,
)
from swell_quant.marketdata.source_fundamentals import DEFAULT_ITEMS as FUNDAMENTAL_ITEMS
from swell_quant.marketdata.source_valuation import (
    DEFAULT_ITEMS,
    ValuationSourceError,
    fetch_valuations_baidu,
)
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
    _log_batch(store, result, table_name="stock_bar_1d", source=source,
               started_at=started_at, finished_at=now or datetime.now())
    return result


def _log_batch(
    store: MarketStore,
    result: CollectionResult,
    *,
    table_name: str,
    source: str,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    failures = "; ".join(f"{r.symbol}: {r.reason}" for r in result.failed[:5])
    store.record_ingestion(
        batch_id=result.batch_id,
        table_name=table_name,
        source=source,
        started_at=started_at,
        finished_at=finished_at,
        row_count=result.total_rows,
        status=result.status,
        message=failures,
    )


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


def collect_valuations(
    symbols: Sequence[str],
    store: MarketStore,
    provider: Any,
    *,
    items: tuple[str, ...] = DEFAULT_ITEMS,
    period: str = "近一年",
    source: str = "baidu",
    fetch: Callable[..., list[ValuationRecord]] = fetch_valuations_baidu,
    now: datetime | None = None,
) -> CollectionResult:
    """采集股票池每日估值到 store：增量 + 单票失败隔离 + 批次审计。

    百度估值按 ``period`` 返回整段序列（非日期窗口），故增量方式为“拉整段、只留
    ``date > max_date`` 的新观测”。单票失败记录并继续；整批写一条 ingestion_log。
    """

    started_at = now or datetime.now()
    batch_id = started_at.strftime("%Y%m%dT%H%M%S%f")

    results: list[SymbolCollectResult] = []
    for symbol in symbols:
        try:
            max_date = store.get_max_date(symbol, table="stock_valuation")
            records = fetch(symbol, provider, items=items, period=period, source=source)
            if max_date is not None:
                records = [r for r in records if r.date > max_date]
            if not records:
                results.append(SymbolCollectResult(symbol=symbol, rows=0, status="skipped"))
                continue
            store.write_valuations(records)
            results.append(SymbolCollectResult(symbol=symbol, rows=len(records), status="ok"))
        except ValuationSourceError as error:
            # 估值源空响应：增量时视为已最新，首采时视为失败。
            if store.get_max_date(symbol, table="stock_valuation") is not None:
                results.append(SymbolCollectResult(symbol=symbol, rows=0, status="skipped"))
            else:
                results.append(
                    SymbolCollectResult(symbol=symbol, rows=0, status="failed", reason=str(error))
                )
        except Exception as error:  # noqa: BLE001 - 单票失败应记录并继续采集其它标的。
            results.append(
                SymbolCollectResult(symbol=symbol, rows=0, status="failed", reason=str(error))
            )

    result = CollectionResult(batch_id=batch_id, results=tuple(results))
    _log_batch(store, result, table_name="stock_valuation", source=source,
               started_at=started_at, finished_at=now or datetime.now())
    return result


def collect_fundamentals(
    symbols: Sequence[str],
    store: MarketStore,
    provider: Any,
    periods: Sequence[str],
    *,
    items: tuple[str, ...] = FUNDAMENTAL_ITEMS,
    source: str = "yjbb_em_est",
    fetch: Callable[..., list[FundamentalRecord]] = fetch_fundamentals,
    now: datetime | None = None,
) -> CollectionResult:
    """采集财务到 store：**按报告期驱动**（一次取全市场该期数据，按股票池过滤）。

    业绩报表一次调用返回全 A 股某期数据，故外层循环是 periods 而非 symbols。
    单期失败记录并继续；整批写一条 ingestion_log。``periods`` 如 ("20240331", "20240630")。
    每期的结果记在 SymbolCollectResult 的 symbol 位（此处存报告期）。幂等：同期重采按主键 upsert。
    """

    started_at = now or datetime.now()
    batch_id = started_at.strftime("%Y%m%dT%H%M%S%f")
    symbol_set = set(symbols)

    results: list[SymbolCollectResult] = []
    for period in periods:
        try:
            records = [r for r in fetch(provider, period, items=items, source=source)
                       if r.symbol in symbol_set]
            if not records:
                results.append(SymbolCollectResult(symbol=period, rows=0, status="skipped"))
                continue
            store.write_fundamentals(records)
            results.append(SymbolCollectResult(symbol=period, rows=len(records), status="ok"))
        except FundamentalSourceError as error:
            results.append(
                SymbolCollectResult(symbol=period, rows=0, status="failed", reason=str(error))
            )
        except Exception as error:  # noqa: BLE001 - 单期失败应记录并继续采集其它期。
            results.append(
                SymbolCollectResult(symbol=period, rows=0, status="failed", reason=str(error))
            )

    result = CollectionResult(batch_id=batch_id, results=tuple(results))
    _log_batch(store, result, table_name="stock_fundamental", source=source,
               started_at=started_at, finished_at=now or datetime.now())
    return result


def _to_yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _parse_yyyymmdd(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()
