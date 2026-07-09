from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any


FUND_DISCLAIMER = "仅用于研究，不构成投资建议"
FUND_PROFILES = ("conservative", "balanced", "aggressive")


@dataclass(frozen=True)
class FundInfo:
    fund_code: str
    fund_name: str
    fund_type: str
    manager: str
    inception_date: date
    aum_billion: float
    management_fee: float
    custody_fee: float


@dataclass(frozen=True)
class FundNav:
    fund_code: str
    trade_date: date
    nav: float


@dataclass(frozen=True)
class FundMetrics:
    fund_code: str
    fund_name: str
    fund_type: str
    manager: str
    inception_date: date
    aum_billion: float
    management_fee: float
    custody_fee: float
    total_fee: float
    return_1m: float
    return_3m: float
    return_6m: float
    return_1y: float
    max_drawdown: float
    volatility: float
    downside_volatility: float
    age_years: float


@dataclass(frozen=True)
class FundCandidate:
    rank: int
    fund_code: str
    fund_name: str
    fund_type: str
    profile: str
    score: float
    score_level: str
    factor_reasons: tuple[str, ...]
    risk_notes: tuple[str, ...]
    verification_status: str
    verification_label: str
    verification_checks: tuple[str, ...]
    verification_blockers: tuple[str, ...]


def generate_sample_funds() -> tuple[list[FundInfo], list[FundNav]]:
    funds = [
        FundInfo(
            "510300",
            "沪深300ETF样例",
            "宽基指数",
            "指数团队",
            date(2012, 5, 4),
            620.0,
            0.005,
            0.001,
        ),
        FundInfo(
            "159915",
            "创业成长ETF样例",
            "成长指数",
            "指数团队",
            date(2011, 9, 20),
            210.0,
            0.005,
            0.001,
        ),
        FundInfo(
            "110022",
            "稳健混合基金样例",
            "主动权益",
            "样例经理A",
            date(2015, 1, 12),
            86.0,
            0.012,
            0.002,
        ),
        FundInfo(
            "161725",
            "消费主题基金样例",
            "行业主题",
            "样例经理B",
            date(2010, 8, 18),
            135.0,
            0.010,
            0.002,
        ),
    ]
    end = date(2024, 12, 31)
    navs: list[FundNav] = []
    profiles = {
        "510300": (1.0, 0.00045, 0.012),
        "159915": (1.0, 0.00075, 0.022),
        "110022": (1.0, 0.00050, 0.010),
        "161725": (1.0, 0.00035, 0.017),
    }
    for fund in funds:
        base, drift, amplitude = profiles[fund.fund_code]
        for index in range(260):
            current = end - timedelta(days=259 - index)
            cycle = math.sin(index / 13) * amplitude + math.cos(index / 29) * amplitude * 0.5
            nav = round(base * (1 + drift * index + cycle), 4)
            navs.append(FundNav(fund.fund_code, current, max(nav, 0.2)))
    return funds, navs


def write_funds_csv(path: Path, funds: list[FundInfo]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(FundInfo.__dataclass_fields__.keys()))
        writer.writeheader()
        for fund in funds:
            writer.writerow(
                {
                    "fund_code": fund.fund_code,
                    "fund_name": fund.fund_name,
                    "fund_type": fund.fund_type,
                    "manager": fund.manager,
                    "inception_date": fund.inception_date.isoformat(),
                    "aum_billion": f"{fund.aum_billion:.4f}",
                    "management_fee": f"{fund.management_fee:.6f}",
                    "custody_fee": f"{fund.custody_fee:.6f}",
                }
            )
    return path


def write_fund_nav_csv(path: Path, navs: list[FundNav]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["fund_code", "date", "nav"])
        writer.writeheader()
        for nav in navs:
            writer.writerow(
                {
                    "fund_code": nav.fund_code,
                    "date": nav.trade_date.isoformat(),
                    "nav": f"{nav.nav:.4f}",
                }
            )
    return path


def read_funds_csv(path: Path) -> list[FundInfo]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return [
            FundInfo(
                fund_code=row["fund_code"],
                fund_name=row["fund_name"],
                fund_type=row["fund_type"],
                manager=row["manager"],
                inception_date=date.fromisoformat(row["inception_date"]),
                aum_billion=float(row["aum_billion"]),
                management_fee=float(row["management_fee"]),
                custody_fee=float(row["custody_fee"]),
            )
            for row in csv.DictReader(file)
        ]


def read_fund_nav_csv(path: Path) -> list[FundNav]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return [
            FundNav(
                fund_code=row["fund_code"],
                trade_date=date.fromisoformat(row["date"]),
                nav=float(row["nav"]),
            )
            for row in csv.DictReader(file)
        ]


def compute_fund_metrics(funds: list[FundInfo], navs: list[FundNav]) -> list[FundMetrics]:
    navs_by_fund: dict[str, list[FundNav]] = {}
    for nav in navs:
        navs_by_fund.setdefault(nav.fund_code, []).append(nav)

    metrics: list[FundMetrics] = []
    for fund in funds:
        series = sorted(navs_by_fund.get(fund.fund_code, []), key=lambda row: row.trade_date)
        if len(series) < 2:
            continue
        latest = series[-1]
        daily_returns = [
            series[index].nav / series[index - 1].nav - 1.0 for index in range(1, len(series))
        ]
        metrics.append(
            FundMetrics(
                fund_code=fund.fund_code,
                fund_name=fund.fund_name,
                fund_type=fund.fund_type,
                manager=fund.manager,
                inception_date=fund.inception_date,
                aum_billion=fund.aum_billion,
                management_fee=fund.management_fee,
                custody_fee=fund.custody_fee,
                total_fee=fund.management_fee + fund.custody_fee,
                return_1m=_period_return(series, 21),
                return_3m=_period_return(series, 63),
                return_6m=_period_return(series, 126),
                return_1y=_period_return(series, 252),
                max_drawdown=_max_drawdown(series),
                volatility=_annualized_volatility(daily_returns),
                downside_volatility=_annualized_volatility(
                    [value for value in daily_returns if value < 0]
                ),
                age_years=round((latest.trade_date - fund.inception_date).days / 365.25, 2),
            )
        )
    return metrics


def build_fund_candidates(
    metrics: list[FundMetrics], profile: str = "balanced"
) -> list[FundCandidate]:
    if profile not in FUND_PROFILES:
        raise ValueError(f"profile must be one of {FUND_PROFILES}")
    if not metrics:
        return []

    scores = {metric.fund_code: _candidate_score(metric, metrics, profile) for metric in metrics}
    ranked = sorted(metrics, key=lambda metric: scores[metric.fund_code], reverse=True)
    candidates: list[FundCandidate] = []
    for index, metric in enumerate(ranked):
        verification = build_fund_verification(metric)
        candidates.append(
            FundCandidate(
                rank=index + 1,
                fund_code=metric.fund_code,
                fund_name=metric.fund_name,
                fund_type=metric.fund_type,
                profile=profile,
                score=round(scores[metric.fund_code], 4),
                score_level=_score_level(scores[metric.fund_code]),
                factor_reasons=tuple(_factor_reasons(metric, profile)),
                risk_notes=tuple(_risk_notes(metric)),
                verification_status=verification["status"],
                verification_label=verification["label"],
                verification_checks=tuple(verification["checks"]),
                verification_blockers=tuple(verification["blockers"]),
            )
        )
    return candidates


def build_fund_verification(metric: FundMetrics | dict[str, Any]) -> dict[str, Any]:
    """生成买前验证摘要；只判断研究材料是否足够，不给出申购、赎回或仓位建议。"""
    blockers = _verification_blockers(metric)
    status = _verification_status(metric, blockers)
    return {
        "status": status,
        "label": _verification_label(status),
        "checks": _verification_checks(metric),
        "blockers": blockers,
    }


def write_fund_metrics_csv(path: Path, metrics: list[FundMetrics]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(FundMetrics.__dataclass_fields__.keys()))
        writer.writeheader()
        for metric in metrics:
            writer.writerow(_fund_metrics_row(metric))
    return path


def write_fund_candidates_csv(path: Path, candidates: list[FundCandidate]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(FundCandidate.__dataclass_fields__.keys()))
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    "rank": candidate.rank,
                    "fund_code": candidate.fund_code,
                    "fund_name": candidate.fund_name,
                    "fund_type": candidate.fund_type,
                    "profile": candidate.profile,
                    "score": f"{candidate.score:.4f}",
                    "score_level": candidate.score_level,
                    "factor_reasons": "|".join(candidate.factor_reasons),
                    "risk_notes": "|".join(candidate.risk_notes),
                    "verification_status": candidate.verification_status,
                    "verification_label": candidate.verification_label,
                    "verification_checks": "|".join(candidate.verification_checks),
                    "verification_blockers": "|".join(candidate.verification_blockers),
                }
            )
    return path


def read_fund_metrics_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return [_parse_fund_metrics_row(row) for row in csv.DictReader(file)]


def read_fund_candidates_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return [
            {
                "rank": int(row["rank"]),
                "fund_code": row["fund_code"],
                "fund_name": row["fund_name"],
                "fund_type": row["fund_type"],
                "profile": row["profile"],
                "score": float(row["score"]),
                "score_level": row["score_level"],
                "factor_reasons": _split_pipe(row["factor_reasons"]),
                "risk_notes": _split_pipe(row["risk_notes"]),
                "verification_status": row.get("verification_status") or "review",
                "verification_label": row.get("verification_label") or "需补充验证",
                "verification_checks": _split_pipe(row.get("verification_checks", "")),
                "verification_blockers": _split_pipe(row.get("verification_blockers", "")),
            }
            for row in csv.DictReader(file)
        ]


def _period_return(series: list[FundNav], window: int) -> float:
    if len(series) <= window:
        first = series[0]
    else:
        first = series[-window - 1]
    return series[-1].nav / first.nav - 1.0


def _max_drawdown(series: list[FundNav]) -> float:
    peak = series[0].nav
    drawdown = 0.0
    for row in series:
        peak = max(peak, row.nav)
        drawdown = min(drawdown, row.nav / peak - 1.0)
    return drawdown


def _annualized_volatility(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance) * math.sqrt(252)


def _candidate_score(metric: FundMetrics, all_metrics: list[FundMetrics], profile: str) -> float:
    returns = _normalize(metric.return_1y, [item.return_1y for item in all_metrics])
    recent = _normalize(metric.return_6m, [item.return_6m for item in all_metrics])
    drawdown = 1 - _normalize(
        abs(metric.max_drawdown), [abs(item.max_drawdown) for item in all_metrics]
    )
    volatility = 1 - _normalize(metric.volatility, [item.volatility for item in all_metrics])
    fee = 1 - _normalize(metric.total_fee, [item.total_fee for item in all_metrics])
    scale = _normalize(metric.aum_billion, [item.aum_billion for item in all_metrics])
    if profile == "conservative":
        return (
            0.2 * returns
            + 0.1 * recent
            + 0.3 * drawdown
            + 0.2 * volatility
            + 0.1 * fee
            + 0.1 * scale
        )
    if profile == "aggressive":
        return (
            0.3 * returns
            + 0.3 * recent
            + 0.1 * drawdown
            + 0.1 * volatility
            + 0.05 * fee
            + 0.15 * scale
        )
    return (
        0.3 * returns + 0.2 * recent + 0.2 * drawdown + 0.1 * volatility + 0.1 * fee + 0.1 * scale
    )


def _normalize(value: float, values: list[float]) -> float:
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return 0.5
    return (value - minimum) / (maximum - minimum)


def _score_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _factor_reasons(metric: FundMetrics, profile: str) -> list[str]:
    reasons = [
        f"近1年收益 {metric.return_1y:.2%}",
        f"最大回撤 {metric.max_drawdown:.2%}",
        f"总费率 {metric.total_fee:.2%}",
    ]
    if profile == "aggressive":
        reasons.insert(1, f"近6月收益 {metric.return_6m:.2%}")
    if profile == "conservative":
        reasons.insert(1, f"波动率 {metric.volatility:.2%}")
    return reasons[:4]


def _risk_notes(metric: FundMetrics | dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if abs(_metric_value(metric, "max_drawdown")) >= 0.15:
        notes.append("历史回撤偏高")
    if _metric_value(metric, "volatility") >= 0.18:
        notes.append("净值波动偏高")
    if _metric_value(metric, "aum_billion") < 20:
        notes.append("规模偏小")
    if _metric_value(metric, "total_fee") >= 0.015:
        notes.append("费用偏高")
    return notes


def _verification_status(metric: FundMetrics | dict[str, Any], blockers: list[str]) -> str:
    if any("缺少" in blocker or "样例" in blocker for blocker in blockers):
        return "block"
    if blockers or _risk_notes(metric):
        return "review"
    return "ready"


def _verification_label(status: str) -> str:
    if status == "ready":
        return "可进入人工复核"
    if status == "block":
        return "暂不适合决策"
    return "需补充验证"


def _verification_checks(metric: FundMetrics | dict[str, Any]) -> list[str]:
    checks = [
        f"历史净值覆盖 {_metric_value(metric, 'age_years'):.1f} 年",
        f"最大回撤 {_metric_value(metric, 'max_drawdown'):.2%}",
        f"年化波动 {_metric_value(metric, 'volatility'):.2%}",
        f"总费率 {_metric_value(metric, 'total_fee'):.2%}",
        f"规模 {_metric_value(metric, 'aum_billion'):.1f} 亿",
    ]
    if not _risk_notes(metric):
        checks.append("未触发规模、费用、回撤或波动阈值风险")
    return checks


def _verification_blockers(metric: FundMetrics | dict[str, Any]) -> list[str]:
    blockers = [
        "当前为样例基金数据，不能作为真实申购依据",
        "缺少最新基金合同、招募说明书和定期报告复核",
        "缺少真实费用口径、申购赎回限制和销售服务费复核",
        "缺少个人风险承受能力、资金期限和流动性需求输入",
    ]
    if _metric_value(metric, "age_years") < 3:
        blockers.append("历史净值少于 3 年，无法验证完整市场周期")
    if abs(_metric_value(metric, "max_drawdown")) >= 0.15:
        blockers.append("历史最大回撤偏高，需要确认能否承受")
    if _metric_value(metric, "volatility") >= 0.18:
        blockers.append("年化波动偏高，需要确认风险等级匹配")
    if _metric_value(metric, "aum_billion") < 20:
        blockers.append("基金规模偏小，需要复核清盘和流动性风险")
    if _metric_value(metric, "total_fee") >= 0.015:
        blockers.append("总费率偏高，需要比较同类低费率替代品")
    return blockers


def _metric_value(metric: FundMetrics | dict[str, Any], field: str) -> float:
    if isinstance(metric, dict):
        return float(metric[field])
    return float(getattr(metric, field))


def _fund_metrics_row(metric: FundMetrics) -> dict[str, Any]:
    return {
        "fund_code": metric.fund_code,
        "fund_name": metric.fund_name,
        "fund_type": metric.fund_type,
        "manager": metric.manager,
        "inception_date": metric.inception_date.isoformat(),
        "aum_billion": f"{metric.aum_billion:.4f}",
        "management_fee": f"{metric.management_fee:.6f}",
        "custody_fee": f"{metric.custody_fee:.6f}",
        "total_fee": f"{metric.total_fee:.6f}",
        "return_1m": f"{metric.return_1m:.6f}",
        "return_3m": f"{metric.return_3m:.6f}",
        "return_6m": f"{metric.return_6m:.6f}",
        "return_1y": f"{metric.return_1y:.6f}",
        "max_drawdown": f"{metric.max_drawdown:.6f}",
        "volatility": f"{metric.volatility:.6f}",
        "downside_volatility": f"{metric.downside_volatility:.6f}",
        "age_years": f"{metric.age_years:.4f}",
    }


def _parse_fund_metrics_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "fund_code": row["fund_code"],
        "fund_name": row["fund_name"],
        "fund_type": row["fund_type"],
        "manager": row["manager"],
        "inception_date": row["inception_date"],
        "aum_billion": float(row["aum_billion"]),
        "management_fee": float(row["management_fee"]),
        "custody_fee": float(row["custody_fee"]),
        "total_fee": float(row["total_fee"]),
        "return_1m": float(row["return_1m"]),
        "return_3m": float(row["return_3m"]),
        "return_6m": float(row["return_6m"]),
        "return_1y": float(row["return_1y"]),
        "max_drawdown": float(row["max_drawdown"]),
        "volatility": float(row["volatility"]),
        "downside_volatility": float(row["downside_volatility"]),
        "age_years": float(row["age_years"]),
    }


def _split_pipe(value: str) -> list[str]:
    return [item for item in value.split("|") if item]
