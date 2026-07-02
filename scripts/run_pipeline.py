#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from swell_quant.core.config import Settings
from swell_quant.core.pipeline import PipelineStep, StepStatus, run_steps
from swell_quant.storage.duckdb_backup import backup_duckdb


def prepare_directories(settings: Settings) -> str:
    settings.ensure_directories()
    return f"prepared data directories under {settings.data_dir}"


def run_data_update_stub(settings: Settings) -> str:
    settings.ensure_directories()
    backup_path = backup_duckdb(settings.duckdb_path, settings.data_dir / "processed" / "duckdb_backups")
    backup_message = f"backup={backup_path}" if backup_path else "backup=skipped_missing_duckdb"
    # 阶段 1 先把 pipeline 入口和备份钩子跑通，真实 AKShare 采集在数据层实现后接入。
    return f"data update stub completed ({backup_message})"


def build_steps(settings: Settings) -> list[PipelineStep]:
    return [
        PipelineStep("prepare_directories", lambda: prepare_directories(settings)),
        PipelineStep("data_update", lambda: run_data_update_stub(settings)),
        PipelineStep("features", lambda: "feature pipeline not implemented", enabled=False),
        PipelineStep("labels", lambda: "label pipeline not implemented", enabled=False),
        PipelineStep("train", lambda: "training pipeline not implemented", enabled=False),
        PipelineStep("backtest", lambda: "backtest pipeline not implemented", enabled=False),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Swell Quant offline research pipeline.")
    parser.add_argument("--fail-on-skipped", action="store_true", help="Return non-zero if any step is skipped.")
    args = parser.parse_args()

    settings = Settings.from_env()
    results = run_steps(build_steps(settings))

    for result in results:
        print(f"{result.status.value:7s} {result.name}: {result.message}")

    if any(result.status == StepStatus.FAILED for result in results):
        return 1
    if args.fail_on_skipped and any(result.status == StepStatus.SKIPPED for result in results):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
