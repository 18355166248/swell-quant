from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


def backup_duckdb(duckdb_path: Path, backup_dir: Path) -> Path | None:
    """Copy a DuckDB file to a timestamped backup path.

    Returns None when the database file does not exist yet. Stage 1 creates the
    backup hook before real ingestion writes the database, so the missing-file
    path is an expected no-op instead of a hard failure.
    """

    source = duckdb_path.expanduser()
    if not source.exists():
        return None

    backup_dir = backup_dir.expanduser()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"{source.stem}.{timestamp}{source.suffix}"

    # DuckDB v1 采用单文件本地模式，任务结束后复制完整文件是最低成本的恢复点。
    shutil.copy2(source, target)
    return target
