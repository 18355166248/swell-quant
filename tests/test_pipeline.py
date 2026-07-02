import json
from pathlib import Path

from swell_quant.core.pipeline import PipelineStep, StepStatus, run_steps, write_run_manifest


def test_run_steps_reports_success_and_skipped() -> None:
    results = run_steps(
        [
            PipelineStep("ready", lambda: "ok"),
            PipelineStep("future", lambda: "not used", enabled=False),
        ]
    )

    assert [result.status for result in results] == [StepStatus.SUCCESS, StepStatus.SKIPPED]
    assert results[0].message == "ok"
    assert results[0].started_at
    assert results[0].ended_at
    assert results[0].duration_seconds >= 0


def test_run_steps_stops_on_failure() -> None:
    def fail() -> str:
        raise RuntimeError("boom")

    results = run_steps(
        [
            PipelineStep("first", lambda: "ok"),
            PipelineStep("fail", fail),
            PipelineStep("never", lambda: "unused"),
        ]
    )

    assert [result.name for result in results] == ["first", "fail"]
    assert results[-1].status == StepStatus.FAILED


def test_write_run_manifest_serializes_results(tmp_path: Path) -> None:
    results = run_steps(
        [
            PipelineStep("first", lambda: "ok"),
            PipelineStep("future", lambda: "unused", enabled=False),
        ]
    )

    path = write_run_manifest(tmp_path / "pipeline_run.json", results)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["status"] == "skipped"
    assert payload["step_count"] == 2
    assert payload["steps"][0]["name"] == "first"
    assert payload["steps"][0]["status"] == "success"
    assert payload["steps"][1]["status"] == "skipped"
