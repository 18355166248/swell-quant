# 模型策略

## 总原则

核心预测不用 LLM。股票预测分数、未来收益估计、Top N 排名必须来自可回测的机器学习模型或规则模型。

LLM 的职责是：

- 解释模型输出。
- 总结回测结果。
- 生成研究报告。
- 辅助阅读财报、新闻和公告。
- 帮助研究因子和改进实验设计。

LLM 不负责：

- 直接判断买入或卖出。
- 直接生成预测收益率。
- 替代回测。
- 绕过数据质量和风控检查。

## 开发阶段模型

开发主力使用 Codex + GPT-5.5。

适用任务：

- 项目架构设计。
- 后端和前端实现。
- 数据 pipeline、训练 pipeline、回测逻辑开发。
- Debug、重构、测试补齐。
- 复杂技术方案评审。

理由：

- Codex 官方推荐大多数 Codex 任务从 `gpt-5.5` 开始。
- `gpt-5.5` 适合复杂编码、电脑使用、知识工作和研究流程。
- 本项目涉及数据、模型、回测、前端和 AI 报告，属于多步骤复杂工程。

## 产品内 LLM 路由

建议封装统一 `LLMProvider`：

```txt
LLMProvider
  ├── OpenAIProvider
  │   └── gpt-5.5
  └── DeepSeekProvider
      ├── deepseek-v4-flash
      └── deepseek-v4-pro
```

默认路由：

| 任务 | 推荐模型 |
| --- | --- |
| 简单日报 | deepseek-v4-flash |
| 批量股票摘要 | deepseek-v4-flash |
| 回测结果解释 | deepseek-v4-pro |
| 复杂金融报告 | deepseek-v4-pro |
| 策略风险复盘 | deepseek-v4-pro 或 gpt-5.5 |
| 高价值研究任务 | gpt-5.5 |
| DeepSeek 失败回退 | gpt-5.5 |

## DeepSeek API 策略

DeepSeek V4 用于产品内低成本和长上下文任务。

推荐：

- `deepseek-v4-flash`：低成本批量摘要、日报、普通解释。
- `deepseek-v4-pro`：复杂报告、长上下文金融文本分析、回测复盘。

接入方式：

- 使用 OpenAI-compatible API。
- `base_url=https://api.deepseek.com`
- API key 只通过环境变量注入，不写入代码和文档正文。

## 报告输入约束

AI 报告服务只能读取结构化结果：

- 数据更新时间和数据覆盖范围。
- 模型版本、训练区间、验证区间、测试区间。
- Top N 预测结果。
- 回测指标。
- 因子重要性。
- 风险提示和数据质量问题。

报告必须避免：

- 编造未提供的数据。
- 输出确定性收益承诺。
- 输出“必涨”“必跌”等绝对判断。
- 把回测收益包装成未来收益。

## 降级策略

- 没有 LLM API key：返回规则化摘要。
- LLM 调用失败：记录错误，核心预测和回测继续可用。
- 报告内容校验失败：展示结构化指标，不展示 AI 文本。
- 高价值任务失败：允许从 DeepSeek 回退到 GPT-5.5。

## 后续与 swell-lobster 集成

后续可以为本项目提供 MCP server 或 HTTP API，让 `swell-lobster` 调用：

- 更新行情数据。
- 触发模型训练。
- 运行回测。
- 获取最新预测。
- 生成 AI 报告。

集成时，`swell-lobster` 只作为 Agent 工作台和任务入口，不复制本项目的数据、模型和回测逻辑。
