from __future__ import annotations

import json
import csv
import importlib.util
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from swell_quant.core.config import Settings
from swell_quant.data.quality import read_quality_report
from swell_quant.research.backtest import read_backtest_result
from swell_quant.research.modeling import read_predictions_csv


_PIPELINE_RUN_LOCK = threading.Lock()


class ResearchApiHandler(BaseHTTPRequestHandler):
    data_dir = Path("./data")
    duckdb_path = Path("./data/duckdb/swell_quant.duckdb")
    deepseek_api_key_configured = False
    openai_api_key_configured = False

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)
        if route == "/api/health":
            self._send_json({"status": "ok", "service": "swell-quant-local-api"})
            return
        if route == "/api/settings":
            self._send_json(
                load_settings_artifact(
                    self.data_dir,
                    self.duckdb_path,
                    self.deepseek_api_key_configured,
                    self.openai_api_key_configured,
                )
            )
            return
        if route == "/api/status":
            self._send_artifact_json(self.data_dir / "reports" / "research_status.json")
            return
        if route == "/api/pipeline":
            self._send_artifact_json(self.data_dir / "reports" / "pipeline_run.json")
            return
        if route == "/api/data/status":
            self._send_loader_json(
                self.data_dir / "processed" / "data_quality.json",
                load_data_status_artifact,
            )
            return
        if route == "/api/models/latest":
            self._send_loader_json(
                self.data_dir / "models" / "baseline-rule-v1.json",
                load_latest_model_artifact,
            )
            return
        model_response = load_model_route(route, self.data_dir)
        if model_response is not None:
            status, payload = model_response
            self._send_json(payload, status=status)
            return
        task_response = load_task_route(route, self.data_dir)
        if task_response is not None:
            status, payload = task_response
            self._send_json(payload, status=status)
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
        prediction_response = load_prediction_route(route, query, self.data_dir)
        if prediction_response is not None:
            status, payload = prediction_response
            self._send_json(payload, status=status)
            return
        if route == "/api/backtest/latest":
            self._send_loader_json(
                self.data_dir / "reports" / "sample_backtest.json",
                load_backtest_artifact,
            )
            return
        backtest_response = load_backtest_route(route, self.data_dir)
        if backtest_response is not None:
            status, payload = backtest_response
            self._send_json(payload, status=status)
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
        report_response = load_report_route(route, self.data_dir)
        if report_response is not None:
            status, payload = report_response
            self._send_json(payload, status=status)
            return

        self._send_json({"error": "not_found", "path": route}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        route = urlparse(self.path).path
        if route == "/api/pipeline/run":
            payload = run_pipeline_for_api(self.data_dir)
            status = pipeline_status_to_http_status(payload["status"])
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


def create_server(
    host: str,
    port: int,
    data_dir: Path,
    settings: Settings | None = None,
) -> ThreadingHTTPServer:
    resolved_settings = settings or Settings(
        data_dir=data_dir,
        duckdb_path=data_dir / "duckdb" / "swell_quant.duckdb",
    )
    # 为每个 server 创建独立 handler 子类，避免多个测试或本地服务共享 data_dir。
    handler_class = type(
        "ConfiguredResearchApiHandler",
        (ResearchApiHandler,),
        {
            "data_dir": resolved_settings.data_dir,
            "duckdb_path": resolved_settings.duckdb_path,
            "deepseek_api_key_configured": resolved_settings.deepseek_api_key is not None,
            "openai_api_key_configured": resolved_settings.openai_api_key is not None,
        },
    )
    return ThreadingHTTPServer((host, port), handler_class)


def pipeline_status_to_http_status(status: str) -> HTTPStatus:
    if status == "success":
        return HTTPStatus.OK
    if status == "busy":
        return HTTPStatus.CONFLICT
    return HTTPStatus.INTERNAL_SERVER_ERROR


def run_pipeline_for_api(
    data_dir: Path,
    lock: threading.Lock | None = None,
) -> dict[str, Any]:
    run_lock = _PIPELINE_RUN_LOCK if lock is None else lock
    # pipeline 会连续写 raw/processed/models/reports，进程内先串行化，避免并发触发覆盖同一批产物。
    if not run_lock.acquire(blocking=False):
        return {
            "status": "busy",
            "error": "pipeline_already_running",
            "message": "pipeline is already running; retry after the current run finishes",
        }

    try:
        return _run_pipeline_for_api_unlocked(data_dir)
    finally:
        run_lock.release()


def _run_pipeline_for_api_unlocked(data_dir: Path) -> dict[str, Any]:
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


def load_settings_artifact(
    data_dir: Path,
    duckdb_path: Path,
    deepseek_api_key_configured: bool,
    openai_api_key_configured: bool,
) -> dict[str, Any]:
    artifacts = {
        "raw_prices": data_dir / "raw" / "sample_prices.csv",
        "data_quality": data_dir / "processed" / "data_quality.json",
        "features": data_dir / "processed" / "sample_features.csv",
        "labels": data_dir / "processed" / "sample_labels.csv",
        "model": data_dir / "models" / "baseline-rule-v1.json",
        "latest_predictions": data_dir / "processed" / "latest_predictions.csv",
        "historical_predictions": data_dir / "processed" / "historical_predictions.csv",
        "backtest": data_dir / "reports" / "sample_backtest.json",
        "report": data_dir / "reports" / "sample_research_summary.md",
        "pipeline": data_dir / "reports" / "pipeline_run.json",
        "status": data_dir / "reports" / "research_status.json",
    }
    return {
        "service": {
            "name": "swell-quant-local-api",
            "mode": "local-research",
            "disclaimer": "仅用于研究，不构成投资建议",
        },
        "paths": {
            "data_dir": str(data_dir),
            "duckdb_path": str(duckdb_path),
        },
        "api_keys": {
            # 只暴露是否配置，避免把任何 secret 明文返回给前端或日志。
            "deepseek_configured": deepseek_api_key_configured,
            "openai_configured": openai_api_key_configured,
        },
        "artifacts": [
            {
                "name": name,
                "path": str(path),
                "exists": path.exists(),
            }
            for name, path in artifacts.items()
        ],
    }


def load_task_route(route: str, data_dir: Path) -> tuple[HTTPStatus, dict[str, Any]] | None:
    if route == "/api/tasks":
        pipeline_path = data_dir / "reports" / "pipeline_run.json"
        if not pipeline_path.exists():
            return HTTPStatus.NOT_FOUND, missing_artifact_payload(pipeline_path)
        return HTTPStatus.OK, load_tasks_artifact(pipeline_path)
    if route == "/api/tasks/pipeline-latest":
        pipeline_path = data_dir / "reports" / "pipeline_run.json"
        if not pipeline_path.exists():
            return HTTPStatus.NOT_FOUND, missing_artifact_payload(pipeline_path)
        return HTTPStatus.OK, load_task_detail_artifact(pipeline_path)
    if route.startswith("/api/tasks/"):
        task_id = route[len("/api/tasks/") :]
        return HTTPStatus.NOT_FOUND, {"error": "task_not_found", "task_id": task_id}
    return None


def load_tasks_artifact(path: Path) -> dict[str, Any]:
    detail = load_task_detail_artifact(path)
    summary = {
        key: detail[key]
        for key in (
            "id",
            "type",
            "status",
            "started_at",
            "ended_at",
            "duration_seconds",
            "step_count",
            "failed_step",
            "output_path",
        )
    }
    return {"count": 1, "tasks": [summary]}


def load_task_detail_artifact(path: Path) -> dict[str, Any]:
    manifest = load_json_artifact(path)
    steps = manifest.get("steps", [])
    failed_step = next((step["name"] for step in steps if step.get("status") == "failed"), None)
    return {
        "id": "pipeline-latest",
        "type": "pipeline",
        "status": manifest.get("status", "unknown"),
        "started_at": manifest.get("started_at"),
        "ended_at": manifest.get("ended_at"),
        "duration_seconds": manifest.get("duration_seconds"),
        "step_count": manifest.get("step_count", len(steps)),
        "failed_step": failed_step,
        "output_path": str(path),
        "steps": steps,
    }


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


def load_data_status_artifact(path: Path) -> dict[str, Any]:
    quality = load_data_quality_artifact(path)
    return {
        "market": "A_SHARE_DAILY",
        "universe": "sample_a_share",
        "row_count": quality["row_count"],
        "symbol_count": quality["symbol_count"],
        "start_date": quality["start_date"],
        "end_date": quality["end_date"],
        "quality_passed": quality["passed"],
        "issue_count": quality["issue_count"],
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def load_latest_model_artifact(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return {
        "model_version": payload["model_version"],
        "model_type": payload["model_type"],
        "feature_names": payload["feature_names"],
        "feature_count": len(payload["feature_names"]),
        "train_start": payload["train_start"],
        "train_end": payload["train_end"],
        "prediction_date": payload["prediction_date"],
        "row_count": payload["row_count"],
        "disclaimer": payload.get("disclaimer", "仅用于研究，不构成投资建议"),
    }


def load_model_route(route: str, data_dir: Path) -> tuple[HTTPStatus, dict[str, Any]] | None:
    if route == "/api/models":
        models_dir = data_dir / "models"
        if not models_dir.exists():
            return HTTPStatus.NOT_FOUND, missing_artifact_payload(models_dir)
        return HTTPStatus.OK, load_models_artifact(models_dir)
    if route.startswith("/api/models/"):
        model_version = route[len("/api/models/") :]
        path = data_dir / "models" / f"{model_version}.json"
        if not path.exists():
            return HTTPStatus.NOT_FOUND, {"error": "model_not_found", "model_version": model_version}
        return HTTPStatus.OK, load_model_artifact(path)
    return None


def load_models_artifact(models_dir: Path) -> dict[str, Any]:
    model_paths = sorted(
        models_dir.glob("*.json"),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    models = [model_summary_payload(path) for path in model_paths]
    return {
        "count": len(models),
        "models": models,
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def load_model_artifact(path: Path) -> dict[str, Any]:
    payload = load_latest_model_artifact(path)
    payload["path"] = str(path)
    payload["updated_at"] = _format_file_timestamp(path)
    return payload


def model_summary_payload(path: Path) -> dict[str, Any]:
    detail = load_model_artifact(path)
    summary_keys = (
        "model_version",
        "model_type",
        "feature_count",
        "train_start",
        "train_end",
        "prediction_date",
        "row_count",
        "path",
        "updated_at",
        "disclaimer",
    )
    # 列表只返回摘要字段，详情接口再给出完整 feature_names，避免模型多时列表负载过大。
    return {key: detail[key] for key in summary_keys}


def load_latest_predictions_artifact(path: Path) -> dict[str, Any]:
    predictions = read_predictions_csv(path)
    ordered = sorted(predictions, key=lambda row: row.rank)
    return predictions_payload(ordered)


def load_prediction_route(
    route: str,
    query: dict[str, list[str]],
    data_dir: Path,
) -> tuple[HTTPStatus, dict[str, Any]] | None:
    if route != "/api/predictions":
        return None
    path = data_dir / "processed" / "historical_predictions.csv"
    if not path.exists():
        return HTTPStatus.NOT_FOUND, missing_artifact_payload(path)
    return HTTPStatus.OK, load_predictions_artifact(path, query)


def load_predictions_artifact(path: Path, query: dict[str, list[str]]) -> dict[str, Any]:
    rows = read_predictions_csv(path)
    selected_date = _first_query_value(query, "date")
    selected_model = _first_query_value(query, "model_version")
    top_n_value = _first_query_value(query, "top_n")

    if selected_date is None and rows:
        selected_date = max(row.trade_date for row in rows).isoformat()

    filtered = rows
    if selected_date is not None:
        filtered = [row for row in filtered if row.trade_date.isoformat() == selected_date]
    if selected_model is not None:
        filtered = [row for row in filtered if row.model_version == selected_model]

    ordered = sorted(filtered, key=lambda row: (row.rank, row.symbol))
    if top_n_value is not None:
        top_n = max(0, int(top_n_value))
        ordered = ordered[:top_n]

    payload = predictions_payload(ordered)
    payload["filters"] = {
        "date": selected_date,
        "model_version": selected_model,
        "top_n": None if top_n_value is None else int(top_n_value),
    }
    # 前端筛选项来自同一份历史预测文件，避免 UI 可选日期/模型版本和实际查询口径分叉。
    payload["available_dates"] = sorted({row.trade_date.isoformat() for row in rows}, reverse=True)
    payload["model_versions"] = sorted({row.model_version for row in rows})
    return payload


def predictions_payload(predictions: list[Any]) -> dict[str, Any]:
    return {
        "count": len(predictions),
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
            for row in predictions
        ],
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def _first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def load_backtest_artifact(path: Path) -> dict[str, Any]:
    result = read_backtest_result(path)
    return {
        "backtest_id": result.backtest_id,
        "model_version": result.model_version,
        "top_n": result.top_n,
        "fee_rate": result.fee_rate,
        "execution_price": result.execution_price,
        "holding_period": result.holding_period,
        "rebalance_rule": result.rebalance_rule,
        "trade_count": result.trade_count,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "cumulative_return": result.cumulative_return,
        "benchmark_return": result.benchmark_return,
        "excess_return": result.excess_return,
        "equity_curve": normalize_equity_curve(result.equity_curve),
        "disclaimer": result.disclaimer,
    }


def load_backtest_route(route: str, data_dir: Path) -> tuple[HTTPStatus, dict[str, Any]] | None:
    if route == "/api/backtests":
        path = data_dir / "reports" / "sample_backtest.json"
        if not path.exists():
            return HTTPStatus.NOT_FOUND, missing_artifact_payload(path)
        return HTTPStatus.OK, load_backtests_artifact(path)
    if route in {"/api/backtests/latest", "/api/backtests/sample-topn-baseline"}:
        path = data_dir / "reports" / "sample_backtest.json"
        if not path.exists():
            return HTTPStatus.NOT_FOUND, missing_artifact_payload(path)
        return HTTPStatus.OK, load_backtest_artifact(path)
    if route.startswith("/api/backtests/"):
        backtest_id = route[len("/api/backtests/") :]
        return HTTPStatus.NOT_FOUND, {"error": "backtest_not_found", "backtest_id": backtest_id}
    return None


def load_report_route(route: str, data_dir: Path) -> tuple[HTTPStatus, dict[str, Any]] | None:
    if route == "/api/reports":
        path = data_dir / "reports" / "sample_research_summary.md"
        if not path.exists():
            return HTTPStatus.NOT_FOUND, missing_artifact_payload(path)
        return HTTPStatus.OK, load_reports_artifact(path)
    if route in {"/api/reports/latest", "/api/reports/sample-research-summary"}:
        path = data_dir / "reports" / "sample_research_summary.md"
        if not path.exists():
            return HTTPStatus.NOT_FOUND, missing_artifact_payload(path)
        return HTTPStatus.OK, load_report_artifact(path)
    if route.startswith("/api/reports/"):
        report_id = route[len("/api/reports/") :]
        return HTTPStatus.NOT_FOUND, {"error": "report_not_found", "report_id": report_id}
    return None


def load_reports_artifact(path: Path) -> dict[str, Any]:
    detail = load_report_artifact(path)
    summary_keys = (
        "report_id",
        "title",
        "path",
        "generated_at",
        "model_version",
        "backtest_id",
        "summary",
        "disclaimer",
    )
    return {"count": 1, "reports": [{key: detail[key] for key in summary_keys}]}


def load_report_artifact(path: Path) -> dict[str, Any]:
    body = load_text_artifact(path)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    title = lines[0].lstrip("# ").strip() if lines else "Research Report"
    return {
        "report_id": "sample-research-summary",
        "title": title,
        "path": str(path),
        "generated_at": _format_file_timestamp(path),
        "model_version": _extract_markdown_value(body, "模型版本"),
        "backtest_id": _extract_markdown_value(body, "回测 ID"),
        "summary": _first_markdown_paragraph(body),
        "body": body,
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def _format_file_timestamp(path: Path) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _extract_markdown_value(body: str, label: str) -> str | None:
    prefix = f"- {label}："
    for line in body.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip().strip("`")
    return None


def _first_markdown_paragraph(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            return stripped.lstrip("- ").strip()
    return ""


def load_backtests_artifact(path: Path) -> dict[str, Any]:
    detail = load_backtest_artifact(path)
    summary_keys = (
        "backtest_id",
        "model_version",
        "top_n",
        "fee_rate",
        "execution_price",
        "holding_period",
        "rebalance_rule",
        "trade_count",
        "start_date",
        "end_date",
        "cumulative_return",
        "benchmark_return",
        "excess_return",
        "disclaimer",
    )
    return {"count": 1, "backtests": [{key: detail[key] for key in summary_keys}]}


def normalize_equity_curve(rows: list[dict[str, str | float]]) -> list[dict[str, str | float]]:
    normalized: list[dict[str, str | float]] = []
    for row in rows:
        portfolio_value = float(row["equity"])
        benchmark_value = float(row["benchmark_equity"])
        normalized.append(
            {
                "date": str(row["trade_date"]),
                "signal_date": str(row["signal_date"]),
                "portfolio_return": float(row["portfolio_return"]),
                "benchmark_return": float(row["benchmark_return"]),
                "portfolio_value": portfolio_value,
                "benchmark_value": benchmark_value,
                "excess_value": portfolio_value - benchmark_value,
            }
        )
    return normalized


def load_stock_route(route: str, data_dir: Path) -> tuple[HTTPStatus, dict[str, Any]] | None:
    if route == "/api/stocks":
        path = data_dir / "raw" / "sample_prices.csv"
        if not path.exists():
            return HTTPStatus.NOT_FOUND, missing_artifact_payload(path)
        return HTTPStatus.OK, load_stocks_artifact(data_dir)

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


def load_stocks_artifact(data_dir: Path) -> dict[str, Any]:
    price_rows = _read_csv_rows(data_dir / "raw" / "sample_prices.csv")
    prediction_rows = _read_csv_rows(data_dir / "processed" / "historical_predictions.csv")
    price_stats: dict[str, dict[str, Any]] = {}
    prediction_counts: dict[str, int] = {}

    # 股票池以行情文件为准；预测文件可能尚未生成，不能因此让前端下拉缺失可研究标的。
    for row in price_rows:
        symbol = row["symbol"]
        stats = price_stats.setdefault(
            symbol,
            {
                "symbol": symbol,
                "price_row_count": 0,
                "start_date": row["date"],
                "end_date": row["date"],
            },
        )
        stats["price_row_count"] += 1
        stats["start_date"] = min(stats["start_date"], row["date"])
        stats["end_date"] = max(stats["end_date"], row["date"])

    for row in prediction_rows:
        symbol = row["symbol"]
        prediction_counts[symbol] = prediction_counts.get(symbol, 0) + 1

    stocks = [
        {
            "symbol": symbol,
            "price_row_count": stats["price_row_count"],
            "prediction_row_count": prediction_counts.get(symbol, 0),
            "start_date": stats["start_date"],
            "end_date": stats["end_date"],
            "disclaimer": "仅用于研究，不构成投资建议",
        }
        for symbol, stats in sorted(price_stats.items())
    ]
    return {
        "count": len(stocks),
        "stocks": stocks,
        "disclaimer": "仅用于研究，不构成投资建议",
    }


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
