#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from swell_quant.core.config import Settings
from swell_quant.core.pipeline import PipelineStep, StepStatus, run_steps, write_run_manifest
from swell_quant.data.akshare_data import (
    collect_akshare_price_bars,
    resolve_akshare_symbol_metadata,
)
from swell_quant.data.quality import read_quality_report, validate_price_bars, write_quality_report
from swell_quant.data.sample_data import (
    DATA_SOURCE_METADATA_FILENAME,
    SAMPLE_SYMBOLS,
    build_price_data_metadata,
    ensure_sample_prices,
    read_price_data_metadata,
    read_price_bars_csv,
    write_price_bars_csv,
    write_price_data_metadata,
)
from swell_quant.research.backtest import (
    read_backtest_result,
    run_top_n_backtest,
    write_backtest_result,
)
from swell_quant.research.features import compute_features, read_features_csv, write_features_csv
from swell_quant.research.funds import (
    FUND_PROFILES,
    build_fund_candidates,
    compute_fund_metrics,
    generate_sample_funds,
    write_fund_candidates_csv,
    write_fund_metrics_csv,
    write_fund_nav_csv,
    write_funds_csv,
)
from swell_quant.research.labels import compute_labels, read_labels_csv, write_labels_csv
from swell_quant.research.llm_reporting import (
    DeepSeekProvider,
    generate_ai_report_payload,
    write_ai_report_markdown,
    write_ai_report_payload,
)
from swell_quant.research.modeling import (
    LATEST_MODEL_METADATA_FILENAME,
    LIGHTGBM_MODEL_VERSION,
    build_training_samples,
    generate_historical_predictions,
    generate_predictions,
    read_model_metadata,
    read_predictions_csv,
    read_training_samples_csv,
    train_model,
    write_model_metadata,
    write_predictions_csv,
    write_training_samples_csv,
)
from swell_quant.research.reporting import (
    build_research_report_payload,
    render_research_summary,
    write_research_report_payload,
    write_research_summary,
)
from swell_quant.research.status import (
    build_research_status,
    default_artifact_paths,
    read_json,
    write_research_status,
)
from swell_quant.storage.duckdb_backup import backup_duckdb
from swell_quant.storage.duckdb_mirror import inspect_duckdb_mirror, mirror_pipeline_csvs_to_duckdb


def prepare_directories(settings: Settings) -> str:
    settings.ensure_directories()
    return f"prepared data directories under {settings.data_dir}"


def run_data_update(settings: Settings) -> str:
    settings.ensure_directories()
    sample_path = settings.data_dir / "raw" / "sample_prices.csv"
    metadata_path = settings.data_dir / "raw" / DATA_SOURCE_METADATA_FILENAME
    data_source = settings.data_source.strip().lower()
    if data_source == "sample":
        ensure_sample_prices(sample_path)
        write_price_data_metadata(
            metadata_path,
            build_price_data_metadata(
                data_source="sample",
                symbols=SAMPLE_SYMBOLS,
                start_date="2024-01-02",
                end_date="2024-01-21",
                benchmark="CSI800",
            ),
        )
        source_message = "source=sample"
    elif data_source == "akshare":
        symbol_metadata = resolve_akshare_symbol_metadata(
            universe_mode=settings.akshare_universe_mode,
            manual_symbols=settings.akshare_symbols,
        )
        resolved_symbols = tuple(symbol_metadata.keys())
        symbols = limit_akshare_symbols(resolved_symbols, settings.akshare_max_symbols)
        try:
            fetch_result = collect_akshare_price_bars(
                symbols=symbols,
                start_date=settings.akshare_start_date,
                end_date=settings.akshare_end_date,
                benchmark_symbol=settings.akshare_benchmark_symbol,
            )
        except Exception as error:
            cached_metadata = _usable_akshare_cache_metadata(sample_path, metadata_path, settings)
            if cached_metadata is None:
                raise
            # 真实行情源全量断连时允许复用上一次质量可用缓存，保证研究看板仍可生成预测；
            # metadata 显式标记 cached_fallback，避免把缓存结果误认为本次实时采集成功。
            cached_metadata["update_mode"] = "cached_fallback"
            cached_metadata["fallback_reason"] = str(error)
            write_price_data_metadata(metadata_path, cached_metadata)
            source_message = (
                "source=akshare, cache_fallback=true, "
                f"symbols={cached_metadata.get('selected_symbol_count')}, "
                f"succeeded={cached_metadata.get('succeeded_symbol_count')}, "
                f"failed={cached_metadata.get('failed_symbol_count')}, "
                f"range={cached_metadata.get('start_date')}-{cached_metadata.get('end_date')}, "
                f"benchmark={cached_metadata.get('benchmark')}"
            )
        else:
            write_price_bars_csv(sample_path, fetch_result.bars)
            write_price_data_metadata(
                metadata_path,
                build_price_data_metadata(
                    data_source="akshare",
                    symbols=symbols,
                    start_date=settings.akshare_start_date,
                    end_date=settings.akshare_end_date,
                    benchmark=settings.akshare_benchmark_symbol,
                    universe_mode=settings.akshare_universe_mode,
                    resolved_symbol_count=len(resolved_symbols),
                    max_symbols=settings.akshare_max_symbols,
                    symbol_names={
                        symbol: symbol_metadata.get(symbol, symbol) for symbol in symbols
                    },
                    succeeded_symbols=fetch_result.succeeded_symbols,
                    failed_symbols=tuple(
                        {"symbol": failure.symbol, "reason": failure.reason}
                        for failure in fetch_result.failed_symbols
                    ),
                    source_attempts=tuple(
                        {
                            "symbol": attempt.symbol,
                            "source": attempt.source,
                            "status": attempt.status,
                            "attempts": attempt.attempts,
                            "error": attempt.error or "",
                        }
                        for attempt in fetch_result.source_attempts
                    ),
                ),
            )
            source_message = (
                "source=akshare, "
                f"universe_mode={settings.akshare_universe_mode}, "
                f"symbols={len(symbols)}, "
                f"succeeded={len(fetch_result.succeeded_symbols)}, "
                f"failed={len(fetch_result.failed_symbols)}, "
                f"resolved_symbols={len(resolved_symbols)}, "
                f"range={settings.akshare_start_date}-{settings.akshare_end_date}, "
                f"benchmark={settings.akshare_benchmark_symbol}"
            )
    else:
        raise ValueError(f"unsupported DATA_SOURCE: {settings.data_source}")
    backup_path = backup_duckdb(
        settings.duckdb_path, settings.data_dir / "processed" / "duckdb_backups"
    )
    backup_message = f"backup={backup_path}" if backup_path else "backup=skipped_missing_duckdb"
    # 数据更新统一落到同一 CSV 契约，后续因子、标签、训练和回测不感知样例数据或 AKShare 来源差异。
    return f"wrote prices to {sample_path} ({source_message}; {backup_message})"


def _usable_akshare_cache_metadata(
    sample_path: Path,
    metadata_path: Path,
    settings: Settings,
) -> dict[str, Any] | None:
    if not sample_path.exists() or not metadata_path.exists():
        return None
    metadata = read_price_data_metadata(metadata_path)
    if metadata.get("data_source") != "akshare":
        return None
    if metadata.get("start_date") != settings.akshare_start_date:
        return None
    if metadata.get("end_date") != settings.akshare_end_date:
        return None
    if float(metadata.get("success_rate") or 0.0) < 0.8:
        return None
    if not read_price_bars_csv(sample_path):
        return None
    return dict(metadata)


def run_fund_research_pipeline(settings: Settings) -> str:
    funds, navs = generate_sample_funds()
    funds_path = settings.data_dir / "raw" / "sample_funds.csv"
    nav_path = settings.data_dir / "raw" / "sample_fund_nav.csv"
    metrics_path = settings.data_dir / "processed" / "sample_fund_metrics.csv"
    write_funds_csv(funds_path, funds)
    write_fund_nav_csv(nav_path, navs)
    metrics = compute_fund_metrics(funds, navs)
    write_fund_metrics_csv(metrics_path, metrics)
    for profile in FUND_PROFILES:
        write_fund_candidates_csv(
            settings.data_dir / "processed" / f"sample_fund_candidates_{profile}.csv",
            build_fund_candidates(metrics, profile=profile),
        )
    return f"wrote {len(metrics)} fund metrics and {len(FUND_PROFILES)} candidate views"


def limit_akshare_symbols(
    symbols: tuple[str, ...],
    max_symbols: int | None,
) -> tuple[str, ...]:
    if max_symbols is None:
        return symbols
    # 真实 AKShare 首次试跑可能触发数百只股票采集；这里仅在用户显式配置上限时截断，避免默认口径被悄悄缩小。
    return symbols[:max_symbols]


def run_feature_pipeline(settings: Settings) -> str:
    price_path = settings.data_dir / "raw" / "sample_prices.csv"
    feature_path = settings.data_dir / "processed" / "sample_features.csv"
    bars = read_price_bars_csv(price_path)
    features = compute_features(bars)
    write_features_csv(feature_path, features)
    return f"wrote {len(features)} feature rows to {feature_path}"


def run_data_quality_pipeline(settings: Settings) -> str:
    price_path = settings.data_dir / "raw" / "sample_prices.csv"
    quality_path = settings.data_dir / "processed" / "data_quality.json"
    bars = read_price_bars_csv(price_path)
    report = validate_price_bars(bars)
    write_quality_report(quality_path, report)
    if not report.passed:
        raise RuntimeError(f"data quality failed with {report.issue_count} issues")
    return f"wrote data quality report to {quality_path} (issues={report.issue_count})"


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
    training_sample_path = settings.data_dir / "processed" / "training_samples.csv"
    latest_prediction_path = settings.data_dir / "processed" / "latest_predictions.csv"
    historical_prediction_path = settings.data_dir / "processed" / "historical_predictions.csv"

    features = read_features_csv(feature_path)
    labels = read_labels_csv(label_path)
    training_samples = build_training_samples(features, labels)
    requested_model_type = settings.model_type.strip().lower()
    model_output_path = (
        settings.data_dir / "models" / f"{LIGHTGBM_MODEL_VERSION}.txt"
        if requested_model_type in {"", "lightgbm"}
        else None
    )
    metadata = train_model(
        features,
        labels,
        requested_model_type=settings.model_type,
        model_output_path=model_output_path,
    )
    model_path = settings.data_dir / "models" / f"{metadata.model_version}.json"
    latest_model_path = settings.data_dir / "models" / LATEST_MODEL_METADATA_FILENAME
    resolved_model_output_path = (
        Path(metadata.model_artifact_path) if metadata.model_artifact_path else None
    )
    latest_predictions = generate_predictions(
        features, metadata.model_version, metadata, resolved_model_output_path
    )
    historical_predictions = generate_historical_predictions(
        features, metadata.model_version, metadata, resolved_model_output_path
    )

    write_model_metadata(model_path, metadata)
    write_model_metadata(latest_model_path, metadata)
    write_training_samples_csv(training_sample_path, training_samples)
    write_predictions_csv(latest_prediction_path, latest_predictions)
    write_predictions_csv(historical_prediction_path, historical_predictions)
    return (
        f"wrote model metadata to {model_path}, "
        f"{len(training_samples)} training samples, "
        f"{len(latest_predictions)} latest predictions and "
        f"{len(historical_predictions)} historical predictions"
    )


def run_backtest_pipeline(settings: Settings) -> str:
    price_path = settings.data_dir / "raw" / "sample_prices.csv"
    historical_prediction_path = settings.data_dir / "processed" / "historical_predictions.csv"
    report_path = settings.data_dir / "reports" / "sample_backtest.json"

    bars = read_price_bars_csv(price_path)
    historical_predictions = read_predictions_csv(historical_prediction_path)
    result = run_top_n_backtest(bars, historical_predictions, top_n=2)
    write_backtest_result(report_path, result)
    return (
        f"wrote backtest report to {report_path} "
        f"(cumulative_return={result.cumulative_return:.4f}, "
        f"benchmark_return={result.benchmark_return:.4f})"
    )


def run_duckdb_mirror_pipeline(settings: Settings) -> str:
    result = mirror_pipeline_csvs_to_duckdb(settings.data_dir, settings.duckdb_path)
    backup_path = backup_duckdb(
        settings.duckdb_path, settings.data_dir / "processed" / "duckdb_backups"
    )
    backup_message = f"backup={backup_path}" if backup_path else "backup=skipped_missing_duckdb"
    table_summary = ", ".join(f"{table.table_name}={table.row_count}" for table in result.tables)
    return f"mirrored {result.total_rows} rows to {result.duckdb_path} ({table_summary}; {backup_message})"


def run_report_pipeline(settings: Settings) -> str:
    model_path = settings.data_dir / "models" / LATEST_MODEL_METADATA_FILENAME
    latest_prediction_path = settings.data_dir / "processed" / "latest_predictions.csv"
    historical_prediction_path = settings.data_dir / "processed" / "historical_predictions.csv"
    label_path = settings.data_dir / "processed" / "sample_labels.csv"
    quality_path = settings.data_dir / "processed" / "data_quality.json"
    data_metadata_path = settings.data_dir / "raw" / DATA_SOURCE_METADATA_FILENAME
    backtest_path = settings.data_dir / "reports" / "sample_backtest.json"
    summary_path = settings.data_dir / "reports" / "sample_research_summary.md"
    payload_path = settings.data_dir / "reports" / "sample_research_summary.json"
    ai_summary_path = settings.data_dir / "reports" / "sample_ai_research_summary.md"
    ai_payload_path = settings.data_dir / "reports" / "sample_ai_research_summary.json"

    metadata = read_model_metadata(model_path)
    predictions = read_predictions_csv(latest_prediction_path)
    historical_predictions = read_predictions_csv(historical_prediction_path)
    labels = read_labels_csv(label_path)
    quality_report = read_quality_report(quality_path)
    backtest = read_backtest_result(backtest_path)
    data_metadata = read_price_data_metadata(data_metadata_path)
    # report 步骤只有在前置数据、训练、预测、回测步骤成功后才会运行；这里传入本轮 readiness，
    # 避免报告在最终 research_status.json 写入前误判为“门禁缺失”。
    readiness = {"passed": True, "failed_checks": []}
    payload = build_research_report_payload(
        metadata,
        predictions,
        backtest,
        quality_report,
        data_metadata,
        historical_predictions,
        labels,
        readiness,
    )
    summary = render_research_summary(payload)
    write_research_report_payload(payload_path, payload)
    write_research_summary(summary_path, summary)
    ai_payload = generate_ai_report_payload(
        payload,
        provider=_build_llm_provider(settings),
        requested_provider=settings.llm_provider,
    )
    write_ai_report_payload(ai_payload_path, ai_payload)
    write_ai_report_markdown(ai_summary_path, ai_payload)
    return (
        f"wrote research summary to {summary_path}, payload to {payload_path}, "
        f"ai_report_status={ai_payload['status']}"
    )


def _build_llm_provider(settings: Settings) -> DeepSeekProvider | None:
    provider_name = settings.llm_provider.strip().lower()
    if provider_name != "deepseek" or not settings.deepseek_api_key:
        return None
    return DeepSeekProvider(
        api_key=settings.deepseek_api_key,
        model_name=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
    )


def write_status_snapshot(settings: Settings, manifest_path: Path) -> Path:
    quality = read_quality_report(settings.data_dir / "processed" / "data_quality.json")
    metadata = read_model_metadata(settings.data_dir / "models" / LATEST_MODEL_METADATA_FILENAME)
    predictions = read_predictions_csv(settings.data_dir / "processed" / "latest_predictions.csv")
    training_samples = read_training_samples_csv(
        settings.data_dir / "processed" / "training_samples.csv"
    )
    backtest = read_backtest_result(settings.data_dir / "reports" / "sample_backtest.json")
    manifest = read_json(manifest_path)
    storage_status = inspect_duckdb_mirror(settings.duckdb_path, settings.data_dir)
    data_source_metadata = read_price_data_metadata(
        settings.data_dir / "raw" / DATA_SOURCE_METADATA_FILENAME
    )
    status = build_research_status(
        quality,
        metadata,
        predictions,
        backtest,
        manifest,
        storage_status,
        default_artifact_paths(settings.data_dir),
        training_samples,
        data_source_metadata,
    )
    return write_research_status(settings.data_dir / "reports" / "research_status.json", status)


def build_steps(settings: Settings) -> list[PipelineStep]:
    return [
        PipelineStep("prepare_directories", lambda: prepare_directories(settings)),
        PipelineStep("data_update", lambda: run_data_update(settings)),
        PipelineStep("fund_research", lambda: run_fund_research_pipeline(settings)),
        PipelineStep("data_quality", lambda: run_data_quality_pipeline(settings)),
        PipelineStep("features", lambda: run_feature_pipeline(settings)),
        PipelineStep("labels", lambda: run_label_pipeline(settings)),
        PipelineStep("train", lambda: run_training_pipeline(settings)),
        PipelineStep("backtest", lambda: run_backtest_pipeline(settings)),
        PipelineStep("duckdb_mirror", lambda: run_duckdb_mirror_pipeline(settings)),
        PipelineStep("report", lambda: run_report_pipeline(settings)),
    ]


def run_pipeline(settings: Settings) -> tuple[list, Path, Path | None]:
    results = run_steps(build_steps(settings))
    manifest_path = settings.data_dir / "reports" / "pipeline_run.json"
    write_run_manifest(manifest_path, results)
    status_path: Path | None = None
    if not any(result.status == StepStatus.FAILED for result in results):
        status_path = write_status_snapshot(settings, manifest_path)
    return results, manifest_path, status_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Swell Quant offline research pipeline.")
    parser.add_argument(
        "--fail-on-skipped", action="store_true", help="Return non-zero if any step is skipped."
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    results, manifest_path, status_path = run_pipeline(settings)

    for result in results:
        print(f"{result.status.value:7s} {result.name}: {result.message}")
    print(f"manifest {manifest_path}")
    if status_path is not None:
        print(f"status   {status_path}")

    if any(result.status == StepStatus.FAILED for result in results):
        return 1
    if args.fail_on_skipped and any(result.status == StepStatus.SKIPPED for result in results):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
