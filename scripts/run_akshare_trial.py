#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class TrialStep:
    name: str
    command: tuple[str, ...]


def build_trial_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DATA_SOURCE": "akshare",
            "AKSHARE_UNIVERSE_MODE": args.universe_mode,
            "AKSHARE_MAX_SYMBOLS": str(args.max_symbols),
            "AKSHARE_START_DATE": args.start_date,
            "AKSHARE_END_DATE": args.end_date,
            "AKSHARE_BENCHMARK_SYMBOL": args.benchmark_symbol,
        }
    )
    return env


def build_trial_steps(args: argparse.Namespace) -> list[TrialStep]:
    steps = [
        TrialStep("config", (sys.executable, str(ROOT_DIR / "scripts" / "check_config.py"))),
    ]
    if not args.skip_universe_check:
        steps.append(
            TrialStep(
                "akshare_universe",
                (sys.executable, str(ROOT_DIR / "scripts" / "check_akshare_universe.py")),
            )
        )
    steps.extend(
        [
            TrialStep("pipeline", (sys.executable, str(ROOT_DIR / "scripts" / "run_pipeline.py"))),
            TrialStep(
                "data_source",
                (sys.executable, str(ROOT_DIR / "scripts" / "check_data_source.py")),
            ),
            TrialStep(
                "acceptance",
                (sys.executable, str(ROOT_DIR / "scripts" / "check_acceptance.py")),
            ),
            TrialStep(
                "progress", (sys.executable, str(ROOT_DIR / "scripts" / "check_progress.py"))
            ),
        ]
    )
    return steps


def run_trial(args: argparse.Namespace) -> dict[str, Any]:
    env = build_trial_env(args)
    steps = build_trial_steps(args)
    if args.dry_run:
        return {
            "status": "dry_run",
            "passed": True,
            "env": _visible_trial_env(env),
            "steps": [
                {"name": step.name, "command": list(step.command), "status": "planned"}
                for step in steps
            ],
            "disclaimer": "仅用于研究，不构成投资建议",
        }

    results: list[dict[str, Any]] = []
    for step in steps:
        # 真实试跑按依赖顺序短路执行：股票池或采集门禁失败时，后续验收结果会被污染，应立即停下。
        completed = subprocess.run(
            step.command,
            cwd=ROOT_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        results.append(
            {
                "name": step.name,
                "command": list(step.command),
                "status": "passed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        if completed.returncode != 0:
            return _trial_payload("failed", results, env)

    return _trial_payload("passed", results, env)


def _trial_payload(
    status: str, results: list[dict[str, Any]], env: dict[str, str]
) -> dict[str, Any]:
    return {
        "status": status,
        "passed": status == "passed",
        "env": _visible_trial_env(env),
        "steps": results,
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def _visible_trial_env(env: dict[str, str]) -> dict[str, str]:
    keys = (
        "DATA_SOURCE",
        "AKSHARE_UNIVERSE_MODE",
        "AKSHARE_MAX_SYMBOLS",
        "AKSHARE_START_DATE",
        "AKSHARE_END_DATE",
        "AKSHARE_BENCHMARK_SYMBOL",
    )
    return {key: env[key] for key in keys}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded AKShare real-data trial.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable trial JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Only print planned commands.")
    parser.add_argument(
        "--universe-mode", default="csi800", choices=("csi800", "hs300_csi500", "manual")
    )
    parser.add_argument("--max-symbols", type=int, default=20)
    parser.add_argument("--start-date", default="20240102")
    parser.add_argument("--end-date", default="20240131")
    parser.add_argument("--benchmark-symbol", default="sh000906")
    parser.add_argument(
        "--skip-universe-check",
        action="store_true",
        help="Skip AKShare universe resolution check before running pipeline.",
    )
    args = parser.parse_args()
    if args.max_symbols <= 0:
        parser.error("--max-symbols must be greater than 0")

    payload = run_trial(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0 if payload["passed"] else 1


def _print_text(payload: dict[str, Any]) -> None:
    print(f"akshare_trial_status={payload['status']}")
    print(f"passed={str(payload['passed']).lower()}")
    for key, value in payload["env"].items():
        print(f"{key}={value}")
    for step in payload["steps"]:
        print(f"step={step['name']} status={step['status']}")
        if step.get("returncode") not in (None, 0):
            print(f"returncode={step['returncode']}")
            if step.get("stdout"):
                print(step["stdout"].rstrip())
            if step.get("stderr"):
                print(step["stderr"].rstrip())


if __name__ == "__main__":
    raise SystemExit(main())
