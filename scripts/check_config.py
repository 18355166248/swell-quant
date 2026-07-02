#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from swell_quant.core.config import Settings, build_settings_preflight


def main() -> int:
    try:
        settings = Settings.from_env()
    except ValueError as error:
        payload = {
            "status": "failed",
            "passed": False,
            "error": "invalid_settings",
            "message": str(error),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    preflight = build_settings_preflight(settings)
    print(json.dumps(preflight, ensure_ascii=False, indent=2))
    if preflight["failed_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
