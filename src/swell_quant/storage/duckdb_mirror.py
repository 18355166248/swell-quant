from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PIPELINE_DUCKDB_TABLES = (
    "raw_prices",
    "feature_rows",
    "label_rows",
    "latest_predictions",
    "historical_predictions",
)


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

    artifacts = {
        "raw_prices": data_dir / "raw" / "sample_prices.csv",
        "feature_rows": data_dir / "processed" / "sample_features.csv",
        "label_rows": data_dir / "processed" / "sample_labels.csv",
        "latest_predictions": data_dir / "processed" / "latest_predictions.csv",
        "historical_predictions": data_dir / "processed" / "historical_predictions.csv",
    }
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


def inspect_duckdb_mirror(duckdb_path: Path) -> dict[str, object]:
    import duckdb

    duckdb_path = duckdb_path.expanduser()
    if not duckdb_path.exists():
        return {
            "exists": False,
            "path": str(duckdb_path),
            "status": "missing",
            "tables": [],
            "missing_tables": list(PIPELINE_DUCKDB_TABLES),
            "total_rows": 0,
        }

    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        existing_tables = {
            row[0] for row in connection.execute("SHOW TABLES").fetchall()
        }
        tables: list[dict[str, object]] = []
        for table_name in PIPELINE_DUCKDB_TABLES:
            exists = table_name in existing_tables
            row_count = None
            if exists:
                # 表名来自固定白名单，只做只读 COUNT，避免状态接口承担任何写入副作用。
                row_count = int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
            tables.append({"name": table_name, "exists": exists, "row_count": row_count})

    missing_tables = [table["name"] for table in tables if not table["exists"]]
    total_rows = sum(int(table["row_count"] or 0) for table in tables)
    return {
        "exists": True,
        "path": str(duckdb_path),
        "status": "healthy" if not missing_tables else "incomplete",
        "file_size_bytes": duckdb_path.stat().st_size,
        "tables": tables,
        "missing_tables": missing_tables,
        "total_rows": total_rows,
    }
