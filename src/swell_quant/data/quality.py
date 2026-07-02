from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from swell_quant.data.sample_data import PriceBar


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: str
    message: str
    symbol: str | None = None
    date: str | None = None


@dataclass(frozen=True)
class DataQualityReport:
    row_count: int
    symbol_count: int
    start_date: str | None
    end_date: str | None
    issue_count: int
    issues: list[QualityIssue]

    @property
    def passed(self) -> bool:
        return self.issue_count == 0


def validate_price_bars(bars: list[PriceBar]) -> DataQualityReport:
    issues: list[QualityIssue] = []
    keys = [(bar.symbol, bar.trade_date) for bar in bars]
    duplicate_keys = {key for key, count in Counter(keys).items() if count > 1}

    for symbol, trade_date in sorted(duplicate_keys):
        issues.append(
            QualityIssue(
                code="duplicate_symbol_date",
                severity="error",
                message="same symbol/date appears more than once",
                symbol=symbol,
                date=trade_date.isoformat(),
            )
        )

    for bar in bars:
        date_text = bar.trade_date.isoformat()
        if min(bar.open, bar.high, bar.low, bar.close) <= 0:
            issues.append(
                QualityIssue(
                    code="non_positive_price",
                    severity="error",
                    message="open/high/low/close must all be positive",
                    symbol=bar.symbol,
                    date=date_text,
                )
            )
        if not (bar.low <= bar.open <= bar.high and bar.low <= bar.close <= bar.high):
            issues.append(
                QualityIssue(
                    code="invalid_ohlc_range",
                    severity="error",
                    message="open and close must stay within low/high range",
                    symbol=bar.symbol,
                    date=date_text,
                )
            )
        if bar.volume < 0:
            issues.append(
                QualityIssue(
                    code="negative_volume",
                    severity="error",
                    message="volume must not be negative",
                    symbol=bar.symbol,
                    date=date_text,
                )
            )
        if bar.benchmark_close <= 0:
            issues.append(
                QualityIssue(
                    code="invalid_benchmark",
                    severity="error",
                    message="benchmark_close must be positive",
                    symbol=bar.symbol,
                    date=date_text,
                )
            )

    dates = sorted({bar.trade_date for bar in bars})
    symbols = {bar.symbol for bar in bars}
    # 质量报告是后续训练/回测的入口门禁，先在数据层暴露所有问题，不在后续阶段静默兜底。
    return DataQualityReport(
        row_count=len(bars),
        symbol_count=len(symbols),
        start_date=dates[0].isoformat() if dates else None,
        end_date=dates[-1].isoformat() if dates else None,
        issue_count=len(issues),
        issues=issues,
    )


def write_quality_report(path: Path, report: DataQualityReport) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "row_count": report.row_count,
        "symbol_count": report.symbol_count,
        "start_date": report.start_date,
        "end_date": report.end_date,
        "issue_count": report.issue_count,
        "passed": report.passed,
        "issues": [asdict(issue) for issue in report.issues],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_quality_report(path: Path) -> DataQualityReport:
    payload = json.loads(path.read_text(encoding="utf-8"))
    issues = [QualityIssue(**issue) for issue in payload["issues"]]
    return DataQualityReport(
        row_count=int(payload["row_count"]),
        symbol_count=int(payload["symbol_count"]),
        start_date=payload["start_date"],
        end_date=payload["end_date"],
        issue_count=int(payload["issue_count"]),
        issues=issues,
    )
