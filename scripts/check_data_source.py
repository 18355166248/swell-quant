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
from swell_quant.data.source_status import (
    build_data_source_status,
    default_data_source_metadata_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Swell Quant data acquisition metadata.")
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable data source JSON."
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    payload = build_data_source_status(default_data_source_metadata_path(settings.data_dir))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"data_source_status={payload.get('status')}")
        print(f"passed={str(bool(payload.get('passed'))).lower()}")
        print(f"data_source={payload.get('data_source') or '-'}")
        print(f"universe_mode={payload.get('universe_mode') or '-'}")
        print(f"selected_symbol_count={payload.get('selected_symbol_count') or 0}")
        print(f"succeeded_symbol_count={payload.get('succeeded_symbol_count') or 0}")
        print(f"failed_symbol_count={payload.get('failed_symbol_count') or 0}")
        if payload.get("max_symbols") is not None:
            print(f"max_symbols={payload.get('max_symbols')}")
        for warning in payload.get("warnings", []):
            print(f"warning={warning}")
        for failure in payload.get("failures", []):
            print(f"failure={failure}")

    return 0 if payload.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
