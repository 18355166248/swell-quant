from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from swell_quant.data.quality import DataQualityReport
from swell_quant.research.backtest import BacktestResult
from swell_quant.research.candidates import build_research_candidates
from swell_quant.research.labels import LabelRow
from swell_quant.research.modeling import ModelMetadata, PredictionRow


RESEARCH_DISCLAIMER = "仅用于研究，不构成投资建议"


def build_research_summary(
    metadata: ModelMetadata,
    predictions: list[PredictionRow],
    backtest: BacktestResult,
    quality: DataQualityReport | None = None,
    data_metadata: dict[str, Any] | None = None,
    historical_predictions: list[PredictionRow] | None = None,
    labels: list[LabelRow] | None = None,
    readiness: dict[str, Any] | None = None,
) -> str:
    payload = build_research_report_payload(
        metadata,
        predictions,
        backtest,
        quality,
        data_metadata,
        historical_predictions,
        labels,
        readiness,
    )
    return render_research_summary(payload)


def build_research_report_payload(
    metadata: ModelMetadata,
    predictions: list[PredictionRow],
    backtest: BacktestResult,
    quality: DataQualityReport | None = None,
    data_metadata: dict[str, Any] | None = None,
    historical_predictions: list[PredictionRow] | None = None,
    labels: list[LabelRow] | None = None,
    readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sorted_predictions = sorted(predictions, key=lambda row: row.rank)
    acquisition = _acquisition_payload(data_metadata)
    research_candidates = build_research_candidates(
        sorted_predictions,
        historical_predictions=historical_predictions,
        labels=labels,
        top_n=min(10, len(sorted_predictions)),
        readiness=readiness,
        symbol_names=(data_metadata or {}).get("symbol_names", {}),
    )
    return {
        "report_id": "sample-research-summary",
        "title": "Swell Quant 离线研究摘要",
        "disclaimer": RESEARCH_DISCLAIMER,
        "data_quality": _quality_payload(quality),
        "data_acquisition": acquisition,
        "model": {
            "model_version": metadata.model_version,
            "model_type": metadata.model_type,
            "requested_model_type": metadata.requested_model_type,
            "training_backend": metadata.training_backend,
            "dependency_status": metadata.dependency_status,
            "train_start": metadata.train_start,
            "train_end": metadata.train_end,
            "prediction_date": metadata.prediction_date,
            "feature_names": metadata.feature_names,
            "feature_importance": metadata.feature_importance or [],
            "label_gap_days": metadata.label_gap_days,
            "evaluation_status": metadata.evaluation_status,
            "evaluation_train_start": metadata.evaluation_train_start,
            "evaluation_train_end": metadata.evaluation_train_end,
            "validation_start": metadata.validation_start,
            "validation_end": metadata.validation_end,
            "test_start": metadata.test_start,
            "test_end": metadata.test_end,
            "top1_outperform_rate": _metric_float(metadata.metrics, "top1_outperform_rate"),
        },
        "predictions": [
            {
                "rank": row.rank,
                "symbol": row.symbol,
                "score": row.score,
                "momentum_5d": row.momentum_5d,
                "return_1d": row.return_1d,
            }
            for row in sorted_predictions
        ],
        "research_actions": {
            "summary": _research_action_summary(research_candidates["candidates"]),
            "candidates": [
                {
                    "rank": candidate["rank"],
                    "symbol": candidate["symbol"],
                    "symbol_name": candidate["symbol_name"],
                    "confidence_level": candidate["confidence_level"],
                    "research_action": candidate["research_action"],
                }
                for candidate in research_candidates["candidates"]
            ],
            "disclaimer": RESEARCH_DISCLAIMER,
        },
        "backtest": {
            "backtest_id": backtest.backtest_id,
            "top_n": backtest.top_n,
            "start_date": backtest.start_date,
            "end_date": backtest.end_date,
            "fee_rate": backtest.fee_rate,
            "slippage_rate": backtest.slippage_rate,
            "trade_count": backtest.trade_count,
            "rejected_trade_count": len(backtest.rejected_trades),
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
        "risk_notes": [
            f"当前模型类型：{metadata.model_type}，仍处于离线研究验证阶段。",
            "样例数据为本地生成数据，不代表真实 A 股行情。",
            "初始股票池和基准同源，跑赢结果不能解读为跨股票池泛化能力。",
            *_acquisition_risk_notes(acquisition),
            backtest.disclaimer,
        ],
    }


def render_research_summary(payload: dict[str, Any]) -> str:
    model = payload["model"]
    backtest = payload["backtest"]
    lines = [
        f"# {payload['title']}",
        "",
        f"> {payload['disclaimer']}；历史回测不代表未来表现。",
        "",
        "## 数据质量",
        "",
        *_build_quality_lines(payload["data_quality"]),
        "",
        "## 数据采集",
        "",
        *_build_acquisition_lines(payload.get("data_acquisition")),
        "",
        "## 模型",
        "",
        f"- 模型版本：`{model['model_version']}`",
        f"- 模型类型：`{model['model_type']}`",
        f"- 目标模型：`{model['requested_model_type']}`",
        f"- 训练后端：`{model['training_backend']}`",
        f"- 依赖状态：`{model['dependency_status']}`",
        f"- 训练区间：{model['train_start']} 至 {model['train_end']}",
        f"- 预测日期：{model['prediction_date']}",
        f"- 特征：{', '.join(model['feature_names'])}",
        f"- 时间序列评估状态：{model['evaluation_status']}",
        f"- 标签 Gap：{model['label_gap_days']} 个交易日",
        f"- 评估训练窗：{model['evaluation_train_start'] or '-'} 至 {model['evaluation_train_end'] or '-'}",
        f"- 验证窗：{model['validation_start'] or '-'} 至 {model['validation_end'] or '-'}",
        f"- 测试窗：{model['test_start'] or '-'} 至 {model['test_end'] or '-'}",
        f"- Top1 测试跑赢率：{_format_percent(model['top1_outperform_rate'])}",
        "",
        "## 最新预测 Top N",
        "",
        "| 排名 | 代码 | 分数 | 5日动量 | 1日收益 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]

    for prediction in payload["predictions"]:
        lines.append(
            "| "
            f"{prediction['rank']} | "
            f"`{prediction['symbol']}` | "
            f"{prediction['score']:.6f} | "
            f"{_format_percent(prediction['momentum_5d'])} | "
            f"{_format_percent(prediction['return_1d'])} |"
        )

    # Markdown 只渲染结构化 JSON 产物，后续 LLM 报告也应复用同一份输入，避免口径漂移。
    lines.extend(
        [
            "",
            "## 研究动作分层",
            "",
            *_build_research_action_lines(payload.get("research_actions")),
            "",
            "## 回测摘要",
            "",
            f"- 回测 ID：`{backtest['backtest_id']}`",
            f"- Top N：{backtest['top_n']}",
            f"- 回测区间：{backtest['start_date']} 至 {backtest['end_date']}",
            f"- 手续费率：{_format_percent(backtest['fee_rate'])}",
            f"- 滑点率：{_format_percent(backtest['slippage_rate'])}",
            f"- 调仓次数：{backtest['trade_count']}",
            f"- 无法成交记录：{backtest['rejected_trade_count']}",
            f"- 累计收益：{_format_percent(backtest['cumulative_return'])}",
            f"- 年化收益：{_format_percent(backtest['annualized_return'])}",
            f"- 基准收益：{_format_percent(backtest['benchmark_return'])}",
            f"- 超额收益：{_format_percent(backtest['excess_return'])}",
            f"- 最大回撤：{_format_percent(backtest['max_drawdown'])}",
            f"- 夏普比率：{_format_number(backtest['sharpe_ratio'])}",
            f"- 胜率：{_format_percent(backtest['win_rate'])}",
            f"- 平均换手率：{_format_percent(backtest['turnover_rate'])}",
            "",
            "## 风险提示",
            "",
            *[f"- {note}" for note in payload["risk_notes"]],
            "",
        ]
    )
    return "\n".join(lines)


def write_research_summary(path: Path, summary: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(summary, encoding="utf-8")
    return path


def write_research_report_payload(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_research_report_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.2f}%"


def _format_number(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}"


def _metric_float(metrics: dict[str, float | int | str | None] | None, key: str) -> float | None:
    if metrics is None:
        return None
    value = metrics.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _research_action_summary(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"focus": 0, "review": 0, "defer": 0}
    for candidate in candidates:
        status = candidate.get("research_action", {}).get("status")
        if status in counts:
            counts[status] += 1
    return counts


def _build_research_action_lines(actions: dict[str, Any] | None) -> list[str]:
    if actions is None:
        return ["- 研究动作分层：未提供"]

    summary = actions.get("summary", {})
    lines = [
        "- 分层只表示研究复核优先级，不代表买入、卖出、仓位或目标价。",
        (
            "- 分层统计："
            f"可关注 {summary.get('focus', 0)}，"
            f"需复核 {summary.get('review', 0)}，"
            f"暂缓观察 {summary.get('defer', 0)}"
        ),
        "| 排名 | 代码 | 名称 | 动作 | 理由 | 阻塞项 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in actions.get("candidates", []):
        action = candidate["research_action"]
        lines.append(
            "| "
            f"{candidate['rank']} | "
            f"`{candidate['symbol']}` | "
            f"{candidate.get('symbol_name') or candidate['symbol']} | "
            f"{action['label']} | "
            f"{'；'.join(action['reasons']) or '-'} | "
            f"{'；'.join(action['blockers']) or '-'} |"
        )
    return lines


def _quality_payload(quality: DataQualityReport | None) -> dict[str, Any] | None:
    if quality is None:
        return None
    return {
        "row_count": quality.row_count,
        "symbol_count": quality.symbol_count,
        "start_date": quality.start_date,
        "end_date": quality.end_date,
        "issue_count": quality.issue_count,
        "issues": [
            {
                "code": issue.code,
                "symbol": issue.symbol,
                "date": issue.date,
                "message": issue.message,
            }
            for issue in quality.issues[:5]
        ],
    }


def _acquisition_payload(data_metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if data_metadata is None:
        return None
    return {
        "data_source": data_metadata.get("data_source"),
        "universe": data_metadata.get("universe"),
        "universe_mode": data_metadata.get("universe_mode"),
        "resolved_symbol_count": data_metadata.get("resolved_symbol_count"),
        "selected_symbol_count": data_metadata.get("selected_symbol_count"),
        "succeeded_symbol_count": data_metadata.get("succeeded_symbol_count"),
        "failed_symbol_count": data_metadata.get("failed_symbol_count"),
        "failed_symbols": data_metadata.get("failed_symbols") or [],
        "max_symbols": data_metadata.get("max_symbols"),
    }


def _acquisition_risk_notes(acquisition: dict[str, Any] | None) -> list[str]:
    if acquisition is None:
        return []
    notes: list[str] = []
    failed_count = acquisition.get("failed_symbol_count") or 0
    max_symbols = acquisition.get("max_symbols")
    if failed_count:
        notes.append(f"本次数据采集有 {failed_count} 只标的失败，真实数据覆盖不完整。")
    if max_symbols:
        notes.append(
            f"本次 AKShare 采集启用了 {max_symbols} 只标的试跑上限，不代表完整股票池结果。"
        )
    return notes


def _build_quality_lines(quality: dict[str, Any] | None) -> list[str]:
    if quality is None:
        return ["- 数据质量报告：未提供"]

    lines = [
        f"- 行数：{quality['row_count']}",
        f"- 股票数：{quality['symbol_count']}",
        f"- 日期范围：{quality['start_date']} 至 {quality['end_date']}",
        f"- 问题数：{quality['issue_count']}",
    ]
    if quality["issues"]:
        lines.extend(
            f"- `{issue['code']}` {issue['symbol'] or '-'} {issue['date'] or '-'}：{issue['message']}"
            for issue in quality["issues"]
        )
    else:
        lines.append("- 数据质量检查：通过")
    return lines


def _build_acquisition_lines(acquisition: dict[str, Any] | None) -> list[str]:
    if acquisition is None:
        return ["- 数据采集摘要：未提供"]

    lines = [
        f"- 数据源：{acquisition.get('data_source') or '-'}",
        f"- 股票池模式：{acquisition.get('universe_mode') or '-'}",
        f"- 解析标的：{acquisition.get('resolved_symbol_count') or 0}",
        f"- 选择标的：{acquisition.get('selected_symbol_count') or 0}",
        f"- 成功标的：{acquisition.get('succeeded_symbol_count') or 0}",
        f"- 失败标的：{acquisition.get('failed_symbol_count') or 0}",
        f"- 试跑上限：{acquisition.get('max_symbols') or '未限制'}",
    ]
    for failure in acquisition.get("failed_symbols", [])[:5]:
        lines.append(f"- 采集失败 `{failure.get('symbol')}`：{failure.get('reason')}")
    return lines
