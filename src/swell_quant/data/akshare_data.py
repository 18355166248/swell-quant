from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from time import sleep
from typing import Any

from swell_quant.data.sample_data import PriceBar, write_price_bars_csv


class AkshareDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class AkshareSymbolFailure:
    symbol: str
    reason: str


@dataclass(frozen=True)
class AkshareSourceAttempt:
    symbol: str
    source: str
    status: str
    attempts: int
    error: str | None = None


@dataclass(frozen=True)
class AksharePriceFetchResult:
    bars: list[PriceBar]
    requested_symbols: tuple[str, ...]
    succeeded_symbols: tuple[str, ...]
    failed_symbols: tuple[AkshareSymbolFailure, ...]
    source_attempts: tuple[AkshareSourceAttempt, ...]


CSI800_COMPONENT_INDEXES = ("000300", "000905")
CSI800_UNIVERSE_MODES = {"csi800", "hs300_csi500"}


def resolve_akshare_symbols(
    universe_mode: str,
    manual_symbols: tuple[str, ...],
    provider: Any | None = None,
) -> tuple[str, ...]:
    mode = universe_mode.strip().lower()
    if mode == "manual":
        return manual_symbols
    if mode not in CSI800_UNIVERSE_MODES:
        raise ValueError(f"unsupported AKShare universe mode: {universe_mode}")

    akshare = provider or _load_akshare()
    symbols: list[str] = []
    seen: set[str] = set()
    for index_symbol in CSI800_COMPONENT_INDEXES:
        for row in _iter_rows(_fetch_index_cons_frame(akshare, index_symbol)):
            symbol = _normalize_component_symbol(row)
            if symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)
    if not symbols:
        raise ValueError("akshare returned no CSI800 component symbols")
    return tuple(symbols)


def fetch_akshare_price_bars(
    symbols: tuple[str, ...],
    start_date: str,
    end_date: str,
    benchmark_symbol: str = "sh000906",
    provider: Any | None = None,
) -> list[PriceBar]:
    return collect_akshare_price_bars(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        benchmark_symbol=benchmark_symbol,
        provider=provider,
    ).bars


def collect_akshare_price_bars(
    symbols: tuple[str, ...],
    start_date: str,
    end_date: str,
    benchmark_symbol: str = "sh000906",
    provider: Any | None = None,
) -> AksharePriceFetchResult:
    akshare = provider or _load_akshare()
    benchmark_by_date = _fetch_benchmark_close(
        akshare, benchmark_symbol, start_date=start_date, end_date=end_date
    )
    bars: list[PriceBar] = []
    succeeded_symbols: list[str] = []
    failed_symbols: list[AkshareSymbolFailure] = []
    source_attempts: list[AkshareSourceAttempt] = []
    for symbol in symbols:
        try:
            frame, attempts = _fetch_symbol_price_frame(
                akshare, symbol, start_date=start_date, end_date=end_date
            )
            source_attempts.extend(attempts)
            symbol_bars: list[PriceBar] = []
            for row in _iter_rows(frame):
                trade_date = _parse_trade_date(_value(row, "日期", "date"))
                benchmark_close = benchmark_by_date.get(trade_date)
                if benchmark_close is None:
                    continue
                # AKShare 返回前复权日频行情；这里只做字段标准化和基准对齐，不在采集层计算因子或标签。
                symbol_bars.append(
                    PriceBar(
                        symbol=symbol,
                        trade_date=trade_date,
                        open=float(_value(row, "开盘", "open")),
                        high=float(_value(row, "最高", "high")),
                        low=float(_value(row, "最低", "low")),
                        close=float(_value(row, "收盘", "close")),
                        volume=int(float(_value(row, "成交量", "volume"))),
                        benchmark_close=benchmark_close,
                    )
                )
            if symbol_bars:
                bars.extend(symbol_bars)
                succeeded_symbols.append(symbol)
            else:
                failed_symbols.append(
                    AkshareSymbolFailure(
                        symbol=symbol,
                        reason="no_rows_after_benchmark_alignment",
                    )
                )
        except Exception as error:  # noqa: BLE001 - 单只股票失败应记录并继续采集其它标的。
            if isinstance(error, _PriceFrameFetchError):
                source_attempts.extend(error.attempts)
            failed_symbols.append(AkshareSymbolFailure(symbol=symbol, reason=str(error)))
    if not bars:
        # 真实行情源失败时必须保留单标的原因，否则 pipeline 只能看到“无数据”的二次症状，排查不到上游接口或网络问题。
        failure_summary = "; ".join(
            f"{failure.symbol}: {failure.reason}" for failure in failed_symbols[:5]
        )
        detail = f"; failures={failure_summary}" if failure_summary else ""
        raise ValueError(f"akshare returned no price bars after benchmark alignment{detail}")
    return AksharePriceFetchResult(
        bars=sorted(bars, key=lambda bar: (bar.trade_date, bar.symbol)),
        requested_symbols=symbols,
        succeeded_symbols=tuple(succeeded_symbols),
        failed_symbols=tuple(failed_symbols),
        source_attempts=tuple(source_attempts),
    )


def write_akshare_prices_csv(
    path: Path,
    symbols: tuple[str, ...],
    start_date: str,
    end_date: str,
    benchmark_symbol: str = "sh000906",
    provider: Any | None = None,
) -> Path:
    bars = fetch_akshare_price_bars(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        benchmark_symbol=benchmark_symbol,
        provider=provider,
    )
    return write_price_bars_csv(path, bars)


def _load_akshare() -> Any:
    try:
        return importlib.import_module("akshare")
    except ImportError as error:
        raise AkshareDependencyError(
            'DATA_SOURCE=akshare requires optional dependency: python3 -m pip install -e ".[data]"'
        ) from error


@dataclass(frozen=True)
class _PriceFrameFetchError(RuntimeError):
    symbol: str
    attempts: tuple[AkshareSourceAttempt, ...]

    def __str__(self) -> str:
        errors = [attempt.error for attempt in self.attempts if attempt.error]
        return errors[-1] if errors else f"all price sources failed for {self.symbol}"


def _fetch_symbol_price_frame(
    provider: Any,
    symbol: str,
    start_date: str,
    end_date: str,
) -> tuple[Any, list[AkshareSourceAttempt]]:
    attempts: list[AkshareSourceAttempt] = []

    def fetch_akshare() -> Any:
        return provider.stock_zh_a_hist(
            symbol=_akshare_stock_symbol(symbol),
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )

    try:
        frame, attempt = _run_price_source(
            symbol=symbol,
            source="akshare",
            fetcher=fetch_akshare,
        )
        attempts.append(attempt)
        return frame, attempts
    except Exception as error:  # noqa: BLE001 - 失败会进入下一行情源，原始原因写入 attempts。
        attempts.append(_failed_attempt(symbol, "akshare", error))

    try:
        frame, attempt = _run_price_source(
            symbol=symbol,
            source="eastmoney_direct",
            fetcher=lambda: _fetch_eastmoney_price_rows(symbol, start_date, end_date, None),
        )
        attempts.append(attempt)
        return frame, attempts
    except Exception as error:  # noqa: BLE001 - 直连失败后才尝试专用代理 fallback。
        attempts.append(_failed_attempt(symbol, "eastmoney_direct", error))

    proxy_url = _eastmoney_proxy_url()
    if proxy_url:
        try:
            frame, attempt = _run_price_source(
                symbol=symbol,
                source="eastmoney_proxy",
                fetcher=lambda: _fetch_eastmoney_price_rows(
                    symbol, start_date, end_date, proxy_url
                ),
            )
            attempts.append(attempt)
            return frame, attempts
        except Exception as error:  # noqa: BLE001 - 全部失败时由调用方记录单标的失败。
            attempts.append(_failed_attempt(symbol, "eastmoney_proxy", error))

    raise _PriceFrameFetchError(symbol=symbol, attempts=tuple(attempts))


def _run_price_source(
    *,
    symbol: str,
    source: str,
    fetcher: Any,
) -> tuple[Any, AkshareSourceAttempt]:
    last_error: Exception | None = None
    for attempt_index in range(3):
        try:
            return fetcher(), AkshareSourceAttempt(
                symbol=symbol,
                source=source,
                status="passed",
                attempts=attempt_index + 1,
            )
        except Exception as error:  # noqa: BLE001 - 上游数据源错误需要按源重试并保留最后一次原因。
            last_error = error
            if attempt_index < 2:
                sleep(0.25 * (2**attempt_index))
    raise last_error or RuntimeError(f"{source} failed")


def _failed_attempt(symbol: str, source: str, error: Exception) -> AkshareSourceAttempt:
    return AkshareSourceAttempt(
        symbol=symbol,
        source=source,
        status="failed",
        attempts=3,
        error=str(error),
    )


def _fetch_eastmoney_price_rows(
    symbol: str,
    start_date: str,
    end_date: str,
    proxy_url: str | None,
) -> list[dict[str, Any]]:
    try:
        curl_requests = importlib.import_module("curl_cffi.requests")
    except ImportError as error:
        raise AkshareDependencyError(
            'AKShare proxy fallback requires optional dependency: python3 -m pip install -e ".[data]"'
        ) from error

    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "1",
        "secid": _eastmoney_secid(symbol),
        "beg": start_date,
        "end": end_date,
    }
    request_kwargs = {
        "params": params,
        "timeout": 30,
        "impersonate": "chrome",
    }
    if proxy_url:
        request_kwargs["proxy"] = proxy_url
    response = curl_requests.get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        **request_kwargs,
    )
    response.raise_for_status()
    payload = response.json()
    klines = ((payload.get("data") or {}).get("klines")) or []
    return [_parse_eastmoney_kline(kline) for kline in klines]


def _parse_eastmoney_kline(kline: str) -> dict[str, Any]:
    parts = kline.split(",")
    if len(parts) < 6:
        raise ValueError(f"unexpected Eastmoney kline format: {kline}")
    return {
        "日期": parts[0],
        "开盘": float(parts[1]),
        "收盘": float(parts[2]),
        "最高": float(parts[3]),
        "最低": float(parts[4]),
        "成交量": int(float(parts[5])),
    }


def _eastmoney_secid(symbol: str) -> str:
    digits = _akshare_stock_symbol(symbol)
    suffix = symbol.split(".")[1].upper() if "." in symbol else _exchange_suffix(digits, "")
    market = "1" if suffix == "SH" else "0"
    return f"{market}.{digits}"


def _eastmoney_proxy_url() -> str | None:
    # 只认专用的 AKSHARE_HTTP_PROXY 作为 fallback 开关；通用 HTTP(S)_PROXY 常被公司机器或 CI
    # 全局设置，若也当作触发条件，会在采集偶发失败时静默把数据源切到东方财富，行为不可预期。
    return os.getenv("AKSHARE_HTTP_PROXY")


def _fetch_benchmark_close(
    provider: Any, benchmark_symbol: str, start_date: str, end_date: str
) -> dict[date, float]:
    frame = provider.stock_zh_index_daily(symbol=benchmark_symbol)
    start = datetime.strptime(start_date, "%Y%m%d").date()
    end = datetime.strptime(end_date, "%Y%m%d").date()
    closes: dict[date, float] = {}
    for row in _iter_rows(frame):
        trade_date = _parse_trade_date(_value(row, "date", "日期"))
        if start <= trade_date <= end:
            closes[trade_date] = float(_value(row, "close", "收盘"))
    if not closes:
        raise ValueError(f"akshare returned no benchmark rows for {benchmark_symbol}")
    return closes


def _fetch_index_cons_frame(provider: Any, index_symbol: str) -> Any:
    # AKShare 不同版本的指数成分接口名称和来源可能变化；这里按明确优先级尝试，避免把版本差异扩散到 pipeline。
    for method_name in ("index_stock_cons", "index_stock_cons_csindex"):
        method = getattr(provider, method_name, None)
        if method is not None:
            return method(symbol=index_symbol)
    raise AttributeError(
        "akshare provider must expose index_stock_cons or index_stock_cons_csindex"
    )


def _iter_rows(frame: Any) -> list[dict[str, Any]]:
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict("records"))
    return list(frame)


def _value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    raise KeyError(f"missing expected AKShare field; expected one of {keys}")


def _optional_value(row: dict[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _parse_trade_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _akshare_stock_symbol(symbol: str) -> str:
    return symbol.split(".")[0]


def _normalize_component_symbol(row: dict[str, Any]) -> str:
    raw_symbol = str(
        _value(row, "品种代码", "成分券代码", "证券代码", "代码", "stock_code", "code", "symbol")
    ).strip()
    digits = raw_symbol.split(".")[0].zfill(6)
    exchange = _optional_value(row, "交易所", "市场", "exchange")
    suffix = _exchange_suffix(digits, str(exchange) if exchange is not None else "")
    return f"{digits}.{suffix}"


def _exchange_suffix(symbol: str, exchange: str) -> str:
    normalized_exchange = exchange.upper()
    if "SH" in normalized_exchange or "上海" in exchange or "SSE" in normalized_exchange:
        return "SH"
    if "SZ" in normalized_exchange or "深圳" in exchange or "SZSE" in normalized_exchange:
        return "SZ"
    if "BJ" in normalized_exchange or "北京" in exchange or "BSE" in normalized_exchange:
        return "BJ"
    if symbol.startswith(("60", "68", "90")):
        return "SH"
    if symbol.startswith(("00", "30", "20")):
        return "SZ"
    if symbol.startswith(("43", "83", "87", "88")):
        return "BJ"
    raise ValueError(f"cannot infer exchange suffix for AKShare component symbol: {symbol}")
