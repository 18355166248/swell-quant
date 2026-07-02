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
- [页面开发计划](docs/frontend-plan.md)
- [开源参考](docs/open-source-references.md)
- [模型策略](docs/model-strategy.md)

## 本地开发

当前代码处于离线研究闭环样例阶段，已提供配置、数据目录、DuckDB 备份工具、样例行情、基础因子、未来 5 日标签、baseline 预测排名和 Top N 回测能力。

```bash
python3 scripts/run_pipeline.py
python3 -m pytest
```

本地 API 可用于无页面验收：

```bash
python3 scripts/serve_api.py --host 127.0.0.1 --port 8765
```

可用端点：

- `GET /api/health`
- `GET /api/settings`
- `GET /api/status`
- `GET /api/pipeline`
- `GET /api/tasks`
- `GET /api/tasks/pipeline-latest`
- `GET /api/data/status`
- `GET /api/data-quality`
- `GET /api/models`
- `GET /api/models/latest`
- `GET /api/models/{model_version}`
- `GET /api/predictions`
- `GET /api/predictions/latest`
- `GET /api/backtest/latest`
- `GET /api/backtests`
- `GET /api/backtests/latest`
- `GET /api/backtests/{backtest_id}`
- `GET /api/stocks`
- `GET /api/stocks/{symbol}`
- `GET /api/stocks/{symbol}/prices`
- `GET /api/stocks/{symbol}/features`
- `GET /api/stocks/{symbol}/predictions`
- `GET /api/report`
- `GET /api/reports`
- `GET /api/reports/latest`
- `GET /api/reports/{report_id}`
- `POST /api/pipeline/run`

`GET /api/predictions` 支持 `date`、`model_version` 和 `top_n` 查询参数，用于复现指定交易日和模型版本下的 Top N 预测排名；响应中会返回 `available_dates` 和 `model_versions` 供页面筛选。

`GET /api/backtests/{backtest_id}` 会返回标准化 `equity_curve`，包含信号日、成交日、组合收益、基准收益、组合净值、基准净值和超额净值，便于核对回测口径。

`POST /api/pipeline/run` 会同步执行当前离线研究链路；如果同一 API 进程内已有 pipeline 正在运行，会返回 `409` 和 `status=busy`，避免并发覆盖本地产物。

最小研究看板位于 `frontend/`，默认通过 Vite 代理访问 `127.0.0.1:8765` 的 API：

```bash
cd frontend
npm install
npm run dev
```

当前前端包含工作台、任务、预测、回测、单股、报告和设置视图。任务视图会展示最近 pipeline 的步骤明细，并可触发后端 `POST /api/pipeline/run`；单股视图会展示样例标的的价格、因子和历史预测；设置视图只展示 API key 是否配置，不展示密钥明文；所有预测、回测、单股和报告视图都保留研究用途声明。

前端构建检查：

```bash
cd frontend
npm run build
```

`scripts/run_pipeline.py` 现在会创建数据目录，并生成以下本地产物：

- `data/raw/sample_prices.csv`
- `data/processed/data_quality.json`
- `data/processed/sample_features.csv`
- `data/processed/sample_labels.csv`
- `data/models/baseline-rule-v1.json`
- `data/processed/latest_predictions.csv`
- `data/processed/historical_predictions.csv`
- `data/reports/sample_backtest.json`
- `data/reports/sample_research_summary.md`
- `data/reports/pipeline_run.json`
- `data/reports/research_status.json`

当前模型是可复现的规则 baseline，用于验证链路，不是最终 LightGBM 模型。

## 重要声明

本项目仅用于个人学习、研究和工程实验，不构成任何投资建议、交易建议或收益承诺。任何预测、回测、评分、报告和可视化结果都不能直接作为买入、卖出或持仓依据。

第一版不做自动交易，不接券商实盘接口，不提供下单能力。
