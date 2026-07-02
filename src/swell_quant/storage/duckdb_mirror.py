from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
