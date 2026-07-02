from __future__ import annotations

import json
import csv
import importlib.util
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from swell_quant.core.config import Settings
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
        stock_response = load_stock_route(route, self.data_dir)
        if stock_response is not None:
            status, payload = stock_response
            self._send_json(payload, status=status)
            return
        if route == "/api/report":
            self._send_artifact_text(
                self.data_dir / "reports" / "sample_research_summary.md",
                content_type="text/markdown; charset=utf-8",
            )
            return

        self._send_json({"error": "not_found", "path": route}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        route = urlparse(self.path).path
        if route == "/api/pipeline/run":
            payload = run_pipeline_for_api(self.data_dir)
            status = HTTPStatus.OK if payload["status"] == "success" else HTTPStatus.INTERNAL_SERVER_ERROR
            self._send_json(payload, status=status)
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


def run_pipeline_for_api(data_dir: Path) -> dict[str, Any]:
    runner = _load_pipeline_runner()
    settings = Settings(
        data_dir=data_dir,
        duckdb_path=data_dir / "duckdb" / "swell_quant.duckdb",
    )
    results, manifest_path, status_path = runner(settings)
    status = "failed" if any(result.status.value == "failed" for result in results) else "success"
    return {
        "status": status,
        "manifest_path": str(manifest_path),
        "status_path": None if status_path is None else str(status_path),
        "steps": [
            {
                "name": result.name,
                "status": result.status.value,
                "message": result.message,
                "duration_seconds": result.duration_seconds,
            }
            for result in results
        ],
    }


def _load_pipeline_runner() -> Any:
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "run_pipeline.py"
    spec = importlib.util.spec_from_file_location("swell_quant_pipeline_runner", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load pipeline runner from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_pipeline


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


def load_stock_route(route: str, data_dir: Path) -> tuple[HTTPStatus, dict[str, Any]] | None:
    prefix = "/api/stocks/"
    if not route.startswith(prefix):
        return None

    remainder = route[len(prefix) :]
    parts = [part for part in remainder.split("/") if part]
    if not parts:
        return HTTPStatus.NOT_FOUND, {"error": "not_found", "path": route}

    symbol = parts[0]
    if len(parts) == 1:
        payload = load_stock_summary_artifact(data_dir, symbol)
    elif parts == [symbol, "prices"]:
        payload = load_stock_prices_artifact(data_dir / "raw" / "sample_prices.csv", symbol)
    elif parts == [symbol, "features"]:
        payload = load_stock_features_artifact(data_dir / "processed" / "sample_features.csv", symbol)
    elif parts == [symbol, "predictions"]:
        payload = load_stock_predictions_artifact(
            data_dir / "processed" / "historical_predictions.csv", symbol
        )
    else:
        return HTTPStatus.NOT_FOUND, {"error": "not_found", "path": route}

    if payload is None:
        return HTTPStatus.NOT_FOUND, {"error": "symbol_not_found", "symbol": symbol}
    return HTTPStatus.OK, payload


def load_stock_summary_artifact(data_dir: Path, symbol: str) -> dict[str, Any] | None:
    prices = load_stock_prices_artifact(data_dir / "raw" / "sample_prices.csv", symbol)
    if prices is None:
        return None
    predictions = load_stock_predictions_artifact(
        data_dir / "processed" / "historical_predictions.csv", symbol
    )
    return {
        "symbol": symbol,
        "price_row_count": prices["count"],
        "prediction_row_count": 0 if predictions is None else predictions["count"],
        "start_date": prices["prices"][0]["date"] if prices["prices"] else None,
        "end_date": prices["prices"][-1]["date"] if prices["prices"] else None,
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def load_stock_prices_artifact(path: Path, symbol: str) -> dict[str, Any] | None:
    rows = [row for row in _read_csv_rows(path) if row["symbol"] == symbol]
    if not rows:
        return None
    return {
        "symbol": symbol,
        "count": len(rows),
        "prices": [
            {
                "date": row["date"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "benchmark_close": float(row["benchmark_close"]),
            }
            for row in rows
        ],
    }


def load_stock_features_artifact(path: Path, symbol: str) -> dict[str, Any] | None:
    rows = [row for row in _read_csv_rows(path) if row["symbol"] == symbol]
    if not rows:
        return None
    return {
        "symbol": symbol,
        "count": len(rows),
        "features": [
            {
                "date": row["date"],
                "close": float(row["close"]),
                "return_1d": _parse_optional_float(row["return_1d"]),
                "momentum_5d": _parse_optional_float(row["momentum_5d"]),
                "ma_5": _parse_optional_float(row["ma_5"]),
                "volume_change_1d": _parse_optional_float(row["volume_change_1d"]),
            }
            for row in rows
        ],
    }


def load_stock_predictions_artifact(path: Path, symbol: str) -> dict[str, Any] | None:
    rows = [row for row in _read_csv_rows(path) if row["symbol"] == symbol]
    if not rows:
        return None
    return {
        "symbol": symbol,
        "count": len(rows),
        "predictions": [
            {
                "date": row["date"],
                "model_version": row["model_version"],
                "score": float(row["score"]),
                "rank": int(row["rank"]),
                "return_1d": _parse_optional_float(row["return_1d"]),
                "momentum_5d": _parse_optional_float(row["momentum_5d"]),
                "volume_change_1d": _parse_optional_float(row["volume_change_1d"]),
            }
            for row in rows
        ],
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def missing_artifact_payload(path: Path) -> dict[str, str]:
    return {
        "error": "artifact_missing",
        "path": str(path),
        "hint": "run `python3 scripts/run_pipeline.py` first",
    }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _parse_optional_float(value: str) -> float | None:
    return None if value == "" else float(value)
