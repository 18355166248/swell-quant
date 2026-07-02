from __future__ import annotations

from pathlib import Path

from swell_quant.research.backtest import BacktestResult
from swell_quant.research.modeling import ModelMetadata, PredictionRow


RESEARCH_DISCLAIMER = "仅用于研究，不构成投资建议"


def build_research_summary(
    metadata: ModelMetadata,
    predictions: list[PredictionRow],
    backtest: BacktestResult,
) -> str:
    sorted_predictions = sorted(predictions, key=lambda row: row.rank)
    lines = [
        "# Swell Quant 离线研究摘要",
        "",
        f"> {RESEARCH_DISCLAIMER}；历史回测不代表未来表现。",
        "",
        "## 模型",
        "",
        f"- 模型版本：`{metadata.model_version}`",
        f"- 模型类型：`{metadata.model_type}`",
        f"- 训练区间：{metadata.train_start} 至 {metadata.train_end}",
        f"- 预测日期：{metadata.prediction_date}",
        f"- 特征：{', '.join(metadata.feature_names)}",
        "",
        "## 最新预测 Top N",
        "",
        "| 排名 | 代码 | 分数 | 5日动量 | 1日收益 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]

    for prediction in sorted_predictions:
        lines.append(
            "| "
            f"{prediction.rank} | "
            f"`{prediction.symbol}` | "
            f"{prediction.score:.6f} | "
            f"{_format_percent(prediction.momentum_5d)} | "
            f"{_format_percent(prediction.return_1d)} |"
        )

    # 报告只汇总结构化产物，避免 LLM 式扩写把 baseline 结果包装成交易建议。
    lines.extend(
        [
            "",
            "## 回测摘要",
            "",
            f"- 回测 ID：`{backtest.backtest_id}`",
            f"- Top N：{backtest.top_n}",
            f"- 回测区间：{backtest.start_date} 至 {backtest.end_date}",
            f"- 调仓次数：{backtest.trade_count}",
            f"- 累计收益：{_format_percent(backtest.cumulative_return)}",
            f"- 基准收益：{_format_percent(backtest.benchmark_return)}",
            f"- 超额收益：{_format_percent(backtest.excess_return)}",
            "",
            "## 风险提示",
            "",
            "- 当前模型是规则 baseline，不是最终 LightGBM 模型。",
            "- 样例数据为本地生成数据，不代表真实 A 股行情。",
            "- 初始股票池和基准同源，跑赢结果不能解读为跨股票池泛化能力。",
            f"- {backtest.disclaimer}",
            "",
        ]
    )
    return "\n".join(lines)


def write_research_summary(path: Path, summary: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(summary, encoding="utf-8")
    return path


def _format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.2f}%"
