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

from swell_quant.api.local_server import load_progress_artifact
from swell_quant.core.config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Show Swell Quant project stage progress.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable progress JSON.")
    args = parser.parse_args()

    try:
        settings = Settings.from_env()
    except ValueError as error:
        payload = {
            "status": "failed",
            "error": "invalid_settings",
            "message": str(error),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    payload = load_progress_artifact(settings)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"progress_status={payload['status']}")
    print(f"completed_stages={payload['completed_stage_count']}/{payload['stage_count']}")
    print(f"partial_stages={payload['partial_stage_count']}")
    print(f"current_stage={payload['current_stage']['name']}")
    for index, action in enumerate(payload.get("next_actions", []), start=1):
        print(f"next_action_{index}={action}")
    for stage in payload["stages"]:
        print(
            "stage="
            f"{stage['id']} status={stage['status']} "
            f"evidence={stage['completed_count']}/{stage['required_count']} "
            f"name={stage['name']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
