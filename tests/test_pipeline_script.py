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
    assert (tmp_path / "data" / "raw" / "data_source.json").exists()
    assert (tmp_path / "data" / "processed" / "data_quality.json").exists()
    assert (tmp_path / "data" / "processed" / "sample_features.csv").exists()
    assert (tmp_path / "data" / "processed" / "sample_labels.csv").exists()
    assert (tmp_path / "data" / "processed" / "training_samples.csv").exists()
    assert (tmp_path / "data" / "models" / "baseline-rule-v1.json").exists()
    assert (tmp_path / "data" / "models" / "latest_model.json").exists()
    assert (tmp_path / "data" / "processed" / "latest_predictions.csv").exists()
    assert (tmp_path / "data" / "processed" / "historical_predictions.csv").exists()
    assert (tmp_path / "data" / "duckdb" / "swell_quant.duckdb").exists()
    assert (tmp_path / "data" / "reports" / "sample_backtest.json").exists()
    assert (tmp_path / "data" / "reports" / "sample_research_summary.md").exists()
    assert (tmp_path / "data" / "reports" / "sample_research_summary.json").exists()
    assert (tmp_path / "data" / "reports" / "sample_ai_research_summary.md").exists()
    assert (tmp_path / "data" / "reports" / "sample_ai_research_summary.json").exists()
    status_path = tmp_path / "data" / "reports" / "research_status.json"
    assert status_path.exists()
    manifest_path = tmp_path / "data" / "reports" / "pipeline_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert status["pipeline"]["status"] == "success"
    assert status["acceptance"]["status"] == "passed"
    assert status["data_quality"]["passed"] is True
    assert status["training_samples"]["status"] == "ready"
    assert status["training_samples"]["split_counts"]["train"] > 0
    assert status["training_samples"]["split_counts"]["validation"] > 0
    assert status["training_samples"]["split_counts"]["test"] > 0
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
    assert storage["schema_mismatch_tables"] == []

    acceptance_result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_acceptance.py"), "--json"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    acceptance = json.loads(acceptance_result.stdout)
    assert acceptance_result.returncode == 0
    assert acceptance["status"] == "passed"
    assert acceptance["failed_count"] == 0

    smoke_result = subprocess.run(
        [sys.executable, str(root / "scripts" / "smoke_test.py"), "--json"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    smoke = json.loads(smoke_result.stdout)
    assert smoke_result.returncode == 0
    assert smoke["status"] == "passed"
    assert smoke["pipeline"]["failed"] is False
    assert smoke["storage"]["status"] == "healthy"
    assert smoke["acceptance"]["status"] == "passed"


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


def test_check_config_reports_preflight_status(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "DUCKDB_PATH": str(tmp_path / "data" / "duckdb" / "swell_quant.duckdb"),
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_config.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["failed_count"] == 0
    assert any(check["key"] == "data_source" for check in payload["checks"])


def test_check_config_returns_nonzero_for_invalid_settings(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "AKSHARE_SYMBOLS": "000001",
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_config.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["status"] == "failed"
    assert payload["error"] == "invalid_settings"
    assert "AKSHARE_SYMBOLS" in payload["message"]


def test_check_progress_reports_current_stage(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "DUCKDB_PATH": str(tmp_path / "data" / "duckdb" / "swell_quant.duckdb"),
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_progress.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "progress_status=in_progress" in result.stdout
    assert "current_stage=阶段 1：数据采集与存储" in result.stdout
    assert "stage=stage_0 status=complete" in result.stdout


def test_check_progress_json_reports_stage_evidence(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "DUCKDB_PATH": str(tmp_path / "data" / "duckdb" / "swell_quant.duckdb"),
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_progress.py"), "--json"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["stage_count"] == 8
    assert payload["current_stage"]["id"] == "stage_1"
    assert payload["stages"][0]["id"] == "stage_0"
    assert payload["stages"][0]["status"] == "complete"


def test_check_acceptance_returns_nonzero_before_pipeline_runs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_acceptance.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "acceptance_status=missing" in result.stdout
