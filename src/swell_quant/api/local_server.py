from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from swell_quant.data.quality import read_quality_report
from swell_quant.research.backtest import read_backtest_result
from swell_quant.research.modeling import read_predictions_csv


class ResearchApiHandler(BaseHTTPRequestHandler):
    data_dir = Path("./data")

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        route = urlparse(self.path).path
        if route == "/api/health":
            self._send_json({"status": "ok", "service": "swell-quant-local-api"})
            return
        if route == "/api/status":
            self._send_artifact_json(self.data_dir / "reports" / "research_status.json")
            return
        if route == "/api/pipeline":
            self._send_artifact_json(self.data_dir / "reports" / "pipeline_run.json")
            return
        if route == "/api/data-quality":
            self._send_loader_json(
                self.data_dir / "processed" / "data_quality.json",
                load_data_quality_artifact,
            )
            return
        if route == "/api/predictions/latest":
            self._send_loader_json(
                self.data_dir / "processed" / "latest_predictions.csv",
                load_latest_predictions_artifact,
            )
            return
        if route == "/api/backtest/latest":
            self._send_loader_json(
                self.data_dir / "reports" / "sample_backtest.json",
                load_backtest_artifact,
            )
            return
        if route == "/api/report":
            self._send_artifact_text(
                self.data_dir / "reports" / "sample_research_summary.md",
                content_type="text/markdown; charset=utf-8",
            )
            return

        self._send_json({"error": "not_found", "path": route}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_artifact_json(self, path: Path) -> None:
        if not path.exists():
            self._send_json(missing_artifact_payload(path), status=HTTPStatus.NOT_FOUND)
            return
        self._send_json(load_json_artifact(path))

    def _send_loader_json(self, path: Path, loader: Any) -> None:
        if not path.exists():
            self._send_json(missing_artifact_payload(path), status=HTTPStatus.NOT_FOUND)
            return
        self._send_json(loader(path))

    def _send_artifact_text(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_json(missing_artifact_payload(path), status=HTTPStatus.NOT_FOUND)
            return
        payload = load_text_artifact(path).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str, port: int, data_dir: Path) -> ThreadingHTTPServer:
    # 为每个 server 创建独立 handler 子类，避免多个测试或本地服务共享 data_dir。
    handler_class = type(
        "ConfiguredResearchApiHandler",
        (ResearchApiHandler,),
        {"data_dir": data_dir},
    )
    return ThreadingHTTPServer((host, port), handler_class)


def load_json_artifact(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_text_artifact(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_data_quality_artifact(path: Path) -> dict[str, Any]:
    report = read_quality_report(path)
    return {
        "passed": report.passed,
        "row_count": report.row_count,
        "symbol_count": report.symbol_count,
        "start_date": report.start_date,
        "end_date": report.end_date,
        "issue_count": report.issue_count,
        "issues": [
            {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "symbol": issue.symbol,
                "date": issue.date,
            }
            for issue in report.issues
        ],
    }


def load_latest_predictions_artifact(path: Path) -> dict[str, Any]:
    predictions = read_predictions_csv(path)
    ordered = sorted(predictions, key=lambda row: row.rank)
    return {
        "count": len(ordered),
        "predictions": [
            {
                "rank": row.rank,
                "symbol": row.symbol,
                "date": row.trade_date.isoformat(),
                "model_version": row.model_version,
                "score": row.score,
                "return_1d": row.return_1d,
                "momentum_5d": row.momentum_5d,
                "volume_change_1d": row.volume_change_1d,
            }
            for row in ordered
        ],
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def load_backtest_artifact(path: Path) -> dict[str, Any]:
    result = read_backtest_result(path)
    return {
        "backtest_id": result.backtest_id,
        "model_version": result.model_version,
        "top_n": result.top_n,
        "trade_count": result.trade_count,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "cumulative_return": result.cumulative_return,
        "benchmark_return": result.benchmark_return,
        "excess_return": result.excess_return,
        "equity_curve": result.equity_curve,
        "disclaimer": result.disclaimer,
    }


def missing_artifact_payload(path: Path) -> dict[str, str]:
    return {
        "error": "artifact_missing",
        "path": str(path),
        "hint": "run `python3 scripts/run_pipeline.py` first",
    }
