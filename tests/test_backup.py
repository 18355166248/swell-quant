from pathlib import Path

from swell_quant.storage.duckdb_backup import backup_duckdb


def test_backup_duckdb_returns_none_when_source_missing(tmp_path: Path) -> None:
    result = backup_duckdb(tmp_path / "missing.duckdb", tmp_path / "backups")

    assert result is None


def test_backup_duckdb_copies_existing_file(tmp_path: Path) -> None:
    db_path = tmp_path / "swell_quant.duckdb"
    db_path.write_bytes(b"duckdb-content")

    backup_path = backup_duckdb(db_path, tmp_path / "backups")

    assert backup_path is not None
    assert backup_path.exists()
    assert backup_path.read_bytes() == b"duckdb-content"
    assert backup_path.name.startswith("swell_quant.")
