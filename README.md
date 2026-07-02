# Swell Quant

Swell Quant 是一个面向个人研究的 A 股日频 AI 量化预测工具。第一版目标是做成研究看板：拉取历史行情、构建基础因子、训练 LightGBM 模型、做 Top N 回测，并用 LLM 生成研究解释报告。

本项目与 `swell-lobster` 独立。`swell-lobster` 可以在后续通过 MCP 或 HTTP API 调用本项目的研究能力，但不承载量化核心代码。

## v1 目标

- A 股日频数据采集与增量更新。
- 基础技术因子与未来 5 日收益标签。
- LightGBM 预测模型与时间序列切分训练。
- Top N 股票组合回测与基准对比。
- Web 研究看板展示预测、回测、因子重要性和 AI 报告。
- LLM 只做解释、总结和研究辅助，不直接预测涨跌。

## 快速阅读

- [项目计划](docs/plan.md)
- [架构设计](docs/architecture.md)
- [开源参考](docs/open-source-references.md)
- [模型策略](docs/model-strategy.md)

## 本地开发

当前代码处于阶段 0/1 骨架阶段，已提供配置、数据目录、DuckDB 备份工具和离线 pipeline 入口。

```bash
python3 scripts/run_pipeline.py
python3 -m pytest
```

`scripts/run_pipeline.py` 现在会创建数据目录、执行数据更新占位步骤，并明确跳过尚未实现的因子、标签、训练和回测阶段。

## 重要声明

本项目仅用于个人学习、研究和工程实验，不构成任何投资建议、交易建议或收益承诺。任何预测、回测、评分、报告和可视化结果都不能直接作为买入、卖出或持仓依据。

第一版不做自动交易，不接券商实盘接口，不提供下单能力。
