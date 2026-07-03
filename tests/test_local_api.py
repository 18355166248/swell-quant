import threading
from http import HTTPStatus
from pathlib import Path

from swell_quant.api.local_server import (
    load_acceptance_artifact,
    load_akshare_universe_artifact,
    load_akshare_trial_artifact,
    load_artifacts_artifact,
    load_backtest_artifact,
    load_backtest_route,
    load_backtests_artifact,
    load_data_quality_artifact,
    load_data_status_artifact,
    load_duckdb_storage_artifact,
    load_features_artifact,
    load_json_artifact,
    load_labels_artifact,
    load_latest_model_artifact,
    load_latest_predictions_artifact,
    load_model_artifact,
    load_model_route,
    load_models_artifact,
    load_prediction_route,
    load_predictions_artifact,
    load_progress_artifact,
    load_report_artifact,
    load_report_route,
    load_reports_artifact,
    load_settings_artifact,
    load_stock_features_artifact,
    load_stock_predictions_artifact,
    load_stock_prices_artifact,
    load_stock_route,
    load_stock_summary_artifact,
    load_stocks_artifact,
    load_task_detail_artifact,
    load_task_route,
    load_tasks_artifact,
    load_text_artifact,
    load_training_samples_artifact,
    missing_artifact_payload,
    normalize_equity_curve,
    pipeline_status_to_http_status,
    run_pipeline_for_api,
)
from swell_quant.core.config import Settings
from swell_quant.data.quality import validate_price_bars, write_quality_report
from swell_quant.data.sample_data import (
    DATA_SOURCE_METADATA_FILENAME,
    build_price_data_metadata,
    generate_sample_bars,
    write_price_bars_csv,
    write_price_data_metadata,
)
from swell_quant.research.backtest import run_top_n_backtest, write_backtest_result
from swell_quant.research.features import compute_features, write_features_csv
from swell_quant.research.labels import compute_labels, write_labels_csv
from swell_quant.research.modeling import (
    build_training_samples,
    generate_historical_predictions,
    generate_predictions,
    write_predictions_csv,
    write_training_samples_csv,
)
from swell_quant.storage.duckdb_mirror import mirror_pipeline_csvs_to_duckdb


def write_training_samples_artifact(data_dir: Path, features, labels) -> None:
    write_training_samples_csv(
        data_dir / "processed" / "training_samples.csv",
        build_training_samples(features, labels),
    )


def test_local_api_artifact_loaders_read_status_pipeline_and_report(tmp_path: Path) -> None:
    status_path = tmp_path / "research_status.json"
    pipeline_path = tmp_path / "pipeline_run.json"
    report_path = tmp_path / "sample_research_summary.md"

    status_path.write_text(
        '{"pipeline": {"status": "success"}, "disclaimer": "仅用于研究，不构成投资建议"}',
        encoding="utf-8",
    )
    pipeline_path.write_text('{"status": "success", "step_count": 8}', encoding="utf-8")
    report_path.write_text("# Summary\n\n仅用于研究，不构成投资建议\n", encoding="utf-8")

    assert load_json_artifact(status_path)["pipeline"]["status"] == "success"
    assert load_json_artifact(pipeline_path)["step_count"] == 8
    assert "不构成投资建议" in load_text_artifact(report_path)


def test_local_api_akshare_universe_artifact_reports_manual_symbols(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "duckdb" / "swell_quant.duckdb",
        akshare_universe_mode="manual",
        akshare_symbols=("000001.SZ", "600000.SH"),
    )

    status, payload = load_akshare_universe_artifact(settings)

    assert status == HTTPStatus.OK
    assert payload["status"] == "passed"
    assert payload["symbol_count"] == 2
    assert payload["symbols_sample"] == ["000001.SZ", "600000.SH"]
    assert payload["disclaimer"] == "仅用于研究，不构成投资建议"


def test_local_api_akshare_universe_artifact_handles_unavailable_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import swell_quant.api.local_server as local_server
    from swell_quant.data.akshare_data import AkshareDependencyError

    def fail_universe_payload(_settings):
        raise AkshareDependencyError("missing akshare")

    monkeypatch.setattr(local_server, "build_akshare_universe_payload", fail_universe_payload)
    settings = Settings(
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "duckdb" / "swell_quant.duckdb",
        akshare_universe_mode="csi800",
        akshare_symbols=(),
    )

    status, payload = load_akshare_universe_artifact(settings)

    assert status == HTTPStatus.SERVICE_UNAVAILABLE
    assert payload["status"] == "failed"
    assert payload["error"] == "akshare_universe_unavailable"
    assert payload["disclaimer"] == "仅用于研究，不构成投资建议"


def test_local_api_akshare_trial_artifact_reads_latest_trial(tmp_path: Path) -> None:
    trial_path = tmp_path / "akshare_trial_run.json"
    trial_path.write_text(
        """
        {
          "status": "dry_run",
          "passed": true,
          "started_at": "2026-07-03T00:00:00+00:00",
          "ended_at": "2026-07-03T00:00:01+00:00",
          "duration_seconds": 1.0,
          "env": {"DATA_SOURCE": "akshare", "AKSHARE_MAX_SYMBOLS": "20"},
          "steps": [{"name": "config", "status": "planned", "command": ["python"]}]
        }
        """,
        encoding="utf-8",
    )

    payload = load_akshare_trial_artifact(trial_path)

    assert payload["status"] == "dry_run"
    assert payload["passed"] is True
    assert payload["artifact_path"] == str(trial_path)
    assert payload["steps"][0]["name"] == "config"
    assert payload["disclaimer"] == "仅用于研究，不构成投资建议"


def test_local_api_acceptance_artifact_extracts_gate_summary(tmp_path: Path) -> None:
    status_path = tmp_path / "research_status.json"
    status_path.write_text(
        """
        {
          "disclaimer": "仅用于研究，不构成投资建议",
          "acceptance": {
            "status": "passed",
            "passed": true,
            "check_count": 1,
            "failed_count": 0,
            "checks": [
              {"key": "pipeline_success", "name": "Pipeline 执行成功", "status": "passed", "message": "status=success"}
            ]
          }
        }
        """,
        encoding="utf-8",
    )
    legacy_status_path = tmp_path / "legacy_status.json"
    legacy_status_path.write_text('{"pipeline": {"status": "success"}}', encoding="utf-8")

    payload = load_acceptance_artifact(status_path)
    legacy_payload = load_acceptance_artifact(legacy_status_path)

    assert payload["status"] == "passed"
    assert payload["checks"][0]["key"] == "pipeline_success"
    assert payload["disclaimer"] == "仅用于研究，不构成投资建议"
    assert legacy_payload["status"] == "missing"
    assert legacy_payload["passed"] is False
    assert legacy_payload["checks"][0]["key"] == "acceptance_missing"


def test_missing_artifact_payload_points_to_pipeline(tmp_path: Path) -> None:
    payload = missing_artifact_payload(tmp_path / "missing.json")

    assert payload["error"] == "artifact_missing"
    assert payload["hint"] == "run `python3 scripts/run_pipeline.py` first"


def test_local_api_settings_artifact_hides_secret_values(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "duckdb" / "swell_quant.duckdb",
        deepseek_api_key="deepseek-secret",
        openai_api_key=None,
        model_type="lightgbm",
        llm_provider="deepseek",
        data_source="akshare",
        akshare_universe_mode="manual",
        akshare_symbols=("000001.SZ", "600000.SH"),
        akshare_max_symbols=1,
    )
    settings.ensure_directories()
    (settings.data_dir / "reports" / "research_status.json").write_text("{}", encoding="utf-8")

    payload = load_settings_artifact(
        settings,
    )

    serialized = str(payload)
    assert payload["runtime"]["data_source"] == "akshare"
    assert payload["runtime"]["model_type"] == "lightgbm"
    assert payload["runtime"]["llm_provider"] == "deepseek"
    assert payload["akshare"]["universe_mode"] == "manual"
    assert payload["akshare"]["symbols"] == ["000001.SZ", "600000.SH"]
    assert payload["akshare"]["max_symbols"] == 1
    assert payload["llm"]["deepseek_model"] == "deepseek-chat"
    assert payload["preflight"]["status"] == "warning"
    assert payload["preflight"]["failed_count"] == 0
    assert payload["preflight"]["warning_count"] == 2
    assert any(check["key"] == "akshare_symbols" for check in payload["preflight"]["checks"])
    assert any(check["key"] == "akshare_symbol_count" for check in payload["preflight"]["checks"])
    assert any(check["key"] == "akshare_max_symbols" for check in payload["preflight"]["checks"])
    assert payload["api_keys"]["deepseek_configured"] is True
    assert payload["api_keys"]["openai_configured"] is False
    assert "deepseek-secret" not in serialized
    assert any(item["name"] == "status" and item["exists"] is True for item in payload["artifacts"])
    assert any(
        item["name"] == "status" and item["updated_at"] is not None for item in payload["artifacts"]
    )


def test_local_api_settings_preflight_warns_when_deepseek_key_missing(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "duckdb" / "swell_quant.duckdb",
        llm_provider="deepseek",
    )
    settings.ensure_directories()

    payload = load_settings_artifact(settings)

    assert payload["preflight"]["status"] == "warning"
    assert any(check["key"] == "deepseek_api_key" for check in payload["preflight"]["checks"])
    assert "DEEPSEEK_API_KEY" in str(payload["preflight"]["checks"])


def test_local_api_artifacts_artifact_reports_inventory_metadata(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    duckdb_path = data_dir / "duckdb" / "swell_quant.duckdb"
    data_dir.joinpath("reports").mkdir(parents=True)
    data_dir.joinpath("raw").mkdir(parents=True)
    data_dir.joinpath("raw", "sample_prices.csv").write_text("symbol,date\n", encoding="utf-8")

    payload = load_artifacts_artifact(data_dir, duckdb_path)

    raw_prices = next(item for item in payload["artifacts"] if item["name"] == "raw_prices")
    akshare_trial = next(item for item in payload["artifacts"] if item["name"] == "akshare_trial")
    assert payload["status"] == "missing"
    assert payload["disclaimer"] == "仅用于研究，不构成投资建议"
    assert raw_prices["exists"] is True
    assert raw_prices["size_bytes"] > 0
    assert raw_prices["updated_at"] is not None
    assert akshare_trial["exists"] is False
    assert akshare_trial["path"].endswith("akshare_trial_run.json")
    assert "duckdb" in payload["missing"]
    assert "akshare_trial" in payload["missing"]


def test_local_api_progress_artifact_reports_stage_status(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "duckdb" / "swell_quant.duckdb",
    )
    settings.ensure_directories()
    settings.data_dir.joinpath("raw", "sample_prices.csv").write_text(
        "symbol,date\n", encoding="utf-8"
    )

    payload = load_progress_artifact(settings)
    stage_by_id = {stage["id"]: stage for stage in payload["stages"]}

    assert payload["stage_count"] == 8
    assert payload["status"] == "in_progress"
    assert stage_by_id["stage_0"]["status"] == "complete"
    assert stage_by_id["stage_1"]["status"] == "partial"
    assert stage_by_id["stage_5"]["status"] == "complete"
    assert stage_by_id["stage_1"]["completed_count"] == 1
    assert payload["current_stage"]["id"] == "stage_1"
    assert payload["next_actions"]
    assert "阶段 1" in payload["next_actions"][0]
    assert payload["disclaimer"] == "仅用于研究，不构成投资建议"


def test_local_api_progress_artifact_recommends_akshare_trial_when_complete(
    tmp_path: Path,
) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "duckdb" / "swell_quant.duckdb",
    )
    settings.ensure_directories()
    artifact_paths = [
        settings.data_dir / "raw" / "sample_prices.csv",
        settings.data_dir / "processed" / "data_quality.json",
        settings.data_dir / "processed" / "sample_features.csv",
        settings.data_dir / "processed" / "sample_labels.csv",
        settings.data_dir / "processed" / "training_samples.csv",
        settings.data_dir / "models" / "latest_model.json",
        settings.data_dir / "processed" / "latest_predictions.csv",
        settings.data_dir / "processed" / "historical_predictions.csv",
        settings.duckdb_path,
        settings.data_dir / "reports" / "sample_backtest.json",
        settings.data_dir / "reports" / "sample_research_summary.md",
        settings.data_dir / "reports" / "sample_research_summary.json",
        settings.data_dir / "reports" / "sample_ai_research_summary.md",
        settings.data_dir / "reports" / "sample_ai_research_summary.json",
        settings.data_dir / "reports" / "pipeline_run.json",
        settings.data_dir / "reports" / "research_status.json",
    ]
    for path in artifact_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok", encoding="utf-8")

    payload = load_progress_artifact(settings)

    assert payload["status"] == "complete"
    assert payload["next_actions"]
    assert "make akshare-trial" in payload["next_actions"][0]
    assert "make data-source" in payload["next_actions"][1]
    assert "不构成投资建议" in payload["disclaimer"]


def test_local_api_task_artifacts_wrap_pipeline_manifest(tmp_path: Path) -> None:
    pipeline_path = tmp_path / "pipeline_run.json"
    pipeline_path.write_text(
        """
        {
          "status": "success",
          "step_count": 2,
          "started_at": "2026-07-02T00:00:00+00:00",
          "ended_at": "2026-07-02T00:00:01+00:00",
          "duration_seconds": 1.0,
          "steps": [
            {"name": "data_update", "status": "success", "message": "ok", "duration_seconds": 0.4},
            {"name": "report", "status": "success", "message": "ok", "duration_seconds": 0.6}
          ]
        }
        """,
        encoding="utf-8",
    )

    tasks = load_tasks_artifact(pipeline_path)
    detail = load_task_detail_artifact(pipeline_path)

    assert tasks["count"] == 1
    assert tasks["tasks"][0]["id"] == "pipeline-latest"
    assert tasks["tasks"][0]["step_count"] == 2
    assert "steps" not in tasks["tasks"][0]
    assert detail["id"] == "pipeline-latest"
    assert detail["steps"][1]["name"] == "report"


def test_local_api_task_route_dispatches(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "pipeline_run.json").write_text(
        '{"status": "failed", "step_count": 1, "steps": [{"name": "train", "status": "failed"}]}',
        encoding="utf-8",
    )

    list_status, list_payload = load_task_route("/api/tasks", tmp_path)
    detail_status, detail_payload = load_task_route("/api/tasks/pipeline-latest", tmp_path)
    missing_status, missing_payload = load_task_route("/api/tasks/nope", tmp_path)
    ignored = load_task_route("/api/status", tmp_path)

    assert list_status.value == 200
    assert list_payload["tasks"][0]["failed_step"] == "train"
    assert detail_status.value == 200
    assert detail_payload["failed_step"] == "train"
    assert missing_status.value == 404
    assert missing_payload["error"] == "task_not_found"
    assert ignored is None


def test_local_api_structured_artifact_loaders(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)
    quality_path = write_quality_report(
        tmp_path / "processed" / "data_quality.json", validate_price_bars(bars)
    )
    write_price_data_metadata(
        tmp_path / "raw" / DATA_SOURCE_METADATA_FILENAME,
        build_price_data_metadata(
            data_source="akshare",
            symbols=("000001.SZ", "600000.SH"),
            start_date="20240102",
            end_date="20240229",
            benchmark="sh000906",
        ),
    )
    predictions_path = write_predictions_csv(
        tmp_path / "predictions.csv", generate_predictions(features)
    )
    backtest_path = write_backtest_result(
        tmp_path / "backtest.json",
        run_top_n_backtest(bars, generate_historical_predictions(features)),
    )

    quality = load_data_quality_artifact(quality_path)
    data_status = load_data_status_artifact(quality_path)
    features_path = write_features_csv(tmp_path / "features.csv", features)
    features_payload = load_features_artifact(features_path)
    labels_path = write_labels_csv(tmp_path / "labels.csv", labels)
    labels_payload = load_labels_artifact(labels_path)
    training_samples_path = write_training_samples_csv(
        tmp_path / "training_samples.csv", build_training_samples(features, labels)
    )
    training_samples_payload = load_training_samples_artifact(training_samples_path)
    predictions = load_latest_predictions_artifact(predictions_path)
    backtest = load_backtest_artifact(backtest_path)

    assert quality["passed"] is True
    assert quality["row_count"] == 60
    assert data_status["market"] == "A_SHARE_DAILY"
    assert data_status["data_source_status"] == "passed"
    assert data_status["data_source_passed"] is True
    assert data_status["data_source_warnings"] == []
    assert data_status["data_source_failures"] == []
    assert data_status["data_source"] == "akshare"
    assert data_status["universe_mode"] == "manual"
    assert data_status["symbols"] == ["000001.SZ", "600000.SH"]
    assert data_status["selected_symbol_count"] == 2
    assert data_status["resolved_symbol_count"] == 2
    assert data_status["max_symbols"] is None
    assert data_status["succeeded_symbol_count"] == 2
    assert data_status["failed_symbol_count"] == 0
    assert data_status["failed_symbols"] == []
    assert data_status["target_universe"] == "沪深 300 + 中证 500"
    assert data_status["target_universe_size"] == 800
    assert data_status["benchmark"] == "sh000906"
    assert data_status["configured_start_date"] == "20240102"
    assert data_status["configured_end_date"] == "20240229"
    assert data_status["source_updated_at"]
    assert data_status["benchmark_same_source"] is False
    assert "自定义股票池" in data_status["benchmark_note"]
    assert data_status["update_mode"] == "manual_trigger"
    assert data_status["quality_passed"] is True
    assert features_payload["row_count"] == 60
    assert features_payload["symbol_count"] == 3
    assert features_payload["feature_names"] == [
        "return_1d",
        "momentum_5d",
        "ma_5",
        "volatility_5d",
        "rsi_6",
        "macd_dif",
        "macd_signal",
        "macd_hist",
        "volume_change_1d",
    ]
    assert features_payload["non_null_counts"]["momentum_5d"] == 45
    assert features_payload["non_null_counts"]["volatility_5d"] == 45
    assert features_payload["non_null_counts"]["rsi_6"] == 42
    assert features_payload["non_null_counts"]["macd_hist"] == 60
    assert features_payload["latest_samples"][0]["date"] == "2024-01-21"
    assert "macd_hist" in features_payload["latest_samples"][0]
    assert labels_payload["row_count"] == 60
    assert labels_payload["labeled_row_count"] == 45
    assert labels_payload["unlabeled_row_count"] == 15
    assert labels_payload["horizon_days"] == 5
    assert labels_payload["positive_count"] + labels_payload["negative_count"] == 45
    assert labels_payload["latest_samples"][0]["date"] == "2024-01-21"
    assert labels_payload["label_window"] == "T+1 open to T+5 close"
    assert labels_payload["entry_price"] == "next_day_open"
    assert labels_payload["exit_price"] == "horizon_day_close"
    assert training_samples_payload["row_count"] == 45
    assert training_samples_payload["split_counts"] == {
        "gap": 30,
        "test": 3,
        "train": 9,
        "validation": 3,
    }
    assert (
        training_samples_payload["positive_count"] + training_samples_payload["negative_count"]
        == 45
    )
    assert training_samples_payload["missing_feature_counts"]["return_1d"] == 3
    assert training_samples_payload["latest_samples"][0]["split"] == "test"
    assert predictions["count"] == 3
    assert predictions["predictions"][0]["rank"] == 1
    assert predictions["disclaimer"] == "仅用于研究，不构成投资建议"
    assert backtest["backtest_id"] == "sample-topn-baseline"
    assert backtest["trade_count"] == 14
    assert backtest["rejected_trade_count"] > 0
    assert backtest["rejected_trades"][-1]["reason"] == "missing_next_trade_date"
    assert backtest["slippage_rate"] == 0.0005
    assert backtest["annualized_return"] > backtest["cumulative_return"]
    assert backtest["max_drawdown"] <= 0
    assert backtest["win_rate"] >= 0
    assert backtest["turnover_rate"] >= 0
    assert backtest["equity_curve"][0]["date"] == "2024-01-08"
    assert "portfolio_value" in backtest["equity_curve"][0]
    assert "relative_return" in backtest["equity_curve"][0]
    assert "portfolio_drawdown" in backtest["equity_curve"][0]
    assert "benchmark_drawdown" in backtest["equity_curve"][0]


def test_normalize_equity_curve_adds_historical_drawdown() -> None:
    rows = [
        {
            "signal_date": "2024-01-01",
            "trade_date": "2024-01-02",
            "portfolio_return": 0.1,
            "benchmark_return": 0.05,
            "equity": 1.1,
            "benchmark_equity": 1.05,
        },
        {
            "signal_date": "2024-01-02",
            "trade_date": "2024-01-03",
            "portfolio_return": -0.1,
            "benchmark_return": -0.02,
            "equity": 0.99,
            "benchmark_equity": 1.029,
        },
    ]

    normalized = normalize_equity_curve(rows)

    assert normalized[0]["portfolio_drawdown"] == 0.0
    assert normalized[0]["benchmark_drawdown"] == 0.0
    assert round(float(normalized[0]["relative_return"]), 6) == 0.047619
    assert round(float(normalized[1]["portfolio_drawdown"]), 6) == -0.1
    assert round(float(normalized[1]["benchmark_drawdown"]), 6) == -0.02
    assert round(float(normalized[1]["relative_return"]), 6) == -0.037901


def test_local_api_duckdb_storage_artifact_reports_table_counts(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    bars = generate_sample_bars(days=8)
    features = compute_features(bars)
    labels = compute_labels(bars)
    write_price_bars_csv(data_dir / "raw" / "sample_prices.csv", bars)
    write_features_csv(data_dir / "processed" / "sample_features.csv", features)
    write_labels_csv(data_dir / "processed" / "sample_labels.csv", labels)
    write_training_samples_artifact(data_dir, features, labels)
    write_predictions_csv(
        data_dir / "processed" / "latest_predictions.csv", generate_predictions(features)
    )
    write_predictions_csv(
        data_dir / "processed" / "historical_predictions.csv",
        generate_historical_predictions(features),
    )
    duckdb_path = data_dir / "duckdb" / "swell_quant.duckdb"
    mirror_pipeline_csvs_to_duckdb(data_dir, duckdb_path)

    payload = load_duckdb_storage_artifact(duckdb_path, data_dir)
    missing_payload = load_duckdb_storage_artifact(tmp_path / "missing.duckdb")

    assert payload["status"] == "healthy"
    assert payload["total_rows"] > 0
    assert payload["tables"][0]["name"] == "raw_prices"
    assert payload["tables"][0]["row_count"] == len(bars)
    assert payload["tables"][0]["source_row_count"] == len(bars)
    assert payload["tables"][0]["row_count_matches"] is True
    assert payload["tables"][0]["schema_matches"] is True
    assert payload["schema_mismatch_tables"] == []
    assert payload["inconsistent_tables"] == []
    assert payload["disclaimer"] == "仅用于研究，不构成投资建议"
    assert missing_payload["status"] == "missing"
    assert missing_payload["missing_tables"]


def test_local_api_duckdb_storage_artifact_detects_stale_mirror(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    bars = generate_sample_bars(days=8)
    features = compute_features(bars)
    labels = compute_labels(bars)
    write_price_bars_csv(data_dir / "raw" / "sample_prices.csv", bars)
    write_features_csv(data_dir / "processed" / "sample_features.csv", features)
    write_labels_csv(data_dir / "processed" / "sample_labels.csv", labels)
    write_training_samples_artifact(data_dir, features, labels)
    write_predictions_csv(
        data_dir / "processed" / "latest_predictions.csv", generate_predictions(features)
    )
    write_predictions_csv(
        data_dir / "processed" / "historical_predictions.csv",
        generate_historical_predictions(features),
    )
    duckdb_path = data_dir / "duckdb" / "swell_quant.duckdb"
    mirror_pipeline_csvs_to_duckdb(data_dir, duckdb_path)
    write_price_bars_csv(data_dir / "raw" / "sample_prices.csv", generate_sample_bars(days=9))

    payload = load_duckdb_storage_artifact(duckdb_path, data_dir)

    assert payload["status"] == "inconsistent"
    assert payload["inconsistent_tables"] == ["raw_prices"]
    assert payload["tables"][0]["row_count"] == len(bars)
    assert payload["tables"][0]["source_row_count"] == 27
    assert payload["tables"][0]["row_count_matches"] is False


def test_local_api_duckdb_storage_artifact_detects_schema_mismatch(tmp_path: Path) -> None:
    import duckdb

    data_dir = tmp_path / "data"
    bars = generate_sample_bars(days=8)
    features = compute_features(bars)
    labels = compute_labels(bars)
    write_price_bars_csv(data_dir / "raw" / "sample_prices.csv", bars)
    write_features_csv(data_dir / "processed" / "sample_features.csv", features)
    write_labels_csv(data_dir / "processed" / "sample_labels.csv", labels)
    write_training_samples_artifact(data_dir, features, labels)
    write_predictions_csv(
        data_dir / "processed" / "latest_predictions.csv", generate_predictions(features)
    )
    write_predictions_csv(
        data_dir / "processed" / "historical_predictions.csv",
        generate_historical_predictions(features),
    )
    duckdb_path = data_dir / "duckdb" / "swell_quant.duckdb"
    mirror_pipeline_csvs_to_duckdb(data_dir, duckdb_path)
    with duckdb.connect(str(duckdb_path)) as connection:
        connection.execute(
            """
            CREATE OR REPLACE TABLE raw_prices AS
            SELECT symbol, date, close FROM raw_prices
            """
        )

    payload = load_duckdb_storage_artifact(duckdb_path, data_dir)

    assert payload["status"] == "schema_mismatch"
    assert payload["schema_mismatch_tables"] == ["raw_prices"]
    assert payload["tables"][0]["schema_matches"] is False
    assert payload["tables"][0]["missing_columns"] == [
        "open",
        "high",
        "low",
        "volume",
        "benchmark_close",
    ]


def test_local_api_latest_model_artifact(tmp_path: Path) -> None:
    model_path = tmp_path / "model.json"
    model_path.write_text(
        """
        {
          "model_version": "baseline-rule-v1",
          "model_type": "rule_baseline",
          "feature_names": ["momentum_5d", "return_1d"],
          "train_start": "2024-01-02",
          "train_end": "2024-01-16",
          "prediction_date": "2024-01-21",
          "row_count": 60,
          "disclaimer": "仅用于研究，不构成投资建议"
        }
        """,
        encoding="utf-8",
    )

    model = load_latest_model_artifact(model_path)

    assert model["model_version"] == "baseline-rule-v1"
    assert model["feature_count"] == 2
    assert model["row_count"] == 60
    assert model["requested_model_type"] == "rule_baseline"
    assert model["training_backend"] == "rule_baseline"
    assert model["dependency_status"] == "legacy_not_recorded"
    assert model["training_params"] == {}
    assert model["feature_importance"] == []
    assert model["label_gap_days"] == 5
    assert model["evaluation_status"] == "not_available"
    assert model["metrics"] == {}


def test_local_api_model_route_dispatches_list_and_detail(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    model_path = models_dir / "baseline-rule-v1.json"
    model_path.parent.mkdir(parents=True)
    model_path.write_text(
        """
        {
          "model_version": "baseline-rule-v1",
          "model_type": "rule_baseline",
          "feature_names": ["momentum_5d", "return_1d", "volume_change_1d"],
          "train_start": "2024-01-02",
          "train_end": "2024-01-16",
          "prediction_date": "2024-01-21",
          "row_count": 60,
          "requested_model_type": "lightgbm",
          "training_backend": "rule_baseline_fallback",
          "dependency_status": "lightgbm_missing",
          "label_gap_days": 5,
          "evaluation_status": "ready",
          "evaluation_train_start": "2024-01-02",
          "evaluation_train_end": "2024-01-04",
          "validation_start": "2024-01-10",
          "validation_end": "2024-01-10",
          "test_start": "2024-01-16",
          "test_end": "2024-01-16",
          "metrics": {"labeled_row_count": 45, "top1_outperform_rate": 1.0},
          "feature_importance": [{"feature_name": "momentum_5d", "rank": 1, "importance": 0.7, "raw_importance": 0.7, "importance_type": "rule_weight"}],
          "disclaimer": "仅用于研究，不构成投资建议"
        }
        """,
        encoding="utf-8",
    )

    models = load_models_artifact(models_dir)
    detail = load_model_artifact(model_path)
    list_status, list_payload = load_model_route("/api/models", tmp_path)
    detail_status, detail_payload = load_model_route("/api/models/baseline-rule-v1", tmp_path)
    missing_status, missing_payload = load_model_route("/api/models/nope", tmp_path)
    ignored = load_model_route("/api/status", tmp_path)

    assert models["count"] == 1
    assert "feature_names" not in models["models"][0]
    assert models["models"][0]["feature_count"] == 3
    assert models["models"][0]["requested_model_type"] == "lightgbm"
    assert models["models"][0]["training_backend"] == "rule_baseline_fallback"
    assert models["models"][0]["dependency_status"] == "lightgbm_missing"
    assert models["models"][0]["evaluation_status"] == "ready"
    assert detail["model_version"] == "baseline-rule-v1"
    assert detail["feature_names"] == ["momentum_5d", "return_1d", "volume_change_1d"]
    assert detail["requested_model_type"] == "lightgbm"
    assert detail["training_backend"] == "rule_baseline_fallback"
    assert detail["metrics"]["top1_outperform_rate"] == 1.0
    assert detail["feature_importance"][0]["feature_name"] == "momentum_5d"
    assert detail["path"].endswith("baseline-rule-v1.json")
    assert list_status.value == 200
    assert list_payload["models"][0]["model_version"] == "baseline-rule-v1"
    assert detail_status.value == 200
    assert detail_payload["feature_count"] == 3
    assert missing_status.value == 404
    assert missing_payload["error"] == "model_not_found"
    assert ignored is None


def test_local_api_predictions_route_filters_historical_predictions(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=8)
    features = compute_features(bars)
    predictions_path = write_predictions_csv(
        tmp_path / "historical_predictions.csv",
        generate_historical_predictions(features),
    )

    latest = load_predictions_artifact(predictions_path, {})
    top_one = load_predictions_artifact(predictions_path, {"top_n": ["1"]})
    model_filtered = load_predictions_artifact(
        predictions_path, {"model_version": ["baseline-rule-v1"], "date": ["2024-01-08"]}
    )

    assert latest["filters"]["date"] == "2024-01-09"
    assert latest["available_dates"] == ["2024-01-09", "2024-01-08", "2024-01-07"]
    assert latest["model_versions"] == ["baseline-rule-v1"]
    assert latest["count"] == 3
    assert top_one["count"] == 1
    assert top_one["predictions"][0]["rank"] == 1
    assert model_filtered["count"] == 3


def test_local_api_prediction_route_dispatches(tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed"
    bars = generate_sample_bars(days=8)
    features = compute_features(bars)
    write_predictions_csv(
        processed_dir / "historical_predictions.csv",
        generate_historical_predictions(features),
    )

    status, payload = load_prediction_route("/api/predictions", {"top_n": ["2"]}, tmp_path)
    ignored = load_prediction_route("/api/status", {}, tmp_path)

    assert status.value == 200
    assert payload["count"] == 2
    assert ignored is None


def test_local_api_report_route_dispatches(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    report_path = reports_dir / "sample_research_summary.md"
    report_path.write_text(
        "# Swell Quant 离线研究摘要\n\n"
        "> 仅用于研究，不构成投资建议。\n\n"
        "## 模型\n\n"
        "- 模型版本：`baseline-rule-v1`\n\n"
        "## 回测摘要\n\n"
        "- 回测 ID：`sample-topn-baseline`\n",
        encoding="utf-8",
    )
    report_path.with_suffix(".json").write_text(
        """
        {
          "report_id": "sample-research-summary",
          "title": "Swell Quant 离线研究摘要",
          "model": {"model_version": "baseline-rule-v1"},
          "backtest": {"backtest_id": "sample-topn-baseline"},
          "predictions": [{"rank": 1, "symbol": "000300.SH"}],
          "risk_notes": ["仅用于研究，不构成投资建议"]
        }
        """,
        encoding="utf-8",
    )
    (reports_dir / "sample_ai_research_summary.json").write_text(
        """
        {
          "report_id": "sample-ai-research-summary",
          "status": "skipped",
          "provider": "disabled",
          "model": null,
          "reason": "missing_or_disabled_llm_provider",
          "content": "",
          "disclaimer": "仅用于研究，不构成投资建议"
        }
        """,
        encoding="utf-8",
    )

    list_payload = load_reports_artifact(report_path)
    detail_payload = load_report_artifact(report_path)
    list_status, route_list_payload = load_report_route("/api/reports", tmp_path)
    detail_status, route_detail_payload = load_report_route(
        "/api/reports/sample-research-summary", tmp_path
    )
    latest_status, latest_payload = load_report_route("/api/reports/latest", tmp_path)
    missing_status, missing_payload = load_report_route("/api/reports/nope", tmp_path)
    ignored = load_report_route("/api/status", tmp_path)

    assert list_payload["count"] == 1
    assert "body" not in list_payload["reports"][0]
    assert detail_payload["model_version"] == "baseline-rule-v1"
    assert detail_payload["backtest_id"] == "sample-topn-baseline"
    assert detail_payload["payload_path"].endswith("sample_research_summary.json")
    assert detail_payload["structured"]["predictions"][0]["symbol"] == "000300.SH"
    assert detail_payload["ai_report"]["status"] == "skipped"
    assert "不构成投资建议" in detail_payload["body"]
    assert list_status.value == 200
    assert route_list_payload["reports"][0]["report_id"] == "sample-research-summary"
    assert detail_status.value == 200
    assert route_detail_payload["report_id"] == "sample-research-summary"
    assert latest_status.value == 200
    assert latest_payload["report_id"] == "sample-research-summary"
    assert missing_status.value == 404
    assert missing_payload["error"] == "report_not_found"
    assert ignored is None


def test_local_api_backtest_route_dispatches(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    predictions = generate_historical_predictions(features)
    reports_dir = tmp_path / "reports"
    backtest_path = write_backtest_result(
        reports_dir / "sample_backtest.json",
        run_top_n_backtest(bars, predictions),
    )

    list_payload = load_backtests_artifact(backtest_path)
    list_status, route_list_payload = load_backtest_route("/api/backtests", tmp_path)
    detail_status, detail_payload = load_backtest_route(
        "/api/backtests/sample-topn-baseline", tmp_path
    )
    latest_status, latest_payload = load_backtest_route("/api/backtests/latest", tmp_path)
    missing_status, missing_payload = load_backtest_route("/api/backtests/nope", tmp_path)
    ignored = load_backtest_route("/api/status", tmp_path)

    assert list_payload["count"] == 1
    assert "equity_curve" not in list_payload["backtests"][0]
    assert list_payload["backtests"][0]["execution_price"] == "next_day_open"
    assert list_payload["backtests"][0]["slippage_rate"] == 0.0005
    assert list_payload["backtests"][0]["rejected_trade_count"] > 0
    assert "max_drawdown" in list_payload["backtests"][0]
    assert list_status.value == 200
    assert route_list_payload["backtests"][0]["backtest_id"] == "sample-topn-baseline"
    assert detail_status.value == 200
    assert detail_payload["fee_rate"] == 0.001
    assert detail_payload["holding_period"] == "next_day_open_to_close"
    assert detail_payload["equity_curve"][0]["portfolio_value"] > 1.0
    assert latest_status.value == 200
    assert latest_payload["backtest_id"] == "sample-topn-baseline"
    assert missing_status.value == 404
    assert missing_payload["error"] == "backtest_not_found"
    assert ignored is None


def test_local_api_stock_artifact_loaders(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    predictions = generate_historical_predictions(features)
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    write_price_bars_csv(raw_dir / "sample_prices.csv", bars)
    write_features_csv(processed_dir / "sample_features.csv", features)
    write_predictions_csv(processed_dir / "historical_predictions.csv", predictions)

    summary = load_stock_summary_artifact(tmp_path, "000300.SH")
    prices = load_stock_prices_artifact(raw_dir / "sample_prices.csv", "000300.SH")
    stock_features = load_stock_features_artifact(
        processed_dir / "sample_features.csv", "000300.SH"
    )
    stock_predictions = load_stock_predictions_artifact(
        processed_dir / "historical_predictions.csv", "000300.SH"
    )

    assert summary is not None
    assert summary["price_row_count"] == 20
    assert summary["prediction_row_count"] == 15
    assert prices is not None and prices["prices"][0]["date"] == "2024-01-02"
    assert stock_features is not None and stock_features["features"][0]["return_1d"] is None
    assert stock_predictions is not None
    assert stock_predictions["predictions"][0]["rank"] == 1
    assert load_stock_summary_artifact(tmp_path, "NOPE") is None


def test_local_api_stocks_artifact_uses_prices_as_universe(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=8)
    features = compute_features(bars)
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    write_price_bars_csv(raw_dir / "sample_prices.csv", bars)
    write_predictions_csv(
        processed_dir / "historical_predictions.csv",
        generate_historical_predictions(features),
    )

    stocks = load_stocks_artifact(tmp_path)

    assert stocks["count"] == 3
    assert [row["symbol"] for row in stocks["stocks"]] == [
        "000001.SZ",
        "000300.SH",
        "000905.SH",
    ]
    assert stocks["stocks"][0]["price_row_count"] == 8
    assert stocks["stocks"][0]["prediction_row_count"] == 3
    assert stocks["stocks"][0]["start_date"] == "2024-01-02"
    assert stocks["stocks"][0]["end_date"] == "2024-01-09"
    assert stocks["disclaimer"] == "仅用于研究，不构成投资建议"


def test_local_api_stock_route_dispatches(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=8)
    features = compute_features(bars)
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    write_price_bars_csv(raw_dir / "sample_prices.csv", bars)
    write_features_csv(processed_dir / "sample_features.csv", features)
    write_predictions_csv(
        processed_dir / "historical_predictions.csv", generate_historical_predictions(features)
    )

    list_status, list_payload = load_stock_route("/api/stocks", tmp_path)
    status, payload = load_stock_route("/api/stocks/000300.SH/prices", tmp_path)
    missing_status, missing_payload = load_stock_route("/api/stocks/NOPE", tmp_path)
    ignored = load_stock_route("/api/status", tmp_path)
    missing_list_status, missing_list_payload = load_stock_route(
        "/api/stocks", tmp_path / "missing"
    )

    assert list_status.value == 200
    assert list_payload["count"] == 3
    assert status.value == 200
    assert payload["count"] == 8
    assert missing_status.value == 404
    assert missing_payload["error"] == "symbol_not_found"
    assert ignored is None
    assert missing_list_status.value == 404
    assert missing_list_payload["error"] == "artifact_missing"


def test_local_api_can_trigger_pipeline(tmp_path: Path) -> None:
    payload = run_pipeline_for_api(tmp_path / "data")

    assert payload["status"] == "success"
    assert payload["requested_task"] == "pipeline"
    assert payload["execution_mode"] == "full_pipeline_refresh"
    assert payload["manifest_path"].endswith("pipeline_run.json")
    assert payload["status_path"].endswith("research_status.json")
    assert [step["name"] for step in payload["steps"]] == [
        "prepare_directories",
        "data_update",
        "data_quality",
        "features",
        "labels",
        "train",
        "backtest",
        "duckdb_mirror",
        "report",
    ]
    assert (tmp_path / "data" / "reports" / "research_status.json").exists()


def test_local_api_can_trigger_named_task_through_full_pipeline(tmp_path: Path) -> None:
    payload = run_pipeline_for_api(tmp_path / "data", requested_task="model_train")

    assert payload["status"] == "success"
    assert payload["requested_task"] == "model_train"
    assert payload["execution_mode"] == "full_pipeline_refresh"
    assert "dependent artifacts stay consistent" in payload["message"]
    assert (tmp_path / "data" / "models" / "baseline-rule-v1.json").exists()


def test_local_api_pipeline_trigger_uses_configured_settings(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, Settings] = {}

    class FakeStatus:
        value = "success"

    class FakeResult:
        name = "prepare_directories"
        status = FakeStatus()
        message = "ok"
        duration_seconds = 0.0

    def fake_runner(settings: Settings):
        captured["settings"] = settings
        reports_dir = settings.data_dir / "reports"
        reports_dir.mkdir(parents=True)
        return (
            [FakeResult()],
            reports_dir / "pipeline_run.json",
            reports_dir / "research_status.json",
        )

    monkeypatch.setattr(
        "swell_quant.api.local_server._load_pipeline_runner",
        lambda: fake_runner,
    )
    settings = Settings(
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "custom.duckdb",
        data_source="akshare",
        model_type="rule_baseline",
    )

    payload = run_pipeline_for_api(settings)

    assert payload["status"] == "success"
    assert captured["settings"] is settings
    assert captured["settings"].data_source == "akshare"
    assert captured["settings"].model_type == "rule_baseline"


def test_local_api_pipeline_trigger_returns_busy_when_locked(tmp_path: Path) -> None:
    lock = threading.Lock()
    lock.acquire()
    try:
        payload = run_pipeline_for_api(
            tmp_path / "data", lock=lock, requested_task="report_generate"
        )
    finally:
        lock.release()

    assert payload["status"] == "busy"
    assert payload["requested_task"] == "report_generate"
    assert payload["error"] == "pipeline_already_running"
    assert pipeline_status_to_http_status(payload["status"]).value == 409
