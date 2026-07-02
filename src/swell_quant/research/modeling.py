from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from swell_quant.research.features import FeatureRow
from swell_quant.research.labels import LabelRow


BASELINE_MODEL_VERSION = "baseline-rule-v1"


@dataclass(frozen=True)
class ModelMetadata:
    model_version: str
    model_type: str
    feature_names: list[str]
    train_start: str
    train_end: str
    prediction_date: str
    row_count: int
    disclaimer: str


@dataclass(frozen=True)
class PredictionRow:
    symbol: str
    trade_date: date
    model_version: str
    score: float
    rank: int
    return_1d: float | None
    momentum_5d: float | None
    volume_change_1d: float | None


def train_baseline_model(features: list[FeatureRow], labels: list[LabelRow]) -> ModelMetadata:
    usable_dates = sorted(
        {
            label.trade_date
            for label in labels
            if label.future_5d_return is not None and label.outperform_benchmark_5d is not None
        }
    )
    if not usable_dates:
        raise ValueError("no labeled rows available for baseline model metadata")

    # baseline 只记录可复现元数据，不拟合参数；后续接 LightGBM 时沿用同一模型产物接口。
    return ModelMetadata(
        model_version=BASELINE_MODEL_VERSION,
        model_type="rule_baseline",
        feature_names=["momentum_5d", "return_1d", "volume_change_1d"],
        train_start=usable_dates[0].isoformat(),
        train_end=usable_dates[-1].isoformat(),
        prediction_date=max(row.trade_date for row in features).isoformat(),
        row_count=len(features),
        disclaimer="仅用于研究，不构成投资建议",
    )


def generate_predictions(
    features: list[FeatureRow], model_version: str = BASELINE_MODEL_VERSION
) -> list[PredictionRow]:
    latest_date = max(row.trade_date for row in features)
    latest_rows = [row for row in features if row.trade_date == latest_date]

    scored = [
        (
            row,
            _score_feature_row(row),
        )
        for row in latest_rows
        if row.momentum_5d is not None and row.return_1d is not None
    ]
    scored.sort(key=lambda item: (-item[1], item[0].symbol))

    return [
        PredictionRow(
            symbol=row.symbol,
            trade_date=row.trade_date,
            model_version=model_version,
            score=score,
            rank=index + 1,
            return_1d=row.return_1d,
            momentum_5d=row.momentum_5d,
            volume_change_1d=row.volume_change_1d,
        )
        for index, (row, score) in enumerate(scored)
    ]


def generate_historical_predictions(
    features: list[FeatureRow], model_version: str = BASELINE_MODEL_VERSION
) -> list[PredictionRow]:
    by_date: dict[date, list[FeatureRow]] = defaultdict(list)
    for row in features:
        by_date[row.trade_date].append(row)

    predictions: list[PredictionRow] = []
    for trade_date, rows in sorted(by_date.items()):
        scored = [
            (row, _score_feature_row(row))
            for row in rows
            if row.momentum_5d is not None and row.return_1d is not None
        ]
        scored.sort(key=lambda item: (-item[1], item[0].symbol))
        for index, (row, score) in enumerate(scored):
            predictions.append(
                PredictionRow(
                    symbol=row.symbol,
                    trade_date=trade_date,
                    model_version=model_version,
                    score=score,
                    rank=index + 1,
                    return_1d=row.return_1d,
                    momentum_5d=row.momentum_5d,
                    volume_change_1d=row.volume_change_1d,
                )
            )

    return predictions


def write_model_metadata(path: Path, metadata: ModelMetadata) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(metadata), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_model_metadata(path: Path) -> ModelMetadata:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ModelMetadata(
        model_version=payload["model_version"],
        model_type=payload["model_type"],
        feature_names=list(payload["feature_names"]),
        train_start=payload["train_start"],
        train_end=payload["train_end"],
        prediction_date=payload["prediction_date"],
        row_count=int(payload["row_count"]),
        disclaimer=payload["disclaimer"],
    )


def write_predictions_csv(path: Path, rows: list[PredictionRow]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "symbol",
                "date",
                "model_version",
                "score",
                "rank",
                "return_1d",
                "momentum_5d",
                "volume_change_1d",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "symbol": row.symbol,
                    "date": row.trade_date.isoformat(),
                    "model_version": row.model_version,
                    "score": f"{row.score:.8f}",
                    "rank": str(row.rank),
                    "return_1d": _format_optional(row.return_1d),
                    "momentum_5d": _format_optional(row.momentum_5d),
                    "volume_change_1d": _format_optional(row.volume_change_1d),
                }
            )
    return path


def read_predictions_csv(path: Path) -> list[PredictionRow]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return [
            PredictionRow(
                symbol=row["symbol"],
                trade_date=date.fromisoformat(row["date"]),
                model_version=row["model_version"],
                score=float(row["score"]),
                rank=int(row["rank"]),
                return_1d=_parse_optional(row["return_1d"]),
                momentum_5d=_parse_optional(row["momentum_5d"]),
                volume_change_1d=_parse_optional(row["volume_change_1d"]),
            )
            for row in reader
        ]


def _score_feature_row(row: FeatureRow) -> float:
    # baseline 只使用当日已生成的特征，权重固定，确保离线链路可复现且不读取标签。
    return (
        (row.momentum_5d or 0.0) * 0.7
        + (row.return_1d or 0.0) * 0.2
        + (row.volume_change_1d or 0.0) * 0.1
    )


def _format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"


def _parse_optional(value: str) -> float | None:
    return None if value == "" else float(value)
