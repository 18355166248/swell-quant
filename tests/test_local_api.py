import threading
from pathlib import Path

from swell_quant.api.local_server import (
    load_backtest_artifact,
    load_backtest_route,
    load_backtests_artifact,
    load_data_quality_artifact,
    load_json_artifact,
    load_latest_predictions_artifact,
    load_settings_artifact,
    load_stock_features_artifact,
    load_stock_predictions_artifact,
    load_stock_prices_artifact,
    load_stock_route,
    load_stock_summary_artifact,
    load_task_detail_artifact,
    load_task_route,
    load_tasks_artifact,
    load_text_artifact,
    missing_artifact_payload,
    pipeline_status_to_http_status,
    run_pipeline_for_api,
)
from swell_quant.core.config import Settings
from swell_quant.data.quality import validate_price_bars, write_quality_report
from swell_quant.data.sample_data import generate_sample_bars, write_price_bars_csv
from swell_quant.research.backtest import run_top_n_backtest, write_backtest_result
from swell_quant.research.features import compute_features, write_features_csv
from swell_quant.research.modeling import generate_historical_predictions, generate_predictions, write_predictions_csv


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
    )
    settings.ensure_directories()
    (settings.data_dir / "reports" / "research_status.json").write_text("{}", encoding="utf-8")

    payload = load_settings_artifact(
        settings.data_dir,
        settings.duckdb_path,
        settings.deepseek_api_key is not None,
        settings.openai_api_key is not None,
    )

    serialized = str(payload)
    assert payload["api_keys"]["deepseek_configured"] is True
    assert payload["api_keys"]["openai_configured"] is False
    assert "deepseek-secret" not in serialized
    assert any(item["name"] == "status" and item["exists"] is True for item in payload["artifacts"])


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
    quality_path = write_quality_report(tmp_path / "data_quality.json", validate_price_bars(bars))
    predictions_path = write_predictions_csv(tmp_path / "predictions.csv", generate_predictions(features))
    backtest_path = write_backtest_result(
        tmp_path / "backtest.json",
        run_top_n_backtest(bars, generate_historical_predictions(features)),
    )

    quality = load_data_quality_artifact(quality_path)
    predictions = load_latest_predictions_artifact(predictions_path)
    backtest = load_backtest_artifact(backtest_path)

    assert quality["passed"] is True
    assert quality["row_count"] == 60
    assert predictions["count"] == 3
    assert predictions["predictions"][0]["rank"] == 1
    assert predictions["disclaimer"] == "仅用于研究，不构成投资建议"
    assert backtest["backtest_id"] == "sample-topn-baseline"
    assert backtest["trade_count"] == 14
    assert backtest["equity_curve"][0]["date"] == "2024-01-08"
    assert "portfolio_value" in backtest["equity_curve"][0]


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
    assert list_status.value == 200
    assert route_list_payload["backtests"][0]["backtest_id"] == "sample-topn-baseline"
    assert detail_status.value == 200
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
    stock_features = load_stock_features_artifact(processed_dir / "sample_features.csv", "000300.SH")
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

    status, payload = load_stock_route("/api/stocks/000300.SH/prices", tmp_path)
    missing_status, missing_payload = load_stock_route("/api/stocks/NOPE", tmp_path)
    ignored = load_stock_route("/api/status", tmp_path)

    assert status.value == 200
    assert payload["count"] == 8
    assert missing_status.value == 404
    assert missing_payload["error"] == "symbol_not_found"
    assert ignored is None


def test_local_api_can_trigger_pipeline(tmp_path: Path) -> None:
    payload = run_pipeline_for_api(tmp_path / "data")

    assert payload["status"] == "success"
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
        "report",
    ]
    assert (tmp_path / "data" / "reports" / "research_status.json").exists()


def test_local_api_pipeline_trigger_returns_busy_when_locked(tmp_path: Path) -> None:
    lock = threading.Lock()
    lock.acquire()
    try:
        payload = run_pipeline_for_api(tmp_path / "data", lock=lock)
    finally:
        lock.release()

    assert payload["status"] == "busy"
    assert payload["error"] == "pipeline_already_running"
    assert pipeline_status_to_http_status(payload["status"]).value == 409
