from __future__ import annotations

import csv
import importlib.util
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from swell_quant.research.features import FeatureRow
from swell_quant.research.labels import LabelRow


BASELINE_MODEL_VERSION = "baseline-rule-v1"
DEFAULT_MODEL_TYPE = "lightgbm"
BASELINE_FEATURE_NAMES = [
    "momentum_5d",
    "return_1d",
    "volatility_5d",
    "rsi_6",
    "macd_hist",
    "volume_change_1d",
]
BASELINE_TRAINING_PARAMS: dict[str, float | int | str | bool | None] = {
    "score_formula": (
        "0.7*momentum_5d + 0.2*return_1d - 0.1*volatility_5d "
        "+ 0.05*((rsi_6-50)/100) + 0.05*macd_hist + 0.1*volume_change_1d"
    ),
    "requires_fit": False,
    "random_seed": None,
}


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
    label_gap_days: int = 5
    evaluation_status: str = "not_available"
    evaluation_train_start: str | None = None
    evaluation_train_end: str | None = None
    validation_start: str | None = None
    validation_end: str | None = None
    test_start: str | None = None
    test_end: str | None = None
    metrics: dict[str, float | int | str | None] | None = None
    requested_model_type: str = DEFAULT_MODEL_TYPE
    training_backend: str = "rule_baseline"
    dependency_status: str = "not_checked"
    training_params: dict[str, float | int | str | bool | None] | None = None


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


@dataclass(frozen=True)
class TrainingSampleRow:
    symbol: str
    trade_date: date
    split: str
    future_5d_return: float
    benchmark_5d_return: float
    outperform_benchmark_5d: int
    momentum_5d: float | None
    return_1d: float | None
    volatility_5d: float | None
    rsi_6: float | None
    macd_hist: float | None
    volume_change_1d: float | None


def train_model(
    features: list[FeatureRow],
    labels: list[LabelRow],
    requested_model_type: str = DEFAULT_MODEL_TYPE,
) -> ModelMetadata:
    normalized_type = requested_model_type.strip().lower()
    if normalized_type in {"", DEFAULT_MODEL_TYPE}:
        return train_baseline_model(features, labels, requested_model_type=DEFAULT_MODEL_TYPE)
    if normalized_type in {"rule_baseline", "baseline"}:
        return train_baseline_model(features, labels, requested_model_type="rule_baseline")
    raise ValueError(f"unsupported model type: {requested_model_type}")


def train_baseline_model(
    features: list[FeatureRow],
    labels: list[LabelRow],
    requested_model_type: str = DEFAULT_MODEL_TYPE,
) -> ModelMetadata:
    usable_labels = [
        label
        for label in labels
        if label.future_5d_return is not None and label.outperform_benchmark_5d is not None
    ]
    usable_dates = sorted({label.trade_date for label in usable_labels})
    if not usable_dates:
        raise ValueError("no labeled rows available for baseline model metadata")

    split = build_time_series_evaluation_split(usable_dates)
    metrics = build_baseline_evaluation_metrics(features, usable_labels, split)
    lightgbm_available = is_lightgbm_available()
    dependency_status = "lightgbm_available" if lightgbm_available else "lightgbm_missing"
    normalized_requested_type = requested_model_type.strip().lower() or DEFAULT_MODEL_TYPE
    if normalized_requested_type == "rule_baseline":
        training_backend = "rule_baseline"
        dependency_status = "not_required"
    else:
        training_backend = "rule_baseline_fallback"
    # 当前环境未安装 LightGBM 时显式降级到规则模型；元数据保留目标模型类型，方便页面和报告识别。
    return ModelMetadata(
        model_version=BASELINE_MODEL_VERSION,
        model_type="rule_baseline",
        feature_names=BASELINE_FEATURE_NAMES,
        train_start=usable_dates[0].isoformat(),
        train_end=usable_dates[-1].isoformat(),
        prediction_date=max(row.trade_date for row in features).isoformat(),
        row_count=len(features),
        disclaimer="仅用于研究，不构成投资建议",
        label_gap_days=split["label_gap_days"],
        evaluation_status=str(split["status"]),
        evaluation_train_start=_format_date(split["train_start"]),
        evaluation_train_end=_format_date(split["train_end"]),
        validation_start=_format_date(split["validation_start"]),
        validation_end=_format_date(split["validation_end"]),
        test_start=_format_date(split["test_start"]),
        test_end=_format_date(split["test_end"]),
        metrics=metrics,
        requested_model_type=normalized_requested_type,
        training_backend=training_backend,
        dependency_status=dependency_status,
        training_params=BASELINE_TRAINING_PARAMS,
    )


def is_lightgbm_available() -> bool:
    return importlib.util.find_spec("lightgbm") is not None


def build_time_series_evaluation_split(
    usable_dates: list[date], label_gap_days: int = 5
) -> dict[str, date | int | str | None]:
    min_train_dates = 3
    min_eval_dates = 1
    required = min_train_dates + label_gap_days + min_eval_dates + label_gap_days + min_eval_dates
    if len(usable_dates) < required:
        return {
            "status": "skipped_insufficient_history",
            "label_gap_days": label_gap_days,
            "train_start": usable_dates[0],
            "train_end": usable_dates[-1],
            "validation_start": None,
            "validation_end": None,
            "test_start": None,
            "test_end": None,
        }

    train_start_index = 0
    train_end_index = min_train_dates - 1
    validation_start_index = train_end_index + label_gap_days + 1
    validation_end_index = validation_start_index + min_eval_dates - 1
    test_start_index = validation_end_index + label_gap_days + 1
    # 时间序列评估切分必须保留标签窗口 gap，避免 T+5 标签跨 train/valid/test 边界泄漏。
    return {
        "status": "ready",
        "label_gap_days": label_gap_days,
        "train_start": usable_dates[train_start_index],
        "train_end": usable_dates[train_end_index],
        "validation_start": usable_dates[validation_start_index],
        "validation_end": usable_dates[validation_end_index],
        "test_start": usable_dates[test_start_index],
        "test_end": usable_dates[-1],
    }


def build_baseline_evaluation_metrics(
    features: list[FeatureRow],
    labels: list[LabelRow],
    split: dict[str, date | int | str | None],
) -> dict[str, float | int | str | None]:
    positive_count = sum(1 for label in labels if label.outperform_benchmark_5d)
    metrics: dict[str, float | int | str | None] = {
        "labeled_row_count": len(labels),
        "positive_rate": round(positive_count / len(labels), 6) if labels else None,
        "evaluation_status": str(split["status"]),
    }
    if split["status"] != "ready":
        metrics.update(
            {
                "test_prediction_dates": 0,
                "top1_outperform_rate": None,
                "top3_outperform_rate": None,
            }
        )
        return metrics

    test_start = split["test_start"]
    test_end = split["test_end"]
    if not isinstance(test_start, date) or not isinstance(test_end, date):
        raise ValueError("ready evaluation split must include test window")

    label_by_key = {(label.symbol, label.trade_date): label for label in labels}
    features_by_date: dict[date, list[FeatureRow]] = defaultdict(list)
    for row in features:
        if test_start <= row.trade_date <= test_end:
            features_by_date[row.trade_date].append(row)

    top1_hits = 0
    top1_total = 0
    top3_hits = 0
    top3_total = 0
    for trade_date, rows in sorted(features_by_date.items()):
        scored = [
            (row, _score_feature_row(row))
            for row in rows
            if row.momentum_5d is not None
            and row.return_1d is not None
            and (row.symbol, row.trade_date) in label_by_key
        ]
        if not scored:
            continue
        scored.sort(key=lambda item: (-item[1], item[0].symbol))
        top1_total += 1
        top1_label = label_by_key[(scored[0][0].symbol, trade_date)]
        top1_hits += int(bool(top1_label.outperform_benchmark_5d))
        for row, _score in scored[:3]:
            top3_total += 1
            top3_hits += int(bool(label_by_key[(row.symbol, trade_date)].outperform_benchmark_5d))

    metrics.update(
        {
            "test_prediction_dates": top1_total,
            "top1_outperform_rate": round(top1_hits / top1_total, 6) if top1_total else None,
            "top3_outperform_rate": round(top3_hits / top3_total, 6) if top3_total else None,
        }
    )
    return metrics


def build_training_samples(
    features: list[FeatureRow], labels: list[LabelRow]
) -> list[TrainingSampleRow]:
    usable_labels = [
        label
        for label in labels
        if label.future_5d_return is not None
        and label.benchmark_5d_return is not None
        and label.outperform_benchmark_5d is not None
    ]
    usable_dates = sorted({label.trade_date for label in usable_labels})
    if not usable_dates:
        return []

    split = build_time_series_evaluation_split(usable_dates)
    feature_by_key = {(row.symbol, row.trade_date): row for row in features}
    rows: list[TrainingSampleRow] = []
    for label in sorted(usable_labels, key=lambda item: (item.trade_date, item.symbol)):
        feature = feature_by_key.get((label.symbol, label.trade_date))
        if feature is None:
            continue
        rows.append(
            TrainingSampleRow(
                symbol=label.symbol,
                trade_date=label.trade_date,
                split=_training_split_for_date(label.trade_date, split),
                future_5d_return=float(label.future_5d_return),
                benchmark_5d_return=float(label.benchmark_5d_return),
                outperform_benchmark_5d=int(label.outperform_benchmark_5d),
                momentum_5d=feature.momentum_5d,
                return_1d=feature.return_1d,
                volatility_5d=feature.volatility_5d,
                rsi_6=feature.rsi_6,
                macd_hist=feature.macd_hist,
                volume_change_1d=feature.volume_change_1d,
            )
        )
    return rows


def _training_split_for_date(trade_date: date, split: dict[str, date | int | str | None]) -> str:
    if split["status"] != "ready":
        return "train"
    train_start = split["train_start"]
    train_end = split["train_end"]
    validation_start = split["validation_start"]
    validation_end = split["validation_end"]
    test_start = split["test_start"]
    test_end = split["test_end"]
    if (
        isinstance(train_start, date)
        and isinstance(train_end, date)
        and train_start <= trade_date <= train_end
    ):
        return "train"
    if (
        isinstance(validation_start, date)
        and isinstance(validation_end, date)
        and validation_start <= trade_date <= validation_end
    ):
        return "validation"
    if (
        isinstance(test_start, date)
        and isinstance(test_end, date)
        and test_start <= trade_date <= test_end
    ):
        return "test"
    return "gap"


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
    path.write_text(
        json.dumps(asdict(metadata), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
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
        label_gap_days=int(payload.get("label_gap_days", 5)),
        evaluation_status=payload.get("evaluation_status", "not_available"),
        evaluation_train_start=payload.get("evaluation_train_start"),
        evaluation_train_end=payload.get("evaluation_train_end"),
        validation_start=payload.get("validation_start"),
        validation_end=payload.get("validation_end"),
        test_start=payload.get("test_start"),
        test_end=payload.get("test_end"),
        metrics=payload.get("metrics"),
        requested_model_type=payload.get("requested_model_type", "rule_baseline"),
        training_backend=payload.get(
            "training_backend", payload.get("model_type", "rule_baseline")
        ),
        dependency_status=payload.get("dependency_status", "legacy_not_recorded"),
        training_params=payload.get("training_params"),
    )


def write_training_samples_csv(path: Path, rows: list[TrainingSampleRow]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "symbol",
                "date",
                "split",
                "future_5d_return",
                "benchmark_5d_return",
                "outperform_benchmark_5d",
                *BASELINE_FEATURE_NAMES,
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "symbol": row.symbol,
                    "date": row.trade_date.isoformat(),
                    "split": row.split,
                    "future_5d_return": _format_optional(row.future_5d_return),
                    "benchmark_5d_return": _format_optional(row.benchmark_5d_return),
                    "outperform_benchmark_5d": str(row.outperform_benchmark_5d),
                    "momentum_5d": _format_optional(row.momentum_5d),
                    "return_1d": _format_optional(row.return_1d),
                    "volatility_5d": _format_optional(row.volatility_5d),
                    "rsi_6": _format_optional(row.rsi_6),
                    "macd_hist": _format_optional(row.macd_hist),
                    "volume_change_1d": _format_optional(row.volume_change_1d),
                }
            )
    return path


def read_training_samples_csv(path: Path) -> list[TrainingSampleRow]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return [
            TrainingSampleRow(
                symbol=row["symbol"],
                trade_date=date.fromisoformat(row["date"]),
                split=row["split"],
                future_5d_return=float(row["future_5d_return"]),
                benchmark_5d_return=float(row["benchmark_5d_return"]),
                outperform_benchmark_5d=int(row["outperform_benchmark_5d"]),
                momentum_5d=_parse_optional(row["momentum_5d"]),
                return_1d=_parse_optional(row["return_1d"]),
                volatility_5d=_parse_optional(row["volatility_5d"]),
                rsi_6=_parse_optional(row["rsi_6"]),
                macd_hist=_parse_optional(row["macd_hist"]),
                volume_change_1d=_parse_optional(row["volume_change_1d"]),
            )
            for row in reader
        ]


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
        - (row.volatility_5d or 0.0) * 0.1
        + (((row.rsi_6 or 50.0) - 50.0) / 100.0) * 0.05
        + (row.macd_hist or 0.0) * 0.05
        + (row.volume_change_1d or 0.0) * 0.1
    )


def _format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"


def _parse_optional(value: str) -> float | None:
    return None if value == "" else float(value)


def _format_date(value: date | int | str | None) -> str | None:
    return value.isoformat() if isinstance(value, date) else None
