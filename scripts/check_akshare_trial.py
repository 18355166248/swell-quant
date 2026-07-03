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
    return data_dir / "reports" / "akshare_trial_run.json"


def build_trial_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "missing",
            "passed": False,
            "path": str(path),
            "message": "run `make akshare-trial` or `python3 scripts/run_akshare_trial.py --dry-run` first",
            "step_count": 0,
            "failed_step": None,
            "disclaimer": "仅用于研究，不构成投资建议",
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    steps = payload.get("steps") or []
    failed_step = next((step.get("name") for step in steps if step.get("status") == "failed"), None)
    real_data_verified = payload.get("real_data_verified")
    if real_data_verified is None:
        # 老版本 dry-run 摘要没有该字段；检查脚本必须保守区分预演通过和真实行情已验证。
        real_data_verified = payload.get("status") == "passed"
    return {
        "status": payload.get("status", "unknown"),
        "passed": payload.get("passed") is True,
        "trial_kind": payload.get("trial_kind")
        or ("real_data" if real_data_verified else "dry_run"),
        "real_data_verified": real_data_verified,
        "path": str(path),
        "started_at": payload.get("started_at"),
        "ended_at": payload.get("ended_at"),
        "duration_seconds": payload.get("duration_seconds"),
        "env": payload.get("env") or {},
        "step_count": len(steps),
        "failed_step": failed_step,
        "steps": steps,
        "disclaimer": payload.get("disclaimer", "仅用于研究，不构成投资建议"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check latest AKShare real-data trial summary.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable trial status.")
    args = parser.parse_args()

    settings = Settings.from_env()
    payload = build_trial_status(default_trial_path(settings.data_dir))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"akshare_trial_status={payload.get('status')}")
        print(f"passed={str(bool(payload.get('passed'))).lower()}")
        print(f"path={payload.get('path')}")
        print(f"trial_kind={payload.get('trial_kind')}")
        print(f"real_data_verified={str(bool(payload.get('real_data_verified'))).lower()}")
        print(f"step_count={payload.get('step_count')}")
        print(f"failed_step={payload.get('failed_step') or '-'}")
        env = payload.get("env") or {}
        if env:
            print(f"universe_mode={env.get('AKSHARE_UNIVERSE_MODE', '-')}")
            print(f"max_symbols={env.get('AKSHARE_MAX_SYMBOLS', '-')}")
            print(
                f"date_range={env.get('AKSHARE_START_DATE', '-')}..{env.get('AKSHARE_END_DATE', '-')}"
            )
        if payload.get("message"):
            print(f"message={payload.get('message')}")

    return 0 if payload.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
