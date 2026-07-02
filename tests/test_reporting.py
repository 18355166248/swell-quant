from pathlib import Path

from swell_quant.data.quality import validate_price_bars
from swell_quant.data.sample_data import generate_sample_bars
from swell_quant.research.backtest import (
    read_backtest_result,
    run_top_n_backtest,
    write_backtest_result,
)
from swell_quant.research.features import compute_features
from swell_quant.research.labels import compute_labels
from swell_quant.research.modeling import (
    generate_historical_predictions,
    generate_predictions,
    read_model_metadata,
    read_predictions_csv,
    train_baseline_model,
    write_model_metadata,
    write_predictions_csv,
)
from swell_quant.research.reporting import (
    build_research_report_payload,
    build_research_summary,
    read_research_report_payload,
    render_research_summary,
    write_research_report_payload,
    write_research_summary,
)


def test_research_summary_contains_required_sections() -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)
    quality = validate_price_bars(bars)
    metadata = train_baseline_model(features, labels)
    latest_predictions = generate_predictions(features)
    backtest = run_top_n_backtest(bars, generate_historical_predictions(features))

    summary = build_research_summary(metadata, latest_predictions, backtest, quality)
    payload = build_research_report_payload(metadata, latest_predictions, backtest, quality)

    assert payload["model"]["model_version"] == "baseline-rule-v1"
    assert payload["backtest"]["backtest_id"] == "sample-topn-baseline"
    assert payload["predictions"][0]["rank"] == 1
    assert payload["risk_notes"]
    assert "# Swell Quant 离线研究摘要" in summary
    assert "## 数据质量" in summary
    assert "数据质量检查：通过" in summary
    assert "仅用于研究，不构成投资建议" in summary
    assert "baseline-rule-v1" in summary
    assert "目标模型：`lightgbm`" in summary
    assert "训练后端：`rule_baseline_fallback`" in summary
    assert "依赖状态：" in summary
    assert "时间序列评估状态：ready" in summary
    assert "标签 Gap：5 个交易日" in summary
    assert "测试窗：2024-01-16 至 2024-01-16" in summary
    assert "## 最新预测 Top N" in summary
    assert "## 回测摘要" in summary
    assert "滑点率" in summary
    assert "无法成交记录" in summary
    assert "最大回撤" in summary
    assert "夏普比率" in summary
    assert "平均换手率" in summary
    assert "当前模型类型：rule_baseline" in summary


def test_research_artifacts_read_round_trip(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)
    metadata = train_baseline_model(features, labels)
    predictions = generate_predictions(features)
    backtest = run_top_n_backtest(bars, generate_historical_predictions(features))

    metadata_path = write_model_metadata(tmp_path / "model.json", metadata)
    predictions_path = write_predictions_csv(tmp_path / "predictions.csv", predictions)
    backtest_path = write_backtest_result(tmp_path / "backtest.json", backtest)

    summary = build_research_summary(
        read_model_metadata(metadata_path),
        read_predictions_csv(predictions_path),
        read_backtest_result(backtest_path),
    )
    payload = build_research_report_payload(
        read_model_metadata(metadata_path),
        read_predictions_csv(predictions_path),
        read_backtest_result(backtest_path),
    )
    summary_path = write_research_summary(tmp_path / "summary.md", summary)
    payload_path = write_research_report_payload(tmp_path / "summary.json", payload)

    assert summary_path.read_text(encoding="utf-8") == summary
    assert read_research_report_payload(payload_path)["report_id"] == "sample-research-summary"
    assert render_research_summary(payload) == summary
