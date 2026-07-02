from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


AI_REPORT_DISCLAIMER = "仅用于研究，不构成投资建议"


class LLMProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class DeepSeekProvider:
    api_key: str
    model_name: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/chat/completions"
    provider_name: str = "deepseek"
    timeout_seconds: int = 30

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是量化研究报告助手，只能解释给定结构化数据。"
                        "不得给出买入、卖出、持仓或收益承诺。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        request = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"]).strip()


def build_ai_report_prompt(research_payload: dict[str, Any]) -> str:
    model = research_payload["model"]
    backtest = research_payload["backtest"]
    predictions = research_payload.get("predictions", [])[:5]
    return "\n".join(
        [
            "请基于以下结构化研究结果生成中文研究摘要。",
            "要求：",
            "1. 只能解释数据、模型、预测排序和回测指标，不得输出投资建议。",
            "2. 必须包含风险提示：仅用于研究，不构成投资建议。",
            "3. 不得把历史回测收益描述为未来可实现收益。",
            "",
            "模型：",
            json.dumps(model, ensure_ascii=False, indent=2),
            "",
            "特征重要性：",
            json.dumps(model.get("feature_importance", []), ensure_ascii=False, indent=2),
            "",
            "最新预测 Top N：",
            json.dumps(predictions, ensure_ascii=False, indent=2),
            "",
            "回测：",
            json.dumps(backtest, ensure_ascii=False, indent=2),
            "",
            "风险提示：",
            json.dumps(research_payload.get("risk_notes", []), ensure_ascii=False, indent=2),
        ]
    )


def generate_ai_report_payload(
    research_payload: dict[str, Any],
    provider: LLMProvider | None = None,
    requested_provider: str = "disabled",
) -> dict[str, Any]:
    prompt = build_ai_report_prompt(research_payload)
    if provider is None:
        return {
            "report_id": "sample-ai-research-summary",
            "status": "skipped",
            "provider": requested_provider,
            "model": None,
            "reason": "missing_or_disabled_llm_provider",
            "prompt": prompt,
            "content": "",
            "disclaimer": AI_REPORT_DISCLAIMER,
        }

    try:
        # LLM 只消费结构化研究产物；失败会降级为 failed 状态产物，不影响训练、预测和回测主链路。
        content = provider.generate(prompt)
    except Exception as error:
        return {
            "report_id": "sample-ai-research-summary",
            "status": "failed",
            "provider": provider.provider_name,
            "model": provider.model_name,
            "reason": str(error),
            "prompt": prompt,
            "content": "",
            "disclaimer": AI_REPORT_DISCLAIMER,
        }

    return {
        "report_id": "sample-ai-research-summary",
        "status": "success",
        "provider": provider.provider_name,
        "model": provider.model_name,
        "reason": None,
        "prompt": prompt,
        "content": content,
        "disclaimer": AI_REPORT_DISCLAIMER,
    }


def render_ai_report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Swell Quant AI 研究说明",
        "",
        f"> {payload['disclaimer']}；AI 说明只解释结构化研究产物。",
        "",
        f"- 状态：{payload['status']}",
        f"- Provider：{payload['provider']}",
        f"- 模型：{payload['model'] or '-'}",
    ]
    if payload.get("reason"):
        lines.append(f"- 原因：{payload['reason']}")
    lines.extend(["", "## 内容", "", payload.get("content") or "未生成 AI 内容。", ""])
    return "\n".join(lines)


def write_ai_report_payload(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_ai_report_markdown(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ai_report_markdown(payload), encoding="utf-8")
    return path
