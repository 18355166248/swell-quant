import os
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from scripts import run_akshare_trial as akshare_trial_script
from scripts.run_pipeline import limit_akshare_symbols, run_data_update
from scripts.run_akshare_trial import TrialStep, write_trial_artifacts
from swell_quant.core.config import Settings
from swell_quant.data.sample_data import (
    build_price_data_metadata,
    generate_sample_bars,
    write_price_bars_csv,
    write_price_data_metadata,
)
from swell_quant.data.universe_check import build_akshare_universe_payload


class FakeUniverseFrame:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def to_dict(self, orient: str) -> list[dict]:
        assert orient == "records"
        return self.rows


class SmallFakeUniverseProvider:
    def index_stock_cons(self, symbol: str) -> FakeUniverseFrame:
        rows_by_symbol = {
            "000300": [{"品种代码": "600000", "交易所": "SH"}],
            "000905": [{"品种代码": "000001", "交易所": "SZ"}],
        }
        return FakeUniverseFrame(rows_by_symbol[symbol])


def test_limit_akshare_symbols_only_applies_explicit_trial_cap() -> None:
    symbols = ("000001.SZ", "000002.SZ", "600000.SH")

    assert limit_akshare_symbols(symbols, None) == symbols
    assert limit_akshare_symbols(symbols, 2) == ("000001.SZ", "000002.SZ")


def test_run_data_update_reuses_usable_akshare_cache_when_live_fetch_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    raw_dir = data_dir / "raw"
    symbols = ("000001.SZ", "000002.SZ", "600000.SH")
    write_price_bars_csv(raw_dir / "sample_prices.csv", generate_sample_bars(days=8))
    write_price_data_metadata(
        raw_dir / "data_source.json",
        build_price_data_metadata(
            data_source="akshare",
            symbols=symbols,
            start_date="20240102",
            end_date="20240109",
            benchmark="sh000906",
            universe_mode="manual",
            succeeded_symbols=symbols,
        ),
    )
    settings = Settings(
        data_dir=data_dir,
        duckdb_path=data_dir / "duckdb" / "swell_quant.duckdb",
        data_source="akshare",
        akshare_universe_mode="manual",
        akshare_symbols=symbols,
        akshare_start_date="20240102",
        akshare_end_date="20240109",
    )
    monkeypatch.setattr(
        "scripts.run_pipeline.resolve_akshare_symbol_metadata",
        lambda **_kwargs: {symbol: symbol for symbol in symbols},
    )
    monkeypatch.setattr(
        "scripts.run_pipeline.collect_akshare_price_bars",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("live source unavailable")),
    )

    message = run_data_update(settings)
    metadata = json.loads((raw_dir / "data_source.json").read_text(encoding="utf-8"))

    assert "cache_fallback=true" in message
    assert metadata["data_source"] == "akshare"
    assert metadata["update_mode"] == "cached_fallback"
    assert metadata["fallback_reason"] == "live source unavailable"
    assert metadata["succeeded_symbol_count"] == 3


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
        "fund_research",
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

    data_source_result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_data_source.py"), "--json"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    data_source = json.loads(data_source_result.stdout)
    assert data_source_result.returncode == 0
    assert data_source["status"] == "passed"
    assert data_source["selected_symbol_count"] == 3
    assert data_source["failed_symbol_count"] == 0

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


def test_check_akshare_universe_reports_manual_symbols(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "AKSHARE_UNIVERSE_MODE": "manual",
        "AKSHARE_SYMBOLS": "000001.SZ,600000.SH",
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_akshare_universe.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "akshare_universe_status=passed" in result.stdout
    assert "universe_mode=manual" in result.stdout
    assert "symbol_count=2" in result.stdout


def test_check_akshare_universe_json_reports_research_disclaimer(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "AKSHARE_UNIVERSE_MODE": "manual",
        "AKSHARE_SYMBOLS": "000001.SZ",
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_akshare_universe.py"), "--json"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["symbol_count"] == 1
    assert payload["disclaimer"] == "仅用于研究，不构成投资建议"


def test_check_akshare_universe_returns_nonzero_for_invalid_settings(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
        "AKSHARE_UNIVERSE_MODE": "manual",
        "AKSHARE_SYMBOLS": "",
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_akshare_universe.py"), "--json"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["error"] == "invalid_settings"
    assert "manual mode" in payload["message"]


def test_akshare_universe_payload_fails_when_csi800_count_is_too_small() -> None:
    settings = Settings(
        data_dir=Path("./data"),
        duckdb_path=Path("./data/duckdb/swell_quant.duckdb"),
        data_source="akshare",
        akshare_universe_mode="csi800",
        akshare_symbols=(),
    )

    payload = build_akshare_universe_payload(settings, provider=SmallFakeUniverseProvider())

    assert payload["status"] == "failed"
    assert payload["passed"] is False
    assert payload["symbol_count"] == 2
    assert payload["minimum_expected_count"] == 700


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
    assert "next_action_1=阶段 1：数据采集与存储 缺少证据" in result.stdout
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
    assert payload["next_actions"]
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


def test_check_data_source_returns_nonzero_before_pipeline_runs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_data_source.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "data_source_status=missing" in result.stdout


def test_run_akshare_trial_dry_run_reports_planned_steps(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
    }

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "run_akshare_trial.py"),
            "--dry-run",
            "--json",
            "--max-symbols",
            "5",
            "--start-date",
            "20240102",
            "--end-date",
            "20240105",
        ],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["status"] == "dry_run"
    assert payload["passed"] is True
    assert payload["trial_kind"] == "dry_run"
    assert payload["real_data_verified"] is False
    assert payload["artifact_path"] == str(tmp_path / "data" / "reports" / "akshare_trial_run.json")
    assert payload["started_at"]
    assert payload["ended_at"]
    assert payload["env"]["DATA_SOURCE"] == "akshare"
    assert payload["env"]["AKSHARE_UNIVERSE_MODE"] == "csi800"
    assert payload["env"]["AKSHARE_MAX_SYMBOLS"] == "5"
    assert [step["name"] for step in payload["steps"]] == [
        "config",
        "akshare_universe",
        "pipeline",
        "data_source",
        "acceptance",
        "progress",
    ]
    artifact = json.loads(
        (tmp_path / "data" / "reports" / "akshare_trial_run.json").read_text(encoding="utf-8")
    )
    assert artifact["status"] == "dry_run"
    assert artifact["steps"][0]["name"] == "config"

    check_result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_akshare_trial.py"), "--json"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    trial_status = json.loads(check_result.stdout)
    assert check_result.returncode == 0
    assert trial_status["status"] == "dry_run"
    assert trial_status["passed"] is True
    assert trial_status["trial_kind"] == "dry_run"
    assert trial_status["real_data_verified"] is False
    assert trial_status["step_count"] == 6
    assert trial_status["failed_step"] is None


def test_akshare_trial_dry_run_entrypoint_writes_summary(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_akshare_trial.py"), "--dry-run"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "akshare_trial_status=dry_run" in result.stdout
    assert (tmp_path / "data" / "reports" / "akshare_trial_run.json").exists()


def test_write_trial_artifacts_preserves_last_passed_summary(tmp_path: Path) -> None:
    latest_path = tmp_path / "data" / "reports" / "akshare_trial_run.json"
    payload = {
        "status": "passed",
        "passed": True,
        "real_data_verified": True,
        "artifact_path": str(latest_path),
        "steps": [],
    }

    write_trial_artifacts(latest_path, payload)

    last_passed_path = tmp_path / "data" / "reports" / "akshare_trial_last_passed.json"
    assert latest_path.exists()
    assert last_passed_path.exists()
    assert json.loads(last_passed_path.read_text(encoding="utf-8"))["status"] == "passed"

    failed_payload = {
        "status": "failed",
        "passed": False,
        "real_data_verified": False,
        "artifact_path": str(latest_path),
        "steps": [{"name": "pipeline", "status": "failed"}],
    }
    write_trial_artifacts(latest_path, failed_payload)

    assert json.loads(latest_path.read_text(encoding="utf-8"))["status"] == "failed"
    assert json.loads(last_passed_path.read_text(encoding="utf-8"))["status"] == "passed"


def test_run_akshare_trial_failed_attempt_reports_real_data_kind(monkeypatch) -> None:
    args = SimpleNamespace(
        dry_run=False,
        universe_mode="csi800",
        max_symbols=1,
        start_date="20240102",
        end_date="20240131",
        benchmark_symbol="sh000906",
    )
    monkeypatch.setattr(
        akshare_trial_script,
        "build_trial_steps",
        lambda _args: [TrialStep("failing_step", (sys.executable, "-c", "raise SystemExit(1)"))],
    )

    payload = akshare_trial_script.run_trial(args)

    assert payload["status"] == "failed"
    assert payload["trial_kind"] == "real_data"
    assert payload["real_data_verified"] is False


def test_run_akshare_trial_rejects_invalid_symbol_cap(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
    }

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "run_akshare_trial.py"),
            "--dry-run",
            "--max-symbols",
            "0",
        ],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--max-symbols must be greater than 0" in result.stderr


def test_check_akshare_trial_returns_nonzero_before_trial_runs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
    }

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_akshare_trial.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "akshare_trial_status=missing" in result.stdout


def test_check_akshare_trial_summarizes_failed_step(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"),
    }
    trial_path = tmp_path / "data" / "reports" / "akshare_trial_run.json"
    trial_path.parent.mkdir(parents=True, exist_ok=True)
    trial_path.write_text(
        json.dumps(
            {
                "status": "failed",
                "passed": False,
                "trial_kind": "real_data",
                "real_data_verified": False,
                "steps": [
                    {"name": "pipeline", "status": "passed", "stdout": "ok"},
                    {
                        "name": "data_source",
                        "status": "failed",
                        "stdout": (
                            "data_source_status=failed\n"
                            "failure=data source quality is poor: success_rate=70.00%\n"
                        ),
                        "stderr": "",
                    },
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_akshare_trial.py"), "--json"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["failed_step"] == "data_source"
    assert payload["failed_step_summary"]["name"] == "data_source"
    assert "success_rate=70.00%" in payload["failed_step_summary"]["stdout_tail"]
