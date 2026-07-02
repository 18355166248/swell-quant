from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swell_quant.data.quality import DataQualityReport
from swell_quant.research.backtest import BacktestResult
from swell_quant.research.modeling import ModelMetadata, PredictionRow


def build_research_status(
    quality: DataQualityReport,
    metadata: ModelMetadata,
    predictions: list[PredictionRow],
    backtest: BacktestResult,
    pipeline_manifest: dict[str, Any],
    storage_status: dict[str, Any] | None = None,
    artifact_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    top_predictions = sorted(predictions, key=lambda row: row.rank)
    resolved_artifact_paths = artifact_paths or default_artifact_paths(Path("data"))
    artifact_status = build_artifact_status(resolved_artifact_paths)
    gates = build_acceptance_gates(
        quality=quality,
        predictions=top_predictions,
        backtest=backtest,
        pipeline_manifest=pipeline_manifest,
        storage_status=storage_status,
        artifact_status=artifact_status,
    )

    # 状态快照面向 CLI/API/页面复用，只聚合结构化产物，不重新计算研究结果。
    return {
        "disclaimer": "仅用于研究，不构成投资建议",
        "acceptance": gates,
        "pipeline": {
            "status": pipeline_manifest.get("status"),
            "started_at": pipeline_manifest.get("started_at"),
            "ended_at": pipeline_manifest.get("ended_at"),
            "duration_seconds": pipeline_manifest.get("duration_seconds"),
            "step_count": pipeline_manifest.get("step_count"),
        },
        "data_quality": {
            "passed": quality.passed,
            "row_count": quality.row_count,
            "symbol_count": quality.symbol_count,
            "start_date": quality.start_date,
            "end_date": quality.end_date,
            "issue_count": quality.issue_count,
        },
        "model": {
            "model_version": metadata.model_version,
            "model_type": metadata.model_type,
            "train_start": metadata.train_start,
            "train_end": metadata.train_end,
            "prediction_date": metadata.prediction_date,
            "feature_names": metadata.feature_names,
            "label_gap_days": metadata.label_gap_days,
            "evaluation_status": metadata.evaluation_status,
            "evaluation_train_start": metadata.evaluation_train_start,
            "evaluation_train_end": metadata.evaluation_train_end,
            "validation_start": metadata.validation_start,
            "validation_end": metadata.validation_end,
            "test_start": metadata.test_start,
            "test_end": metadata.test_end,
            "metrics": metadata.metrics or {},
        },
        "predictions": {
            "count": len(top_predictions),
            "top": [
                {
                    "rank": row.rank,
                    "symbol": row.symbol,
                    "date": row.trade_date.isoformat(),
                    "score": row.score,
                    "momentum_5d": row.momentum_5d,
                    "return_1d": row.return_1d,
                }
                for row in top_predictions
            ],
        },
        "backtest": {
            "backtest_id": backtest.backtest_id,
            "top_n": backtest.top_n,
            "trade_count": backtest.trade_count,
            "fee_rate": backtest.fee_rate,
            "slippage_rate": backtest.slippage_rate,
            "start_date": backtest.start_date,
            "end_date": backtest.end_date,
            "cumulative_return": backtest.cumulative_return,
            "annualized_return": backtest.annualized_return,
            "benchmark_return": backtest.benchmark_return,
            "excess_return": backtest.excess_return,
            "max_drawdown": backtest.max_drawdown,
            "sharpe_ratio": backtest.sharpe_ratio,
            "win_rate": backtest.win_rate,
            "turnover_rate": backtest.turnover_rate,
            "disclaimer": backtest.disclaimer,
        },
        "artifacts": {key: str(path) for key, path in resolved_artifact_paths.items()},
        "artifact_status": artifact_status,
    }


def default_artifact_paths(data_dir: Path) -> dict[str, Path]:
    return {
        "data_quality": data_dir / "processed" / "data_quality.json",
        "model": data_dir / "models" / "baseline-rule-v1.json",
        "latest_predictions": data_dir / "processed" / "latest_predictions.csv",
        "historical_predictions": data_dir / "processed" / "historical_predictions.csv",
        "duckdb": data_dir / "duckdb" / "swell_quant.duckdb",
        "backtest": data_dir / "reports" / "sample_backtest.json",
        "summary": data_dir / "reports" / "sample_research_summary.md",
        "pipeline_run": data_dir / "reports" / "pipeline_run.json",
    }


def build_artifact_status(artifact_paths: dict[str, Path]) -> dict[str, Any]:
    artifacts = [_build_artifact_entry(name, path) for name, path in artifact_paths.items()]
    missing = [artifact["name"] for artifact in artifacts if not artifact["exists"]]
    return {
        "status": "complete" if not missing else "missing",
        "missing": missing,
        "artifacts": artifacts,
    }


def _build_artifact_entry(name: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    # 产物元数据用于验收页和脚本排查“文件存在但明显过旧/为空”的问题，不读取正文以避免放大状态检查成本。
    stat = path.stat() if exists else None
    return {
        "name": name,
        "path": str(path),
        "exists": exists,
        "size_bytes": stat.st_size if stat else None,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat() if stat else None,
    }


def build_acceptance_gates(
    quality: DataQualityReport,
    predictions: list[PredictionRow],
    backtest: BacktestResult,
    pipeline_manifest: dict[str, Any],
    storage_status: dict[str, Any] | None,
    artifact_status: dict[str, Any] | None,
) -> dict[str, Any]:
    checks = [
        _gate_check(
            "pipeline_success",
            "Pipeline 执行成功",
            pipeline_manifest.get("status") == "success",
            f"status={pipeline_manifest.get('status')}",
        ),
        _gate_check(
            "data_quality_passed",
            "数据质量通过",
            quality.passed,
            f"issues={quality.issue_count}, rows={quality.row_count}",
        ),
        _gate_check(
            "duckdb_mirror_healthy",
            "DuckDB 镜像一致",
            storage_status is not None and storage_status.get("status") == "healthy",
            "status=missing"
            if storage_status is None
            else f"status={storage_status.get('status')}",
        ),
        _gate_check(
            "predictions_available",
            "预测结果非空",
            len(predictions) > 0,
            f"count={len(predictions)}",
        ),
        _gate_check(
            "backtest_has_trades",
            "回测存在交易",
            backtest.trade_count > 0,
            f"trade_count={backtest.trade_count}",
        ),
        _gate_check(
            "artifacts_complete",
            "关键产物完整",
            artifact_status is not None and artifact_status.get("status") == "complete",
            "status=missing"
            if artifact_status is None
            else f"missing={','.join(artifact_status.get('missing', [])) or '-'}",
        ),
    ]
    failed_checks = [check for check in checks if check["status"] != "passed"]
    # 验收门禁是开发期的最小端到端判定，失败项必须结构化暴露给 CLI/API/页面，而不是只留在日志里。
    return {
        "status": "passed" if not failed_checks else "failed",
        "passed": not failed_checks,
        "check_count": len(checks),
        "failed_count": len(failed_checks),
        "checks": checks,
    }


def _gate_check(key: str, name: str, passed: bool, message: str) -> dict[str, str]:
    return {
        "key": key,
        "name": name,
        "status": "passed" if passed else "failed",
        "message": message,
    }


def write_research_status(path: Path, status: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
