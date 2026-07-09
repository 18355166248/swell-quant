#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from swell_quant.data.fund_data import collect_akshare_fund_data
from swell_quant.research.funds import (
    FUND_PROFILES,
    build_fund_candidates,
    compute_fund_metrics,
    write_fund_candidates_csv,
    write_fund_metrics_csv,
    write_fund_nav_csv,
    write_funds_csv,
)


def run_trial(args: argparse.Namespace) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    started_counter = perf_counter()
    env = _visible_env(args)
    if args.dry_run:
        return _trial_payload(
            "dry_run",
            [{"name": "fund_data", "status": "planned", "fund_codes": list(args.fund_codes)}],
            env,
            started_at,
            started_counter,
        )

    try:
        result = collect_akshare_fund_data(
            fund_codes=tuple(args.fund_codes),
            start_date=args.start_date,
            end_date=args.end_date,
        )
        _write_fund_outputs(args.data_dir, result.funds, result.navs)
        steps = [
            {
                "name": "fund_data",
                "status": "passed",
                "succeeded_count": len(result.succeeded_codes),
                "failed_count": len(result.failed_codes),
                "failed_codes": list(result.failed_codes),
                "metadata": result.metadata,
            }
        ]
        return _trial_payload("passed", steps, env, started_at, started_counter)
    except Exception as error:  # noqa: BLE001 - 真实数据试跑需要把外部失败落盘，便于页面和 CLI 排查。
        return _trial_payload(
            "failed",
            [{"name": "fund_data", "status": "failed", "error": str(error)}],
            env,
            started_at,
            started_counter,
        )


def _write_fund_outputs(data_dir: Path, funds: list[Any], navs: list[Any]) -> None:
    raw_dir = data_dir / "raw"
    processed_dir = data_dir / "processed"
    write_funds_csv(raw_dir / "akshare_funds.csv", funds)
    write_fund_nav_csv(raw_dir / "akshare_fund_nav.csv", navs)
    metrics = compute_fund_metrics(funds, navs)
    write_fund_metrics_csv(processed_dir / "akshare_fund_metrics.csv", metrics)
    for profile in FUND_PROFILES:
        write_fund_candidates_csv(
            processed_dir / f"akshare_fund_candidates_{profile}.csv",
            build_fund_candidates(metrics, profile=profile),
        )


def _trial_payload(
    status: str,
    steps: list[dict[str, Any]],
    env: dict[str, Any],
    started_at: datetime,
    started_counter: float,
) -> dict[str, Any]:
    ended_at = datetime.now(UTC)
    return {
        "status": status,
        "passed": status in {"passed", "dry_run"},
        "trial_kind": "dry_run" if status == "dry_run" else "real_data",
        "real_data_verified": status == "passed",
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": round(perf_counter() - started_counter, 6),
        "artifact_path": str(default_trial_artifact_path(Path(env["DATA_DIR"]))),
        "env": env,
        "steps": steps,
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def _visible_env(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "DATA_DIR": str(args.data_dir),
        "FUND_SYMBOLS": ",".join(args.fund_codes),
        "FUND_START_DATE": args.start_date,
        "FUND_END_DATE": args.end_date,
    }


def default_trial_artifact_path(data_dir: Path) -> Path:
    if not data_dir.is_absolute():
        data_dir = ROOT_DIR / data_dir
    return data_dir / "reports" / "fund_trial_run.json"


def last_passed_trial_artifact_path(path: Path) -> Path:
    return path.with_name("fund_trial_last_passed.json")


def write_trial_payload(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_trial_artifacts(path: Path, payload: dict[str, Any]) -> Path:
    write_trial_payload(path, payload)
    if payload.get("real_data_verified") is True:
        write_trial_payload(last_passed_trial_artifact_path(path), payload)
    return path


def _parse_fund_codes(value: str) -> tuple[str, ...]:
    codes = tuple(item.strip() for item in value.split(",") if item.strip())
    invalid = [code for code in codes if not (len(code) == 6 and code.isdigit())]
    if invalid:
        raise argparse.ArgumentTypeError(f"fund codes must be 6-digit codes; invalid={invalid}")
    if not codes:
        raise argparse.ArgumentTypeError("at least one fund code is required")
    return codes


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded AKShare fund data trial.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable trial JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Only print planned fund trial.")
    parser.add_argument(
        "--fund-codes",
        type=_parse_fund_codes,
        default=_parse_fund_codes(os.getenv("FUND_SYMBOLS", "510300,159915,110022")),
    )
    parser.add_argument("--start-date", default=os.getenv("FUND_START_DATE", "20250101"))
    parser.add_argument("--end-date", default=os.getenv("FUND_END_DATE", "20260708"))
    parser.add_argument(
        "--data-dir", type=Path, default=Path(os.getenv("DATA_DIR", "./data")).expanduser()
    )
    args = parser.parse_args()

    payload = run_trial(args)
    write_trial_artifacts(Path(payload["artifact_path"]), payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0 if payload["passed"] else 1


def _print_text(payload: dict[str, Any]) -> None:
    print(f"fund_trial_status={payload['status']}")
    print(f"passed={str(payload['passed']).lower()}")
    print(f"trial_kind={payload['trial_kind']}")
    print(f"real_data_verified={str(payload['real_data_verified']).lower()}")
    print(f"artifact_path={payload['artifact_path']}")
    for step in payload["steps"]:
        print(f"step={step['name']} status={step['status']}")
        if step.get("error"):
            print(f"error={step['error']}")


if __name__ == "__main__":
    raise SystemExit(main())
