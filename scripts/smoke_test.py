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

from swell_quant.api.local_server import load_acceptance_artifact, load_duckdb_storage_artifact
from swell_quant.core.config import Settings
from swell_quant.core.pipeline import StepStatus

import run_pipeline as pipeline_runner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local end-to-end research smoke test.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable smoke test JSON.")
    args = parser.parse_args()

    settings = Settings.from_env()
    results, manifest_path, status_path = pipeline_runner.run_pipeline(settings)
    pipeline_failed = any(result.status == StepStatus.FAILED for result in results)
    storage = load_duckdb_storage_artifact(settings.duckdb_path, settings.data_dir)
    acceptance = (
        load_acceptance_artifact(status_path)
        if status_path is not None
        else {
            "status": "missing",
            "passed": False,
            "checks": [],
            "message": "pipeline did not write research_status.json",
        }
    )
    payload = {
        "status": "passed"
        if not pipeline_failed and storage["status"] == "healthy" and acceptance.get("passed") is True
        else "failed",
        "pipeline": {
            "manifest_path": str(manifest_path),
            "status_path": None if status_path is None else str(status_path),
            "failed": pipeline_failed,
            "steps": [
                {
                    "name": result.name,
                    "status": result.status.value,
                    "message": result.message,
                }
                for result in results
            ],
        },
        "storage": storage,
        "acceptance": acceptance,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"smoke_status={payload['status']}")
        print(f"pipeline_failed={str(pipeline_failed).lower()}")
        print(f"duckdb_status={storage['status']}")
        print(f"acceptance_status={acceptance.get('status')}")
        for result in results:
            print(f"step={result.name} status={result.status.value}")

    # 这个入口作为本地端到端验收门禁，必须同时满足 pipeline、存储和研究验收三层状态。
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
