import json
from pathlib import Path

from swell_quant.api.local_server import load_json_artifact, load_text_artifact, missing_artifact_payload


def test_local_api_artifact_loaders_read_status_pipeline_and_report(tmp_path: Path) -> None:
    status_path = tmp_path / "research_status.json"
    pipeline_path = tmp_path / "pipeline_run.json"
    report_path = tmp_path / "sample_research_summary.md"

    status_path.write_text(
        json.dumps({"pipeline": {"status": "success"}, "disclaimer": "仅用于研究，不构成投资建议"}),
        encoding="utf-8",
    )
    pipeline_path.write_text(json.dumps({"status": "success", "step_count": 8}), encoding="utf-8")
    report_path.write_text("# Summary\n\n仅用于研究，不构成投资建议\n", encoding="utf-8")

    assert load_json_artifact(status_path)["pipeline"]["status"] == "success"
    assert load_json_artifact(pipeline_path)["step_count"] == 8
    assert "不构成投资建议" in load_text_artifact(report_path)


def test_missing_artifact_payload_points_to_pipeline(tmp_path: Path) -> None:
    payload = missing_artifact_payload(tmp_path / "missing.json")

    assert payload["error"] == "artifact_missing"
    assert payload["hint"] == "run `python3 scripts/run_pipeline.py` first"
