from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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


def run_steps(steps: Iterable[PipelineStep]) -> list[StepResult]:
    results: list[StepResult] = []
    for step in steps:
        if not step.enabled:
            results.append(
                StepResult(name=step.name, status=StepStatus.SKIPPED, message="step not implemented")
            )
            continue

        try:
            message = step.run()
        except Exception as exc:  # pragma: no cover - exercised through CLI behavior later.
            # pipeline 是端到端集成入口，失败必须保留明确阶段名，方便定位断在哪一步。
            results.append(StepResult(name=step.name, status=StepStatus.FAILED, message=str(exc)))
            break
        results.append(StepResult(name=step.name, status=StepStatus.SUCCESS, message=message))

    return results
