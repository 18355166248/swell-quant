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


def test_build_research_status_aggregates_outputs() -> None:
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

    storage_status = {"status": "healthy"}
    status = build_research_status(quality, metadata, predictions, backtest, manifest, storage_status)

    assert status["disclaimer"] == "仅用于研究，不构成投资建议"
    assert status["acceptance"]["status"] == "passed"
    assert status["acceptance"]["failed_count"] == 0
    assert status["pipeline"]["status"] == "success"
    assert status["data_quality"]["passed"] is True
    assert status["model"]["model_version"] == "baseline-rule-v1"
    assert status["predictions"]["count"] == 3
    assert status["predictions"]["top"][0]["rank"] == 1
    assert status["backtest"]["trade_count"] == 14
    assert status["artifacts"]["duckdb"] == "data/duckdb/swell_quant.duckdb"
    assert status["artifacts"]["summary"] == "data/reports/sample_research_summary.md"


def test_build_research_status_fails_acceptance_when_storage_is_stale() -> None:
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
    )

    assert status["acceptance"]["status"] == "failed"
    assert status["acceptance"]["failed_count"] == 1
    assert status["acceptance"]["checks"][2]["key"] == "duckdb_mirror_healthy"
