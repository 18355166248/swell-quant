#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from swell_quant.core.config import Settings


def default_trial_path(data_dir: Path) -> Path:
    return data_dir / "reports" / "fund_trial_run.json"


def last_passed_trial_path(path: Path) -> Path:
    return path.with_name("fund_trial_last_passed.json")


def build_fund_trial_status(path: Path) -> dict[str, Any]:
    last_passed = _load_last_passed_summary(last_passed_trial_path(path))
    if not path.exists():
        return {
            "status": "missing",
            "passed": False,
            "path": str(path),
            "last_passed": last_passed,
            "message": "run `make fund-trial` or `python3 scripts/run_fund_trial.py --dry-run` first",
            "step_count": 0,
            "failed_step": None,
            "disclaimer": "仅用于研究，不构成投资建议",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    steps = payload.get("steps") or []
    failed_step_payload = next((step for step in steps if step.get("status") == "failed"), None)
    return {
        "status": payload.get("status", "unknown"),
        "passed": payload.get("passed") is True,
        "trial_kind": payload.get("trial_kind", "real_data"),
        "real_data_verified": payload.get("real_data_verified") is True,
        "last_passed": last_passed,
        "path": str(path),
        "started_at": payload.get("started_at"),
        "ended_at": payload.get("ended_at"),
        "duration_seconds": payload.get("duration_seconds"),
        "env": payload.get("env") or {},
        "step_count": len(steps),
        "failed_step": failed_step_payload.get("name") if failed_step_payload else None,
        "failed_step_summary": _build_failed_step_summary(failed_step_payload),
        "steps": steps,
        "disclaimer": payload.get("disclaimer", "仅用于研究，不构成投资建议"),
    }


def _build_failed_step_summary(step: dict[str, Any] | None) -> dict[str, Any] | None:
    if step is None:
        return None
    return {
        "name": step.get("name"),
        "error": step.get("error"),
    }


def _load_last_passed_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("real_data_verified") is not True:
        return None
    return {
        "status": payload.get("status", "unknown"),
        "passed": payload.get("passed") is True,
        "trial_kind": payload.get("trial_kind") or "real_data",
        "real_data_verified": True,
        "path": str(path),
        "started_at": payload.get("started_at"),
        "ended_at": payload.get("ended_at"),
        "duration_seconds": payload.get("duration_seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check latest AKShare fund data trial summary.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable trial status.")
    args = parser.parse_args()
    settings = Settings.from_env()
    payload = build_fund_trial_status(default_trial_path(settings.data_dir))
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"fund_trial_status={payload.get('status')}")
        print(f"passed={str(bool(payload.get('passed'))).lower()}")
        print(f"path={payload.get('path')}")
        print(f"trial_kind={payload.get('trial_kind')}")
        print(f"real_data_verified={str(bool(payload.get('real_data_verified'))).lower()}")
        print(f"step_count={payload.get('step_count')}")
        print(f"failed_step={payload.get('failed_step') or '-'}")
        env = payload.get("env") or {}
        if env:
            print(f"fund_symbols={env.get('FUND_SYMBOLS', '-')}")
            print(f"date_range={env.get('FUND_START_DATE', '-')}..{env.get('FUND_END_DATE', '-')}")
        if payload.get("message"):
            print(f"message={payload.get('message')}")
    return 0 if payload.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
