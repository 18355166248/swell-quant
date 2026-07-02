from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable


class StepStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class PipelineStep:
    name: str
    run: Callable[[], str]
    enabled: bool = True


@dataclass(frozen=True)
class StepResult:
    name: str
    status: StepStatus
    message: str
    started_at: str
    ended_at: str
    duration_seconds: float


def run_steps(steps: Iterable[PipelineStep]) -> list[StepResult]:
    results: list[StepResult] = []
    for step in steps:
        started_at = _now_utc_iso()
        started_perf = perf_counter()
        if not step.enabled:
            ended_at = _now_utc_iso()
            results.append(
                StepResult(
                    name=step.name,
                    status=StepStatus.SKIPPED,
                    message="step not implemented",
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_seconds=_duration(started_perf),
                )
            )
            continue

        try:
            message = step.run()
        except Exception as exc:  # pragma: no cover - exercised through CLI behavior later.
            # pipeline 是端到端集成入口，失败必须保留明确阶段名，方便定位断在哪一步。
            results.append(
                StepResult(
                    name=step.name,
                    status=StepStatus.FAILED,
                    message=str(exc),
                    started_at=started_at,
                    ended_at=_now_utc_iso(),
                    duration_seconds=_duration(started_perf),
                )
            )
            break
        results.append(
            StepResult(
                name=step.name,
                status=StepStatus.SUCCESS,
                message=message,
                started_at=started_at,
                ended_at=_now_utc_iso(),
                duration_seconds=_duration(started_perf),
            )
        )

    return results


def write_run_manifest(path: Path, results: list[StepResult]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    status = StepStatus.SUCCESS.value
    if any(result.status == StepStatus.FAILED for result in results):
        status = StepStatus.FAILED.value
    elif any(result.status == StepStatus.SKIPPED for result in results):
        status = StepStatus.SKIPPED.value

    payload = {
        "status": status,
        "step_count": len(results),
        "started_at": results[0].started_at if results else None,
        "ended_at": results[-1].ended_at if results else None,
        "duration_seconds": round(sum(result.duration_seconds for result in results), 6),
        "steps": [
            {
                "name": result.name,
                "status": result.status.value,
                "message": result.message,
                "started_at": result.started_at,
                "ended_at": result.ended_at,
                "duration_seconds": result.duration_seconds,
            }
            for result in results
        ],
    }
    # 运行清单是 CLI/API/页面共用的任务状态来源，避免只依赖终端输出做人工判断。
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _duration(started_perf: float) -> float:
    return round(perf_counter() - started_perf, 6)
