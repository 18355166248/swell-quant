from __future__ import annotations

import json
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
) -> dict[str, Any]:
    top_predictions = sorted(predictions, key=lambda row: row.rank)

    # 状态快照面向 CLI/API/页面复用，只聚合结构化产物，不重新计算研究结果。
    return {
        "disclaimer": "仅用于研究，不构成投资建议",
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
            "start_date": backtest.start_date,
            "end_date": backtest.end_date,
            "cumulative_return": backtest.cumulative_return,
            "benchmark_return": backtest.benchmark_return,
            "excess_return": backtest.excess_return,
            "disclaimer": backtest.disclaimer,
        },
        "artifacts": {
            "data_quality": "data/processed/data_quality.json",
            "model": "data/models/baseline-rule-v1.json",
            "latest_predictions": "data/processed/latest_predictions.csv",
            "historical_predictions": "data/processed/historical_predictions.csv",
            "backtest": "data/reports/sample_backtest.json",
            "summary": "data/reports/sample_research_summary.md",
            "pipeline_run": "data/reports/pipeline_run.json",
        },
    }


def write_research_status(path: Path, status: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
