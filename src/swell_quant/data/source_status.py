from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from swell_quant.data.sample_data import DATA_SOURCE_METADATA_FILENAME


def default_data_source_metadata_path(data_dir: Path) -> Path:
    return data_dir / "raw" / DATA_SOURCE_METADATA_FILENAME


def build_data_source_status(metadata_path: Path) -> dict[str, Any]:
    if not metadata_path.exists():
        return {
            "status": "missing",
            "passed": False,
            "path": str(metadata_path),
            "message": "run `python3 scripts/run_pipeline.py` first",
            "warning_count": 0,
            "warnings": [],
            "failed_count": 1,
            "failures": ["data_source.json missing"],
            "disclaimer": "仅用于研究，不构成投资建议",
        }

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return build_data_source_status_from_metadata(metadata, metadata_path)


def build_data_source_status_from_metadata(
    metadata: dict[str, Any], metadata_path: Path | None = None
) -> dict[str, Any]:
    selected_symbol_count = int(metadata.get("selected_symbol_count") or 0)
    succeeded_symbol_count = int(metadata.get("succeeded_symbol_count") or selected_symbol_count)
    failed_symbol_count = int(metadata.get("failed_symbol_count") or 0)
    max_symbols = metadata.get("max_symbols")
    warnings: list[str] = []
    failures: list[str] = []

    if selected_symbol_count <= 0:
        failures.append("selected_symbol_count must be greater than 0")
    if succeeded_symbol_count <= 0:
        failures.append("succeeded_symbol_count must be greater than 0")
    # AKShare 单标的临时失败很常见，v1 允许用成功标的继续研究，但必须在门禁和报告里显式暴露。
    if failed_symbol_count > 0:
        warnings.append(f"{failed_symbol_count} symbols failed during collection")
    if max_symbols is not None:
        warnings.append(f"AKSHARE_MAX_SYMBOLS trial cap is active: {max_symbols}")

    status = "failed" if failures else "warning" if warnings else "passed"
    return {
        "status": status,
        "passed": not failures,
        "path": str(metadata_path) if metadata_path is not None else None,
        "data_source": metadata.get("data_source"),
        "market": metadata.get("market"),
        "universe_mode": metadata.get("universe_mode"),
        "universe_name": metadata.get("universe_name"),
        "benchmark": metadata.get("benchmark"),
        "benchmark_name": metadata.get("benchmark_name"),
        "selected_symbol_count": selected_symbol_count,
        "resolved_symbol_count": metadata.get("resolved_symbol_count"),
        "succeeded_symbol_count": succeeded_symbol_count,
        "failed_symbol_count": failed_symbol_count,
        "max_symbols": max_symbols,
        "failed_symbols": metadata.get("failed_symbols") or [],
        "warning_count": len(warnings),
        "warnings": warnings,
        "failed_count": len(failures),
        "failures": failures,
        "updated_at": metadata.get("updated_at"),
        "disclaimer": "仅用于研究，不构成投资建议",
    }
