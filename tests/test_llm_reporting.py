from pathlib import Path

from swell_quant.research.llm_reporting import (
    generate_ai_report_payload,
    render_ai_report_markdown,
    write_ai_report_markdown,
    write_ai_report_payload,
)


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate(self, prompt: str) -> str:
        assert "不得输出投资建议" in prompt
        assert "特征重要性" in prompt
        return "这是基于结构化结果的研究说明。仅用于研究，不构成投资建议。"


class FailingProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate(self, _prompt: str) -> str:
        raise RuntimeError("boom")


def sample_payload() -> dict:
    return {
        "model": {
            "model_version": "baseline-rule-v1",
            "feature_importance": [{"feature_name": "momentum_5d", "importance": 0.7}],
        },
        "predictions": [{"rank": 1, "symbol": "000300.SH"}],
        "backtest": {"backtest_id": "sample-topn-baseline"},
        "risk_notes": ["仅用于研究，不构成投资建议"],
    }


def test_generate_ai_report_payload_skips_without_provider() -> None:
    payload = generate_ai_report_payload(sample_payload(), requested_provider="disabled")

    assert payload["status"] == "skipped"
    assert payload["provider"] == "disabled"
    assert payload["content"] == ""


def test_generate_ai_report_payload_uses_provider() -> None:
    payload = generate_ai_report_payload(sample_payload(), provider=FakeProvider())

    assert payload["status"] == "success"
    assert payload["provider"] == "fake"
    assert "不构成投资建议" in payload["content"]


def test_generate_ai_report_payload_captures_provider_failure(tmp_path: Path) -> None:
    payload = generate_ai_report_payload(sample_payload(), provider=FailingProvider())
    json_path = write_ai_report_payload(tmp_path / "ai.json", payload)
    markdown_path = write_ai_report_markdown(tmp_path / "ai.md", payload)

    assert payload["status"] == "failed"
    assert payload["reason"] == "boom"
    assert json_path.exists()
    assert "状态：failed" in markdown_path.read_text(encoding="utf-8")
    assert render_ai_report_markdown(payload).startswith("# Swell Quant AI 研究说明")
