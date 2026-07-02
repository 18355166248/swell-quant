from swell_quant.core.pipeline import PipelineStep, StepStatus, run_steps


def test_run_steps_reports_success_and_skipped() -> None:
    results = run_steps(
        [
            PipelineStep("ready", lambda: "ok"),
            PipelineStep("future", lambda: "not used", enabled=False),
        ]
    )

    assert [result.status for result in results] == [StepStatus.SUCCESS, StepStatus.SKIPPED]
    assert results[0].message == "ok"


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
