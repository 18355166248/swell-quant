from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


PIPELINE_DUCKDB_TABLES = (
    "raw_prices",
    "feature_rows",
    "label_rows",
    "latest_predictions",
    "historical_predictions",
)

PIPELINE_CSV_ARTIFACTS = {
    "raw_prices": ("raw", "sample_prices.csv"),
    "feature_rows": ("processed", "sample_features.csv"),
    "label_rows": ("processed", "sample_labels.csv"),
    "latest_predictions": ("processed", "latest_predictions.csv"),
    "historical_predictions": ("processed", "historical_predictions.csv"),
}


@dataclass(frozen=True)
class DuckDBTableMirror:
    table_name: str
    csv_path: Path
    row_count: int


@dataclass(frozen=True)
class DuckDBMirrorResult:
    duckdb_path: Path
    tables: list[DuckDBTableMirror]

    @property
    def total_rows(self) -> int:
        return sum(table.row_count for table in self.tables)


def mirror_pipeline_csvs_to_duckdb(data_dir: Path, duckdb_path: Path) -> DuckDBMirrorResult:
    """Mirror pipeline CSV artifacts into the local DuckDB file."""

    import duckdb

    artifacts = _pipeline_csv_paths(data_dir)
    missing = [str(path) for path in artifacts.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing pipeline csv artifacts: {', '.join(missing)}")

    duckdb_path = duckdb_path.expanduser()
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)

    mirrored: list[DuckDBTableMirror] = []
    with duckdb.connect(str(duckdb_path)) as connection:
        for table_name, csv_path in artifacts.items():
            # v1 使用单文件单写入者模式。这里采用整表替换，避免重复追加造成历史样例数据膨胀。
            connection.execute(
                f"""
                CREATE OR REPLACE TABLE {table_name} AS
                SELECT * FROM read_csv_auto(?, header = true)
                """,
                [str(csv_path)],
            )
            row_count = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            mirrored.append(
                DuckDBTableMirror(
                    table_name=table_name,
                    csv_path=csv_path,
                    row_count=int(row_count),
                )
            )

    return DuckDBMirrorResult(duckdb_path=duckdb_path, tables=mirrored)


def inspect_duckdb_mirror(duckdb_path: Path, data_dir: Path | None = None) -> dict[str, object]:
    import duckdb

    duckdb_path = duckdb_path.expanduser()
    if not duckdb_path.exists():
        return {
            "exists": False,
            "path": str(duckdb_path),
            "status": "missing",
            "tables": [],
            "missing_tables": list(PIPELINE_DUCKDB_TABLES),
            "inconsistent_tables": [],
            "total_rows": 0,
        }

    source_paths = _pipeline_csv_paths(data_dir) if data_dir is not None else {}
    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        existing_tables = {
            row[0] for row in connection.execute("SHOW TABLES").fetchall()
        }
        tables: list[dict[str, object]] = []
        for table_name in PIPELINE_DUCKDB_TABLES:
            exists = table_name in existing_tables
            row_count = None
            source_path = source_paths.get(table_name)
            source_exists = source_path.exists() if source_path is not None else None
            source_row_count = _count_csv_rows(source_path) if source_path is not None and source_path.exists() else None
            if exists:
                # 表名来自固定白名单，只做只读 COUNT，避免状态接口承担任何写入副作用。
                row_count = int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
            # CSV 和 DuckDB 行数一致是镜像是否过期的最小验收条件，后续再补字段 schema 校验。
            row_count_matches = (
                None
                if source_row_count is None or row_count is None
                else source_row_count == row_count
            )
            tables.append(
                {
                    "name": table_name,
                    "exists": exists,
                    "row_count": row_count,
                    "source_path": None if source_path is None else str(source_path),
                    "source_exists": source_exists,
                    "source_row_count": source_row_count,
                    "row_count_matches": row_count_matches,
                }
            )

    missing_tables = [table["name"] for table in tables if not table["exists"]]
    inconsistent_tables = [
        table["name"] for table in tables if table["row_count_matches"] is False
    ]
    total_rows = sum(int(table["row_count"] or 0) for table in tables)
    status = "healthy"
    if missing_tables:
        status = "incomplete"
    elif inconsistent_tables:
        status = "inconsistent"
    return {
        "exists": True,
        "path": str(duckdb_path),
        "status": status,
        "file_size_bytes": duckdb_path.stat().st_size,
        "tables": tables,
        "missing_tables": missing_tables,
        "inconsistent_tables": inconsistent_tables,
        "total_rows": total_rows,
    }


def _pipeline_csv_paths(data_dir: Path) -> dict[str, Path]:
    return {
        table_name: data_dir / parts[0] / parts[1]
        for table_name, parts in PIPELINE_CSV_ARTIFACTS.items()
    }


def _count_csv_rows(path: Path) -> int:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)
        return sum(1 for _ in reader)
