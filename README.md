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
- [测试与质量门禁](docs/testing.md)
- [开源参考](docs/open-source-references.md)
- [模型策略](docs/model-strategy.md)

## 本地开发

当前代码处于离线研究闭环样例阶段，已提供配置、数据目录、DuckDB 备份工具、样例行情、基础因子、技术指标因子、未来 5 日标签、baseline 预测排名和 Top N 回测能力。

```bash
make ci-local
```

默认安装不强制包含 LightGBM；需要验证真实模型训练环境时可额外安装：

```bash
python3 -m pip install -e ".[modeling]"
```

训练入口默认读取 `MODEL_TYPE=lightgbm`，当前未安装 LightGBM 时会显式降级为
`rule_baseline_fallback`；如只想运行规则模型，可设置 `MODEL_TYPE=rule_baseline`。

`make ci-local` 会运行 Python lint、Python format check、后端测试、端到端 smoke 验收和前端构建；这些检查与 GitHub Actions 的 `main` push 和 pull request 门禁保持一致。

本地 API 可用于无页面验收：

```bash
python3 scripts/serve_api.py --host 127.0.0.1 --port 8765
```

可用端点：

- `GET /api/health`
- `GET /api/settings`
- `GET /api/status`
- `GET /api/acceptance`
- `GET /api/artifacts`
- `GET /api/pipeline`
- `GET /api/tasks`
- `GET /api/tasks/pipeline-latest`
- `GET /api/data/status`
- `GET /api/storage/duckdb`
- `GET /api/data-quality`
- `GET /api/features`
- `GET /api/labels`
- `GET /api/training-samples`
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
- `POST /api/data/update`
- `POST /api/models/train`
- `POST /api/predictions/run`
- `POST /api/backtests/run`
- `POST /api/reports/generate`

`GET /api/predictions` 支持 `date`、`model_version` 和 `top_n` 查询参数，用于复现指定交易日和模型版本下的 Top N 预测排名；响应中会返回 `available_dates` 和 `model_versions` 供页面筛选。

`GET /api/backtests/{backtest_id}` 会返回手续费率、成交价口径、持有期、调仓规则和标准化 `equity_curve`；曲线包含信号日、成交日、组合收益、基准收益、组合净值、基准净值和超额净值，便于核对回测口径。

`GET /api/status` 会返回当前离线研究链路的验收门禁，覆盖 pipeline、数据质量、DuckDB 镜像、预测结果和回测交易检查。

`GET /api/acceptance` 只返回验收门禁摘要，适合前端首屏、脚本或外部集成直接判断当前研究链路是否可用。

`GET /api/data/status` 会返回市场、样例股票池、v1 目标股票池、基准、复权口径和更新方式；其中会显式标注目标股票池与中证 800 基准同源。

`GET /api/artifacts` 返回本地研究产物清单、缺失项、文件大小和更新时间，适合无页面排查 pipeline 是否生成了完整可用的结果。

`POST /api/pipeline/run` 会同步执行当前离线研究链路；如果同一 API 进程内已有 pipeline 正在运行，会返回 `409` 和 `status=busy`，避免并发覆盖本地产物。

`POST /api/data/update`、`POST /api/models/train`、`POST /api/predictions/run`、`POST /api/backtests/run` 和 `POST /api/reports/generate` 是任务中心的细分触发入口。当前 MVP 为了保证样例数据、因子、标签、模型、预测、回测和报告口径一致，这些入口都会串行执行完整离线 pipeline，并在响应中返回 `requested_task` 与 `execution_mode=full_pipeline_refresh`。

最小研究看板位于 `frontend/`，默认通过 Vite 代理访问 `127.0.0.1:8765` 的 API：

```bash
cd frontend
npm install
npm run dev
```

当前前端包含工作台、验收、数据、任务、模型、预测、回测、单股、报告和设置视图。工作台会展示离线链路验收门禁摘要；验收视图会展示当前门禁检查项，并可直接触发 pipeline；数据视图会展示覆盖范围、质量门禁、DuckDB 表状态、异常明细、因子覆盖和标签覆盖，并区分可训练标签与未成熟标签；任务视图会展示最近 pipeline 的步骤明细，并可触发后端 `POST /api/pipeline/run`；模型视图会展示模型版本、训练区间、特征列表和本地产物信息；单股视图会展示股票池覆盖、样例标的价格、因子和历史预测；设置视图只展示 API key 是否配置，不展示密钥明文；所有预测、回测、单股和报告视图都保留研究用途声明。

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
- `data/processed/training_samples.csv`
- `data/models/baseline-rule-v1.json`
- `data/processed/latest_predictions.csv`
- `data/processed/historical_predictions.csv`
- `data/duckdb/swell_quant.duckdb`
- `data/reports/sample_backtest.json`
- `data/reports/sample_research_summary.md`
- `data/reports/pipeline_run.json`
- `data/reports/research_status.json`

当前模型是可复现的规则 baseline，用于验证链路，不是最终 LightGBM 模型。模型产物已经记录目标模型、实际训练后端、LightGBM 依赖状态、时间序列评估口径，包括 5 个交易日标签 gap、train/valid/test 评估窗口、基础收益/动量/波动率/RSI/MACD 因子和 baseline 测试指标，后续接入 LightGBM 时沿用同一元数据结构。

DuckDB 当前采用本地单文件模式，pipeline 会把 raw/features/labels/predictions CSV 产物整表镜像到
`data/duckdb/swell_quant.duckdb`。v1 只支持单写入者本地研究场景，镜像步骤使用覆盖写入，避免样例
数据重复追加。

`python3 scripts/check_storage.py` 会校验 DuckDB 表是否存在、字段是否匹配预期 schema，以及 DuckDB 行数是否和源 CSV 行数一致；状态不是 `healthy` 时返回非零退出码，可作为无页面验收或 CI 门禁。

`python3 scripts/check_acceptance.py` 会读取 `research_status.json` 中的验收门禁；未通过或尚未生成状态产物时返回非零退出码。

`python3 scripts/smoke_test.py` 会依次执行 pipeline、DuckDB 存储校验和验收门禁校验；任一环节失败都会返回非零退出码，适合作为本地端到端验收入口。

## 重要声明

本项目仅用于个人学习、研究和工程实验，不构成任何投资建议、交易建议或收益承诺。任何预测、回测、评分、报告和可视化结果都不能直接作为买入、卖出或持仓依据。

第一版不做自动交易，不接券商实盘接口，不提供下单能力。
