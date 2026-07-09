from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from swell_quant.research.funds import FundInfo, FundNav


class FundDataDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class FundSourceAttempt:
    fund_code: str
    source: str
    status: str
    error: str | None = None


@dataclass(frozen=True)
class FundFetchResult:
    funds: list[FundInfo]
    navs: list[FundNav]
    succeeded_codes: tuple[str, ...]
    failed_codes: tuple[dict[str, str], ...]
    attempts: tuple[FundSourceAttempt, ...]
    metadata: dict[str, Any]


def collect_akshare_fund_data(
    *,
    fund_codes: tuple[str, ...],
    start_date: str,
    end_date: str,
    provider: Any | None = None,
) -> FundFetchResult:
    if not fund_codes:
        raise ValueError("fund_codes must include at least one fund code")
    akshare = provider or _load_akshare()
    name_map = _load_fund_name_map(akshare)
    funds: list[FundInfo] = []
    navs: list[FundNav] = []
    succeeded: list[str] = []
    failed: list[dict[str, str]] = []
    attempts: list[FundSourceAttempt] = []

    for code in fund_codes:
        try:
            fund_navs, source = _fetch_fund_navs(akshare, code, start_date, end_date)
            if not fund_navs:
                raise ValueError("fund source returned no NAV rows")
            info = name_map.get(code, {})
            funds.append(
                FundInfo(
                    fund_code=code,
                    fund_name=str(info.get("fund_name") or code),
                    fund_type=str(info.get("fund_type") or "未知类型"),
                    manager="待复核",
                    inception_date=min(row.trade_date for row in fund_navs),
                    aum_billion=0.0,
                    management_fee=0.0,
                    custody_fee=0.0,
                )
            )
            navs.extend(fund_navs)
            succeeded.append(code)
            attempts.append(FundSourceAttempt(code, source, "passed"))
        except Exception as error:  # noqa: BLE001 - 外部数据源失败需要逐基金记录，不能中断全批次。
            failed.append({"fund_code": code, "reason": str(error)})
            attempts.append(FundSourceAttempt(code, "akshare", "failed", str(error)))

    if not succeeded:
        detail = "; ".join(f"{item['fund_code']}={item['reason']}" for item in failed)
        raise ValueError(f"akshare returned no usable fund data: {detail}")

    return FundFetchResult(
        funds=funds,
        navs=navs,
        succeeded_codes=tuple(succeeded),
        failed_codes=tuple(failed),
        attempts=tuple(attempts),
        metadata={
            "data_source": "akshare",
            "fund_codes": list(fund_codes),
            "start_date": start_date,
            "end_date": end_date,
            "succeeded_count": len(succeeded),
            "failed_count": len(failed),
            "note": "真实基金数据只用于研究验证，不构成投资建议",
        },
    )


def _load_akshare() -> Any:
    try:
        return importlib.import_module("akshare")
    except ImportError as error:
        raise FundDataDependencyError(
            'fund trial requires optional dependency: python3 -m pip install -e ".[data]"'
        ) from error


def _load_fund_name_map(provider: Any) -> dict[str, dict[str, str]]:
    try:
        frame = provider.fund_name_em()
    except Exception:  # noqa: BLE001 - 名称接口失败不应阻断净值试跑，候选仍可用代码兜底。
        return {}
    name_map: dict[str, dict[str, str]] = {}
    for row in _iter_rows(frame):
        code = str(_value(row, "基金代码", "代码", "fund_code", "code")).strip()
        if not code or not code[:6].isdigit():
            continue
        code = code[:6]
        name_map[code] = {
            "fund_name": str(_optional_value(row, "基金简称", "基金名称", "name") or code),
            "fund_type": str(_optional_value(row, "基金类型", "类型", "fund_type") or "未知类型"),
        }
    return name_map


def _fetch_fund_navs(
    provider: Any, fund_code: str, start_date: str, end_date: str
) -> tuple[list[FundNav], str]:
    for source, fetcher in (
        (
            "fund_open_fund_info_em",
            lambda: provider.fund_open_fund_info_em(
                symbol=fund_code, indicator="单位净值走势", period="成立来"
            ),
        ),
        (
            "fund_etf_fund_info_em",
            lambda: provider.fund_etf_fund_info_em(
                fund=fund_code, start_date=start_date, end_date=end_date
            ),
        ),
    ):
        try:
            navs = _parse_nav_frame(fetcher(), fund_code, start_date, end_date)
            if navs:
                return navs, source
        except Exception:
            continue
    raise ValueError(f"akshare returned no NAV rows for {fund_code}")


def _parse_nav_frame(frame: Any, fund_code: str, start_date: str, end_date: str) -> list[FundNav]:
    start = _parse_yyyymmdd(start_date)
    end = _parse_yyyymmdd(end_date)
    navs: list[FundNav] = []
    for row in _iter_rows(frame):
        trade_date = _parse_date(_value(row, "净值日期", "日期", "date", "FSRQ"))
        if not (start <= trade_date <= end):
            continue
        nav_value = _value(row, "单位净值", "累计净值", "nav", "DWJZ")
        navs.append(FundNav(fund_code=fund_code, trade_date=trade_date, nav=float(nav_value)))
    return sorted(navs, key=lambda item: item.trade_date)


def _iter_rows(frame: Any) -> list[dict[str, Any]]:
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict("records"))
    return list(frame)


def _value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    raise KeyError(f"missing expected fund field; expected one of {keys}")


def _optional_value(row: dict[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _parse_yyyymmdd(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
