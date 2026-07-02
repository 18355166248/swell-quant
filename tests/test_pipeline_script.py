import os
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
    assert "success labels" in result.stdout
    assert "success train" in result.stdout
    assert "success backtest" in result.stdout
    assert (tmp_path / "data" / "raw" / "sample_prices.csv").exists()
    assert (tmp_path / "data" / "processed" / "sample_features.csv").exists()
    assert (tmp_path / "data" / "processed" / "sample_labels.csv").exists()
    assert (tmp_path / "data" / "models" / "baseline-rule-v1.json").exists()
    assert (tmp_path / "data" / "processed" / "latest_predictions.csv").exists()
    assert (tmp_path / "data" / "processed" / "historical_predictions.csv").exists()
    assert (tmp_path / "data" / "reports" / "sample_backtest.json").exists()
