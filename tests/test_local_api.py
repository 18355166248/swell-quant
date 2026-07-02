from pathlib import Path

from swell_quant.api.local_server import (
    load_backtest_artifact,
    load_data_quality_artifact,
    load_json_artifact,
    load_latest_predictions_artifact,
    load_text_artifact,
    missing_artifact_payload,
)
from swell_quant.data.quality import validate_price_bars, write_quality_report
from swell_quant.data.sample_data import generate_sample_bars
from swell_quant.research.backtest import run_top_n_backtest, write_backtest_result
from swell_quant.research.features import compute_features
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
