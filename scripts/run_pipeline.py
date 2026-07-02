#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from swell_quant.core.config import Settings
from swell_quant.core.pipeline import PipelineStep, StepStatus, run_steps
from swell_quant.data.sample_data import ensure_sample_prices, read_price_bars_csv
from swell_quant.research.backtest import (
    read_backtest_result,
    run_top_n_backtest,
    write_backtest_result,
)
from swell_quant.research.features import compute_features, read_features_csv, write_features_csv
from swell_quant.research.labels import compute_labels, read_labels_csv, write_labels_csv
from swell_quant.research.modeling import (
    BASELINE_MODEL_VERSION,
    generate_historical_predictions,
    generate_predictions,
    read_model_metadata,
    read_predictions_csv,
    train_baseline_model,
    write_model_metadata,
    write_predictions_csv,
)
from swell_quant.research.reporting import build_research_summary, write_research_summary
from swell_quant.storage.duckdb_backup import backup_duckdb


def prepare_directories(settings: Settings) -> str:
    settings.ensure_directories()
    return f"prepared data directories under {settings.data_dir}"


def run_data_update(settings: Settings) -> str:
    settings.ensure_directories()
    sample_path = settings.data_dir / "raw" / "sample_prices.csv"
    ensure_sample_prices(sample_path)
    backup_path = backup_duckdb(settings.duckdb_path, settings.data_dir / "processed" / "duckdb_backups")
    backup_message = f"backup={backup_path}" if backup_path else "backup=skipped_missing_duckdb"
    # 阶段 1 先用可复现样例行情打通链路，真实 AKShare 采集接入后沿用同一产物路径。
    return f"wrote sample prices to {sample_path} ({backup_message})"


def run_feature_pipeline(settings: Settings) -> str:
    price_path = settings.data_dir / "raw" / "sample_prices.csv"
    feature_path = settings.data_dir / "processed" / "sample_features.csv"
    bars = read_price_bars_csv(price_path)
    features = compute_features(bars)
    write_features_csv(feature_path, features)
    return f"wrote {len(features)} feature rows to {feature_path}"


def run_label_pipeline(settings: Settings) -> str:
    price_path = settings.data_dir / "raw" / "sample_prices.csv"
    label_path = settings.data_dir / "processed" / "sample_labels.csv"
    bars = read_price_bars_csv(price_path)
    labels = compute_labels(bars, horizon=5)
    write_labels_csv(label_path, labels)
    return f"wrote {len(labels)} label rows to {label_path}"


def run_training_pipeline(settings: Settings) -> str:
    feature_path = settings.data_dir / "processed" / "sample_features.csv"
    label_path = settings.data_dir / "processed" / "sample_labels.csv"
    model_path = settings.data_dir / "models" / f"{BASELINE_MODEL_VERSION}.json"
    latest_prediction_path = settings.data_dir / "processed" / "latest_predictions.csv"
    historical_prediction_path = settings.data_dir / "processed" / "historical_predictions.csv"

    features = read_features_csv(feature_path)
    labels = read_labels_csv(label_path)
    metadata = train_baseline_model(features, labels)
    latest_predictions = generate_predictions(features, metadata.model_version)
    historical_predictions = generate_historical_predictions(features, metadata.model_version)

    write_model_metadata(model_path, metadata)
    write_predictions_csv(latest_prediction_path, latest_predictions)
    write_predictions_csv(historical_prediction_path, historical_predictions)
    return (
        f"wrote model metadata to {model_path}, "
        f"{len(latest_predictions)} latest predictions and "
        f"{len(historical_predictions)} historical predictions"
    )


def run_backtest_pipeline(settings: Settings) -> str:
    price_path = settings.data_dir / "raw" / "sample_prices.csv"
    feature_path = settings.data_dir / "processed" / "sample_features.csv"
    report_path = settings.data_dir / "reports" / "sample_backtest.json"

    bars = read_price_bars_csv(price_path)
    features = read_features_csv(feature_path)
    historical_predictions = generate_historical_predictions(features, BASELINE_MODEL_VERSION)
    result = run_top_n_backtest(bars, historical_predictions, top_n=2)
    write_backtest_result(report_path, result)
    return (
        f"wrote backtest report to {report_path} "
        f"(cumulative_return={result.cumulative_return:.4f}, "
        f"benchmark_return={result.benchmark_return:.4f})"
    )


def run_report_pipeline(settings: Settings) -> str:
    model_path = settings.data_dir / "models" / f"{BASELINE_MODEL_VERSION}.json"
    latest_prediction_path = settings.data_dir / "processed" / "latest_predictions.csv"
    backtest_path = settings.data_dir / "reports" / "sample_backtest.json"
    summary_path = settings.data_dir / "reports" / "sample_research_summary.md"

    metadata = read_model_metadata(model_path)
    predictions = read_predictions_csv(latest_prediction_path)
    backtest = read_backtest_result(backtest_path)
    summary = build_research_summary(metadata, predictions, backtest)
    write_research_summary(summary_path, summary)
    return f"wrote research summary to {summary_path}"


def build_steps(settings: Settings) -> list[PipelineStep]:
    return [
        PipelineStep("prepare_directories", lambda: prepare_directories(settings)),
        PipelineStep("data_update", lambda: run_data_update(settings)),
        PipelineStep("features", lambda: run_feature_pipeline(settings)),
        PipelineStep("labels", lambda: run_label_pipeline(settings)),
        PipelineStep("train", lambda: run_training_pipeline(settings)),
        PipelineStep("backtest", lambda: run_backtest_pipeline(settings)),
        PipelineStep("report", lambda: run_report_pipeline(settings)),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Swell Quant offline research pipeline.")
    parser.add_argument("--fail-on-skipped", action="store_true", help="Return non-zero if any step is skipped.")
    args = parser.parse_args()

    settings = Settings.from_env()
    results = run_steps(build_steps(settings))

    for result in results:
        print(f"{result.status.value:7s} {result.name}: {result.message}")

    if any(result.status == StepStatus.FAILED for result in results):
        return 1
    if args.fail_on_skipped and any(result.status == StepStatus.SKIPPED for result in results):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
