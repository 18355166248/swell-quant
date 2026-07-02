import os
import json
import subprocess
import sys
from pathlib import Path


def test_run_pipeline_writes_sample_outputs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "DUCKDB_PATH": str(tmp_path / "data" / "duckdb" / "swell_quant.duckdb"),
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_pipeline.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "success features" in result.stdout
    assert "success data_quality" in result.stdout
    assert "success labels" in result.stdout
    assert "success train" in result.stdout
    assert "success backtest" in result.stdout
    assert "success duckdb_mirror" in result.stdout
    assert "success report" in result.stdout
    assert "status" in result.stdout
    assert (tmp_path / "data" / "raw" / "sample_prices.csv").exists()
    assert (tmp_path / "data" / "processed" / "data_quality.json").exists()
    assert (tmp_path / "data" / "processed" / "sample_features.csv").exists()
    assert (tmp_path / "data" / "processed" / "sample_labels.csv").exists()
    assert (tmp_path / "data" / "models" / "baseline-rule-v1.json").exists()
    assert (tmp_path / "data" / "processed" / "latest_predictions.csv").exists()
    assert (tmp_path / "data" / "processed" / "historical_predictions.csv").exists()
    assert (tmp_path / "data" / "duckdb" / "swell_quant.duckdb").exists()
    assert (tmp_path / "data" / "reports" / "sample_backtest.json").exists()
    assert (tmp_path / "data" / "reports" / "sample_research_summary.md").exists()
    status_path = tmp_path / "data" / "reports" / "research_status.json"
    assert status_path.exists()
    manifest_path = tmp_path / "data" / "reports" / "pipeline_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert status["pipeline"]["status"] == "success"
    assert status["data_quality"]["passed"] is True
    assert status["predictions"]["count"] == 3
    assert [step["name"] for step in manifest["steps"]] == [
        "prepare_directories",
        "data_update",
        "data_quality",
        "features",
        "labels",
        "train",
        "backtest",
        "duckdb_mirror",
        "report",
    ]

    check_result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_storage.py"), "--json"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    storage = json.loads(check_result.stdout)
    assert check_result.returncode == 0
    assert storage["status"] == "healthy"
    assert storage["inconsistent_tables"] == []


def test_check_storage_returns_nonzero_for_missing_duckdb(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "DUCKDB_PATH": str(tmp_path / "data" / "duckdb" / "missing.duckdb"),
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_storage.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "duckdb_status=missing" in result.stdout
