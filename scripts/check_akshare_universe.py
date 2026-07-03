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
from swell_quant.data.akshare_data import AkshareDependencyError
from swell_quant.data.universe_check import build_akshare_universe_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AKShare universe resolution.")
    parser.add_argument("--json", action="store_true", help="print structured JSON")
    args = parser.parse_args()

    try:
        settings = Settings.from_env()
        payload = build_akshare_universe_payload(settings)
    except ValueError as error:
        payload = {
            "status": "failed",
            "passed": False,
            "error": "invalid_settings",
            "message": str(error),
        }
        return _emit(payload, as_json=args.json, exit_code=2)
    except (AkshareDependencyError, AttributeError) as error:
        payload = {
            "status": "failed",
            "passed": False,
            "error": "akshare_universe_unavailable",
            "message": str(error),
        }
        return _emit(payload, as_json=args.json, exit_code=1)

    return _emit(payload, as_json=args.json, exit_code=0 if payload["passed"] else 1)


def _emit(payload: dict[str, object], *, as_json: bool, exit_code: int) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"akshare_universe_status={payload['status']}")
        print(f"passed={str(payload['passed']).lower()}")
        if "error" in payload:
            print(f"error={payload['error']}")
            print(f"message={payload['message']}")
        else:
            print(f"data_source={payload['data_source']}")
            print(f"universe_mode={payload['universe_mode']}")
            print(f"symbol_count={payload['symbol_count']}")
            print(f"minimum_expected_count={payload['minimum_expected_count']}")
            print(f"symbols_sample={','.join(payload['symbols_sample'])}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
