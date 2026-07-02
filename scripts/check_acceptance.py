#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from swell_quant.core.config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Swell Quant research acceptance gates.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable acceptance JSON.")
    args = parser.parse_args()

    settings = Settings.from_env()
    status_path = settings.data_dir / "reports" / "research_status.json"
    if not status_path.exists():
        payload = {
            "status": "missing",
            "passed": False,
            "path": str(status_path),
            "message": "run `python3 scripts/run_pipeline.py` first",
            "checks": [],
        }
    else:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        payload = status.get(
            "acceptance",
            {
                "status": "missing",
                "passed": False,
                "path": str(status_path),
                "message": "acceptance section missing from research_status.json",
                "checks": [],
            },
        )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"acceptance_status={payload.get('status')}")
        print(f"passed={str(bool(payload.get('passed'))).lower()}")
        for check in payload.get("checks", []):
            print(f"check={check['key']} status={check['status']} message={check['message']}")

    # 整体研究链路验收失败时返回非零，便于本地无页面验收和后续 CI 直接复用。
    return 0 if payload.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
