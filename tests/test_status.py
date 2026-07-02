from pathlib import Path

from swell_quant.data.quality import validate_price_bars
from swell_quant.data.sample_data import generate_sample_bars
from swell_quant.research.backtest import run_top_n_backtest
from swell_quant.research.features import compute_features
from swell_quant.research.labels import compute_labels
from swell_quant.research.modeling import (
    generate_historical_predictions,
    generate_predictions,
    train_baseline_model,
)
from swell_quant.research.status import build_research_status


def write_complete_artifacts(tmp_path: Path) -> dict[str, Path]:
    artifact_paths = {
        "data_quality": tmp_path / "data_quality.json",
        "model": tmp_path / "model.json",
        "training_samples": tmp_path / "training_samples.csv",
        "latest_predictions": tmp_path / "latest_predictions.csv",
        "historical_predictions": tmp_path / "historical_predictions.csv",
        "duckdb": tmp_path / "swell_quant.duckdb",
        "backtest": tmp_path / "backtest.json",
        "summary": tmp_path / "summary.md",
        "pipeline_run": tmp_path / "pipeline_run.json",
    }
    for path in artifact_paths.values():
        path.write_text("ok", encoding="utf-8")
    return artifact_paths


def test_build_research_status_aggregates_outputs(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)
    quality = validate_price_bars(bars)
    metadata = train_baseline_model(features, labels)
    predictions = generate_predictions(features)
    backtest = run_top_n_backtest(bars, generate_historical_predictions(features))
    manifest = {
        "status": "success",
        "started_at": "2024-01-01T00:00:00.000+00:00",
        "ended_at": "2024-01-01T00:00:01.000+00:00",
        "duration_seconds": 1.0,
        "step_count": 8,
    }
    artifact_paths = write_complete_artifacts(tmp_path)

    storage_status = {"status": "healthy"}
    status = build_research_status(
        quality, metadata, predictions, backtest, manifest, storage_status, artifact_paths
    )

    assert status["disclaimer"] == "仅用于研究，不构成投资建议"
    assert status["acceptance"]["status"] == "passed"
    assert status["acceptance"]["failed_count"] == 0
    assert status["artifact_status"]["status"] == "complete"
    assert status["artifact_status"]["artifacts"][0]["size_bytes"] == 2
    assert status["artifact_status"]["artifacts"][0]["updated_at"] is not None
    assert status["pipeline"]["status"] == "success"
    assert status["data_quality"]["passed"] is True
    assert status["model"]["model_version"] == "baseline-rule-v1"
    assert status["model"]["requested_model_type"] == "lightgbm"
    assert status["model"]["training_backend"] == "rule_baseline_fallback"
    assert status["model"]["dependency_status"] in {"lightgbm_available", "lightgbm_missing"}
    assert status["model"]["evaluation_status"] == "ready"
    assert status["model"]["label_gap_days"] == 5
    assert status["model"]["metrics"]["test_prediction_dates"] == 1
    assert status["predictions"]["count"] == 3
    assert status["predictions"]["top"][0]["rank"] == 1
    assert status["backtest"]["trade_count"] == 14
    assert status["backtest"]["rejected_trade_count"] > 0
    assert status["backtest"]["fee_rate"] == 0.001
    assert status["backtest"]["slippage_rate"] == 0.0005
    assert status["backtest"]["annualized_return"] > status["backtest"]["cumulative_return"]
    assert status["backtest"]["max_drawdown"] <= 0
    assert status["backtest"]["win_rate"] >= 0
    assert status["artifacts"]["duckdb"].endswith("swell_quant.duckdb")
    assert status["artifacts"]["summary"].endswith("summary.md")


def test_build_research_status_fails_acceptance_when_storage_is_stale(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)
    quality = validate_price_bars(bars)
    metadata = train_baseline_model(features, labels)
    predictions = generate_predictions(features)
    backtest = run_top_n_backtest(bars, generate_historical_predictions(features), top_n=2)
    manifest = {
        "status": "success",
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:00:01Z",
        "duration_seconds": 1.0,
        "step_count": 9,
    }

    status = build_research_status(
        quality,
        metadata,
        predictions,
        backtest,
        manifest,
        {"status": "inconsistent"},
        write_complete_artifacts(tmp_path),
    )

    assert status["acceptance"]["status"] == "failed"
    assert status["acceptance"]["failed_count"] == 1
    assert status["acceptance"]["checks"][2]["key"] == "duckdb_mirror_healthy"


def test_build_research_status_fails_acceptance_when_artifact_is_missing(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)
    quality = validate_price_bars(bars)
    metadata = train_baseline_model(features, labels)
    predictions = generate_predictions(features)
    backtest = run_top_n_backtest(bars, generate_historical_predictions(features), top_n=2)
    manifest = {
        "status": "success",
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:00:01Z",
        "duration_seconds": 1.0,
        "step_count": 9,
    }
    existing_artifact = tmp_path / "exists.json"
    existing_artifact.write_text("{}", encoding="utf-8")

    status = build_research_status(
        quality,
        metadata,
        predictions,
        backtest,
        manifest,
        {"status": "healthy"},
        {
            "model": existing_artifact,
            "summary": tmp_path / "missing.md",
        },
    )

    assert status["acceptance"]["status"] == "failed"
    assert status["artifact_status"]["status"] == "missing"
    assert status["artifact_status"]["missing"] == ["summary"]
    assert status["artifact_status"]["artifacts"][1]["size_bytes"] is None
    assert status["artifact_status"]["artifacts"][1]["updated_at"] is None
    assert status["acceptance"]["checks"][-1]["key"] == "artifacts_complete"
