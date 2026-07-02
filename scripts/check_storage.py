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

from swell_quant.api.local_server import load_duckdb_storage_artifact
from swell_quant.core.config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local DuckDB mirror consistency.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON payload.")
    args = parser.parse_args()

    settings = Settings.from_env()
    payload = load_duckdb_storage_artifact(settings.duckdb_path, settings.data_dir)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"duckdb_status={payload['status']}")
        print(f"path={payload['path']}")
        print(f"total_rows={payload['total_rows']}")
        for table in payload["tables"]:
            match = table.get("row_count_matches")
            match_text = "unknown" if match is None else str(match).lower()
            print(
                f"table={table['name']} "
                f"duckdb_rows={table.get('row_count')} "
                f"csv_rows={table.get('source_row_count')} "
                f"matches={match_text}"
            )

    # 这个脚本是无页面质量门禁入口，非 healthy 必须非零退出，方便 CI 或本地一条命令拦截过期镜像。
    return 0 if payload["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
