from __future__ import annotations

import csv
import importlib
import importlib.util
import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from math import sqrt
from pathlib import Path
from typing import Any

from swell_quant.research.features import FeatureRow
from swell_quant.research.labels import LabelRow


BASELINE_MODEL_VERSION = "baseline-rule-v1"
LIGHTGBM_MODEL_VERSION = "lightgbm-v1"
LATEST_MODEL_METADATA_FILENAME = "latest_model.json"
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
BASELINE_FEATURE_WEIGHTS = {
    "momentum_5d": 0.7,
    "return_1d": 0.2,
    "volatility_5d": -0.1,
    "rsi_6": 0.05,
    "macd_hist": 0.05,
    "volume_change_1d": 0.1,
}
LIGHTGBM_TRAINING_PARAMS: dict[str, float | int | str | bool | None] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "learning_rate": 0.05,
    "num_leaves": 7,
    "min_data_in_leaf": 1,
    # num_boost_round 是早停的上限；有验证集时按验证 logloss 早停，没有验证集时才跑满。
    "num_boost_round": 200,
    "early_stopping_rounds": 20,
    "seed": 42,
    "deterministic": True,
    "force_col_wise": True,
    "verbosity": -1,
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
    model_artifact_path: str | None = None
    feature_importance: list[dict[str, float | int | str]] | None = None


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
    model_output_path: Path | None = None,
) -> ModelMetadata:
    normalized_type = requested_model_type.strip().lower()
    if normalized_type in {"", DEFAULT_MODEL_TYPE}:
        if is_lightgbm_available():
            return train_lightgbm_model(features, labels, model_output_path=model_output_path)
        return train_baseline_model(features, labels, requested_model_type=DEFAULT_MODEL_TYPE)
    if normalized_type in {"rule_baseline", "baseline"}:
        return train_baseline_model(features, labels, requested_model_type="rule_baseline")
    raise ValueError(f"unsupported model type: {requested_model_type}")


def train_lightgbm_model(
    features: list[FeatureRow],
    labels: list[LabelRow],
    model_output_path: Path | None = None,
) -> ModelMetadata:
    lightgbm = _load_lightgbm_module()
    training_samples = build_training_samples(features, labels)
    train_rows = [row for row in training_samples if row.split == "train"]
    validation_rows = [row for row in training_samples if row.split == "validation"]
    test_rows = [row for row in training_samples if row.split == "test"]
    if not train_rows:
        raise ValueError("no training rows available for lightgbm model")

    numpy = importlib.import_module("numpy")
    params = dict(LIGHTGBM_TRAINING_PARAMS)
    num_boost_round = int(params.pop("num_boost_round"))
    early_stopping_rounds = int(params.pop("early_stopping_rounds"))
    train_set = lightgbm.Dataset(
        numpy.asarray([_feature_vector_from_sample(row) for row in train_rows], dtype=float),
        label=numpy.asarray([row.outperform_benchmark_5d for row in train_rows], dtype=float),
        feature_name=BASELINE_FEATURE_NAMES,
    )
    callbacks = [lightgbm.log_evaluation(0)]
    valid_sets = None
    # 有独立验证集时按验证 logloss 早停，避免固定轮数下的过拟合或欠拟合；无验证集只能跑满上限。
    if validation_rows:
        valid_sets = [
            lightgbm.Dataset(
                numpy.asarray(
                    [_feature_vector_from_sample(row) for row in validation_rows], dtype=float
                ),
                label=numpy.asarray(
                    [row.outperform_benchmark_5d for row in validation_rows], dtype=float
                ),
                reference=train_set,
                feature_name=BASELINE_FEATURE_NAMES,
            )
        ]
        callbacks.append(lightgbm.early_stopping(early_stopping_rounds, verbose=False))
    booster = lightgbm.train(
        params,
        train_set,
        num_boost_round=num_boost_round,
        valid_sets=valid_sets,
        valid_names=["validation"] if valid_sets else None,
        callbacks=callbacks,
    )
    best_iteration = (
        booster.best_iteration if booster.best_iteration else booster.current_iteration()
    )
    if model_output_path is not None:
        model_output_path.parent.mkdir(parents=True, exist_ok=True)
        booster.save_model(str(model_output_path), num_iteration=best_iteration)

    split_dates = sorted({row.trade_date for row in training_samples})
    metrics = build_lightgbm_evaluation_metrics(booster, training_samples)
    metrics["num_boost_round_used"] = best_iteration
    metrics["early_stopping_applied"] = bool(validation_rows)
    metrics.update(
        build_walk_forward_metrics(
            features,
            labels,
            score_fn=lambda row: _predict_scores(booster, [_feature_vector_from_feature(row)])[0],
        )
    )
    # LightGBM 训练只使用 train split；validation/test 仅用于离线评估，确保监督标签不会回流到同日预测特征。
    return ModelMetadata(
        model_version=LIGHTGBM_MODEL_VERSION,
        model_type="lightgbm",
        feature_names=BASELINE_FEATURE_NAMES,
        train_start=min(row.trade_date for row in train_rows).isoformat(),
        train_end=max(row.trade_date for row in train_rows).isoformat(),
        prediction_date=max(row.trade_date for row in features).isoformat(),
        row_count=len(features),
        disclaimer="仅用于研究，不构成投资建议",
        label_gap_days=5,
        evaluation_status="ready"
        if validation_rows and test_rows
        else "skipped_insufficient_history",
        evaluation_train_start=min(row.trade_date for row in train_rows).isoformat(),
        evaluation_train_end=max(row.trade_date for row in train_rows).isoformat(),
        validation_start=min((row.trade_date for row in validation_rows), default=None).isoformat()
        if validation_rows
        else None,
        validation_end=max((row.trade_date for row in validation_rows), default=None).isoformat()
        if validation_rows
        else None,
        test_start=min((row.trade_date for row in test_rows), default=None).isoformat()
        if test_rows
        else None,
        test_end=max((row.trade_date for row in test_rows), default=None).isoformat()
        if test_rows
        else None,
        metrics={
            **metrics,
            "labeled_row_count": len(training_samples),
            "training_row_count": len(train_rows),
            "validation_row_count": len(validation_rows),
            "test_row_count": len(test_rows),
            "evaluation_date_count": len(split_dates),
        },
        requested_model_type=DEFAULT_MODEL_TYPE,
        training_backend="lightgbm",
        dependency_status="lightgbm_available",
        training_params=LIGHTGBM_TRAINING_PARAMS,
        model_artifact_path=str(model_output_path) if model_output_path is not None else None,
        feature_importance=build_lightgbm_feature_importance(booster),
    )


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
    metrics.update(build_walk_forward_metrics(features, usable_labels))
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
        feature_importance=build_baseline_feature_importance(),
    )


def is_lightgbm_available() -> bool:
    return importlib.util.find_spec("lightgbm") is not None


def _load_lightgbm_module() -> Any:
    return importlib.import_module("lightgbm")


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


def build_rank_signal_metrics(
    scored_by_date: dict[date, list[tuple[float, float]]],
    quantile_fraction: float = 1.0 / 3.0,
) -> dict[str, float | int | None]:
    """基于每日截面的 (预测分数, 超额收益) 计算信号质量指标。

    - IC：分数与未来超额收益的皮尔逊相关（逐日再取均值）。
    - RankIC：秩相关，抗异常值，衡量排序方向是否稳定。
    - IC_IR：IC 均值 / IC 标准差，衡量信号跨期稳定性。
    - long_short_spread：高分组与低分组的平均超额收益之差。
    指标只解释历史信号的排序能力，不构成投资建议。
    """
    daily_ic: list[float] = []
    daily_rank_ic: list[float] = []
    daily_spread: list[float] = []
    for _trade_date, rows in sorted(scored_by_date.items()):
        if len(rows) < 2:
            continue
        scores = [score for score, _excess in rows]
        excess = [value for _score, value in rows]
        ic = _pearson_correlation(scores, excess)
        if ic is not None:
            daily_ic.append(ic)
        rank_ic = _pearson_correlation(_average_ranks(scores), _average_ranks(excess))
        if rank_ic is not None:
            daily_rank_ic.append(rank_ic)
        spread = _long_short_spread(rows, quantile_fraction)
        if spread is not None:
            daily_spread.append(spread)

    return {
        "ic_date_count": len(daily_ic),
        "ic_mean": _round_optional(_mean(daily_ic)),
        "rank_ic_mean": _round_optional(_mean(daily_rank_ic)),
        "ic_ir": _round_optional(_information_ratio(daily_ic)),
        "rank_ic_positive_rate": _round_optional(
            sum(1 for value in daily_rank_ic if value > 0) / len(daily_rank_ic)
            if daily_rank_ic
            else None
        ),
        "long_short_spread": _round_optional(_mean(daily_spread)),
    }


def _long_short_spread(rows: list[tuple[float, float]], quantile_fraction: float) -> float | None:
    if len(rows) < 2:
        return None
    ordered = sorted(rows, key=lambda item: item[0], reverse=True)
    group_size = max(1, int(len(ordered) * quantile_fraction))
    # 高低分组各取截面的一端，group_size <= n//3 时两端不重叠，避免同一标的同时进多空组。
    top_excess = [excess for _score, excess in ordered[:group_size]]
    bottom_excess = [excess for _score, excess in ordered[-group_size:]]
    return _mean(top_excess) - _mean(bottom_excess)


def _pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    variance_x = sum((x - mean_x) ** 2 for x in xs)
    variance_y = sum((y - mean_y) ** 2 for y in ys)
    if variance_x <= 0 or variance_y <= 0:
        return None
    return covariance / sqrt(variance_x * variance_y)


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average_rank = (position + end) / 2.0 + 1.0
        for index in range(position, end + 1):
            ranks[order[index]] = average_rank
        position = end + 1
    return ranks


def _information_ratio(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    if variance <= 0:
        return None
    return mean_value / sqrt(variance)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _round_optional(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def build_walk_forward_folds(
    usable_dates: list[date],
    *,
    label_gap_days: int = 5,
    min_train_dates: int = 3,
    test_size: int = 1,
) -> list[dict[str, Any]]:
    """构建扩张窗口 walk-forward 折。

    训练窗从 min_train_dates 起随时间增长，测试窗在保留 label_gap_days 标签间隔后向前滚动，
    相邻折的测试日不重叠。规则基线不需要按折重训，这里的折用于把离线评估从单一测试日
    扩展到滚动样本外时间线。
    """
    folds: list[dict[str, Any]] = []
    total = len(usable_dates)
    train_end = min_train_dates  # exclusive index into usable_dates
    while True:
        test_start = train_end + label_gap_days
        if test_start >= total:
            break
        test_end = min(test_start + test_size, total)
        folds.append(
            {
                "train_start": usable_dates[0],
                "train_end": usable_dates[train_end - 1],
                "test_dates": usable_dates[test_start:test_end],
            }
        )
        train_end += test_size
    return folds


def build_walk_forward_metrics(
    features: list[FeatureRow],
    labels: list[LabelRow],
    *,
    label_gap_days: int = 5,
    min_train_dates: int = 3,
    test_size: int = 1,
    score_fn: Callable[[FeatureRow], float] | None = None,
) -> dict[str, float | int | str | None]:
    """在滚动样本外时间线上评估固定模型信号，比单一测试日更能反映信号稳定性。

    score_fn 默认使用规则基线打分；LightGBM 传入 booster 打分函数即可复用同一套滚动口径。
    """
    score_row = score_fn or _score_feature_row
    usable_labels = [
        label
        for label in labels
        if label.future_5d_return is not None
        and label.benchmark_5d_return is not None
        and label.outperform_benchmark_5d is not None
    ]
    usable_dates = sorted({label.trade_date for label in usable_labels})
    folds = build_walk_forward_folds(
        usable_dates,
        label_gap_days=label_gap_days,
        min_train_dates=min_train_dates,
        test_size=test_size,
    )
    if not folds:
        return {
            "walk_forward_status": "skipped_insufficient_history",
            "walk_forward_fold_count": 0,
            "walk_forward_test_date_count": 0,
        }

    label_by_key = {(label.symbol, label.trade_date): label for label in usable_labels}
    test_dates = {trade_date for fold in folds for trade_date in fold["test_dates"]}
    features_by_date: dict[date, list[FeatureRow]] = defaultdict(list)
    for row in features:
        if row.trade_date in test_dates:
            features_by_date[row.trade_date].append(row)

    scored_by_date: dict[date, list[tuple[float, float]]] = {}
    top1_hits = 0
    top1_total = 0
    top3_hits = 0
    top3_total = 0
    for trade_date in sorted(features_by_date):
        scored = [
            (row, score_row(row))
            for row in features_by_date[trade_date]
            if row.momentum_5d is not None
            and row.return_1d is not None
            and (row.symbol, trade_date) in label_by_key
        ]
        if not scored:
            continue
        scored.sort(key=lambda item: (-item[1], item[0].symbol))
        top1_total += 1
        top1_hits += int(
            bool(label_by_key[(scored[0][0].symbol, trade_date)].outperform_benchmark_5d)
        )
        for row, _score in scored[:3]:
            top3_total += 1
            top3_hits += int(bool(label_by_key[(row.symbol, trade_date)].outperform_benchmark_5d))
        scored_by_date[trade_date] = [
            (score, _label_excess_return(label_by_key[(row.symbol, trade_date)]))
            for row, score in scored
        ]

    signal = build_rank_signal_metrics(scored_by_date)
    return {
        "walk_forward_status": "ready",
        "walk_forward_fold_count": len(folds),
        "walk_forward_test_date_count": top1_total,
        "walk_forward_top1_outperform_rate": round(top1_hits / top1_total, 6)
        if top1_total
        else None,
        "walk_forward_top3_outperform_rate": round(top3_hits / top3_total, 6)
        if top3_total
        else None,
        "walk_forward_ic_mean": signal["ic_mean"],
        "walk_forward_rank_ic_mean": signal["rank_ic_mean"],
        "walk_forward_ic_ir": signal["ic_ir"],
        "walk_forward_rank_ic_positive_rate": signal["rank_ic_positive_rate"],
        "walk_forward_long_short_spread": signal["long_short_spread"],
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
    scored_by_date: dict[date, list[tuple[float, float]]] = {}
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
        scored_by_date[trade_date] = [
            (score, _label_excess_return(label_by_key[(row.symbol, trade_date)]))
            for row, score in scored
        ]

    metrics.update(
        {
            "test_prediction_dates": top1_total,
            "top1_outperform_rate": round(top1_hits / top1_total, 6) if top1_total else None,
            "top3_outperform_rate": round(top3_hits / top3_total, 6) if top3_total else None,
        }
    )
    metrics.update(build_rank_signal_metrics(scored_by_date))
    return metrics


def build_lightgbm_evaluation_metrics(
    booster: Any, rows: list[TrainingSampleRow]
) -> dict[str, float | int | str | None]:
    test_rows = [row for row in rows if row.split == "test"]
    positive_count = sum(1 for row in rows if row.outperform_benchmark_5d)
    metrics: dict[str, float | int | str | None] = {
        "positive_rate": round(positive_count / len(rows), 6) if rows else None,
        "evaluation_status": "ready" if test_rows else "skipped_insufficient_history",
        "test_prediction_dates": len({row.trade_date for row in test_rows}),
    }
    if not test_rows:
        metrics.update({"top1_outperform_rate": None, "top3_outperform_rate": None})
        return metrics

    scores = _predict_scores(booster, [_feature_vector_from_sample(row) for row in test_rows])
    rows_by_date: dict[date, list[tuple[TrainingSampleRow, float]]] = defaultdict(list)
    for row, score in zip(test_rows, scores, strict=True):
        rows_by_date[row.trade_date].append((row, float(score)))

    top1_hits = 0
    top1_total = 0
    top3_hits = 0
    top3_total = 0
    scored_by_date: dict[date, list[tuple[float, float]]] = {}
    for trade_date, scored_rows in sorted(rows_by_date.items()):
        scored_rows.sort(key=lambda item: (-item[1], item[0].symbol))
        top1_total += 1
        top1_hits += int(bool(scored_rows[0][0].outperform_benchmark_5d))
        for row, _score in scored_rows[:3]:
            top3_total += 1
            top3_hits += int(bool(row.outperform_benchmark_5d))
        scored_by_date[trade_date] = [
            (score, row.future_5d_return - row.benchmark_5d_return) for row, score in scored_rows
        ]

    metrics.update(
        {
            "top1_outperform_rate": round(top1_hits / top1_total, 6) if top1_total else None,
            "top3_outperform_rate": round(top3_hits / top3_total, 6) if top3_total else None,
        }
    )
    metrics.update(build_rank_signal_metrics(scored_by_date))
    return metrics


def _label_excess_return(label: LabelRow) -> float:
    future = label.future_5d_return or 0.0
    benchmark = label.benchmark_5d_return or 0.0
    return future - benchmark


def build_baseline_feature_importance() -> list[dict[str, float | int | str]]:
    total_weight = sum(abs(BASELINE_FEATURE_WEIGHTS[name]) for name in BASELINE_FEATURE_NAMES)
    rows = []
    for feature_name in BASELINE_FEATURE_NAMES:
        weight = BASELINE_FEATURE_WEIGHTS[feature_name]
        rows.append(
            {
                "feature_name": feature_name,
                "importance": round(abs(weight) / total_weight, 6),
                "raw_importance": weight,
                "importance_type": "rule_weight",
            }
        )
    return _rank_feature_importance(rows)


def build_lightgbm_feature_importance(booster: Any) -> list[dict[str, float | int | str]]:
    gain_values = _booster_feature_importance(booster, "gain")
    split_values = _booster_feature_importance(booster, "split")
    total_gain = sum(gain_values)
    rows = []
    for index, feature_name in enumerate(BASELINE_FEATURE_NAMES):
        gain = gain_values[index] if index < len(gain_values) else 0.0
        split = split_values[index] if index < len(split_values) else 0.0
        rows.append(
            {
                "feature_name": feature_name,
                "importance": round(gain / total_gain, 6) if total_gain > 0 else 0.0,
                "raw_importance": round(gain, 6),
                "split_count": int(split),
                "importance_type": "lightgbm_gain",
            }
        )
    # 特征重要性只解释已训练模型的相对贡献，不作为独立选股信号或投资建议。
    return _rank_feature_importance(rows)


def _booster_feature_importance(booster: Any, importance_type: str) -> list[float]:
    if not hasattr(booster, "feature_importance"):
        return [0.0 for _feature_name in BASELINE_FEATURE_NAMES]
    values = booster.feature_importance(importance_type=importance_type)
    return [float(value) for value in values]


def _rank_feature_importance(
    rows: list[dict[str, float | int | str]],
) -> list[dict[str, float | int | str]]:
    ranked = sorted(
        rows, key=lambda row: (-abs(float(row["importance"])), str(row["feature_name"]))
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


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
    features: list[FeatureRow],
    model_version: str = BASELINE_MODEL_VERSION,
    metadata: ModelMetadata | None = None,
    model_path: Path | None = None,
) -> list[PredictionRow]:
    latest_date = max(row.trade_date for row in features)
    latest_rows = [row for row in features if row.trade_date == latest_date]
    return _rank_feature_rows(latest_rows, model_version, metadata, model_path)


def generate_historical_predictions(
    features: list[FeatureRow],
    model_version: str = BASELINE_MODEL_VERSION,
    metadata: ModelMetadata | None = None,
    model_path: Path | None = None,
) -> list[PredictionRow]:
    by_date: dict[date, list[FeatureRow]] = defaultdict(list)
    for row in features:
        by_date[row.trade_date].append(row)

    predictions: list[PredictionRow] = []
    booster = _load_prediction_booster(metadata, model_path)
    for trade_date, rows in sorted(by_date.items()):
        predictions.extend(_rank_feature_rows(rows, model_version, metadata, booster=booster))

    return predictions


def _rank_feature_rows(
    rows: list[FeatureRow],
    model_version: str,
    metadata: ModelMetadata | None = None,
    model_path: Path | None = None,
    booster: Any | None = None,
) -> list[PredictionRow]:
    scorable_rows = [
        row for row in rows if row.momentum_5d is not None and row.return_1d is not None
    ]
    prediction_booster = booster or _load_prediction_booster(metadata, model_path)
    if prediction_booster is None:
        scored = [(row, _score_feature_row(row)) for row in scorable_rows]
    else:
        scores = _predict_scores(
            prediction_booster, [_feature_vector_from_feature(row) for row in scorable_rows]
        )
        scored = [(row, float(score)) for row, score in zip(scorable_rows, scores, strict=True)]
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


def _load_prediction_booster(
    metadata: ModelMetadata | None, model_path: Path | Any | None
) -> Any | None:
    if metadata is None or metadata.model_type != "lightgbm":
        return None
    if model_path is not None and hasattr(model_path, "predict"):
        return model_path
    resolved_path = model_path or (
        Path(metadata.model_artifact_path) if metadata.model_artifact_path else None
    )
    if resolved_path is None:
        raise ValueError("lightgbm metadata requires model_path for prediction")
    lightgbm = _load_lightgbm_module()
    return lightgbm.Booster(model_file=str(resolved_path))


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
        model_artifact_path=payload.get("model_artifact_path"),
        feature_importance=payload.get("feature_importance"),
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


def _feature_vector_from_sample(row: TrainingSampleRow) -> list[float]:
    return [
        _model_float(row.momentum_5d),
        _model_float(row.return_1d),
        _model_float(row.volatility_5d),
        _model_float(row.rsi_6),
        _model_float(row.macd_hist),
        _model_float(row.volume_change_1d),
    ]


def _feature_vector_from_feature(row: FeatureRow) -> list[float]:
    return [
        _model_float(row.momentum_5d),
        _model_float(row.return_1d),
        _model_float(row.volatility_5d),
        _model_float(row.rsi_6),
        _model_float(row.macd_hist),
        _model_float(row.volume_change_1d),
    ]


def _model_float(value: float | None) -> float:
    return float("nan") if value is None else float(value)


def _predict_scores(booster: Any, feature_vectors: list[list[float]]) -> list[float]:
    # LightGBM 4.x 的 predict 要求 2D ndarray；统一在此转换，避免各调用点传 Python 列表被判为 1 维。
    if not feature_vectors:
        return []
    numpy = importlib.import_module("numpy")
    matrix = numpy.asarray(feature_vectors, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    return [float(value) for value in booster.predict(matrix)]


def _format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"


def _parse_optional(value: str) -> float | None:
    return None if value == "" else float(value)


def _format_date(value: date | int | str | None) -> str | None:
    return value.isoformat() if isinstance(value, date) else None
