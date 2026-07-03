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

当前代码处于离线研究闭环样例阶段，已提供配置、数据目录、DuckDB 备份工具、样例行情、AKShare 可选采集适配、基础因子、技术指标因子、未来 5 日标签、baseline/LightGBM 可选训练、预测排名和 Top N 回测能力。

首次运行可以先复制本地配置模板，再按需调整数据源、股票池、模型和 LLM 开关：

```bash
cp .env.example .env
```

```bash
make ci-local
```

也可以单独运行配置预检，提前发现本地数据源、股票池、日期区间或 LLM 配置风险：

```bash
make config
```

验证 AKShare 股票池解析：

```bash
make akshare-universe
```

查看当前阶段进度：

```bash
make progress
```

默认安装不强制包含 LightGBM；需要验证真实模型训练环境时可额外安装：

```bash
python3 -m pip install -e ".[modeling]"
```

默认数据源是可复现样例数据；需要尝试真实 AKShare 日频采集时可额外安装并切换：

```bash
python3 -m pip install -e ".[data]"
DATA_SOURCE=akshare \
AKSHARE_UNIVERSE_MODE=manual \
AKSHARE_SYMBOLS=000001.SZ,600000.SH \
AKSHARE_START_DATE=20240102 \
AKSHARE_END_DATE=20240229 \
python3 scripts/run_pipeline.py
```

当前 `AKSHARE_UNIVERSE_MODE=manual` 表示使用 `AKSHARE_SYMBOLS` 手工股票池，适合小范围连通性验证。要使用 v1 目标股票池，可设置 `AKSHARE_UNIVERSE_MODE=csi800` 或别名 `hs300_csi500`，pipeline 会在运行时通过 AKShare 拉取沪深 300 + 中证 500 成分股，再按同一行情 CSV 契约进入因子、标签、训练和回测链路；非法股票代码、非法日期区间或未支持的股票池模式会在配置加载阶段直接报错。

```bash
DATA_SOURCE=akshare \
AKSHARE_UNIVERSE_MODE=csi800 \
AKSHARE_START_DATE=20240102 \
AKSHARE_END_DATE=20240229 \
python3 scripts/check_akshare_universe.py
```

目标股票池解析通过后，再运行 `python3 scripts/run_pipeline.py` 拉取行情并复跑完整离线链路。

首次连接真实 AKShare 时建议先限制标的数量做小规模试跑：

```bash
make akshare-trial
```

该命令等价于用 `DATA_SOURCE=akshare`、`AKSHARE_UNIVERSE_MODE=csi800`、`AKSHARE_MAX_SYMBOLS=20`、`AKSHARE_START_DATE=20240102`、`AKSHARE_END_DATE=20240131` 依次执行配置预检、股票池解析、pipeline、数据源门禁、总验收和进度检查，并把试跑摘要写入 `data/reports/akshare_trial_run.json`。需要先确认计划命令时可运行 `python3 scripts/run_akshare_trial.py --dry-run`；需要调整范围时可使用 `--max-symbols`、`--start-date` 和 `--end-date`。

真实 AKShare 采集会按标的记录成功和失败摘要；单只股票临时失败时，pipeline 会继续处理已成功获取的标的，并把 `succeeded_symbol_count`、`failed_symbol_count` 和 `failed_symbols` 写入 `data/raw/data_source.json`。
跑完真实行情后建议执行 `python3 scripts/check_data_source.py` 或 `make data-source`。该检查会把限量试跑和单标的采集失败标为 warning，只有缺少元数据或没有成功标的时才阻断。

训练入口默认读取 `MODEL_TYPE=lightgbm`，当前未安装 LightGBM 时会显式降级为
`rule_baseline_fallback`；如只想运行规则模型，可设置 `MODEL_TYPE=rule_baseline`。

AI 报告默认通过 `LLM_PROVIDER=disabled` 关闭，核心 pipeline 不依赖 LLM。需要尝试 DeepSeek 生成 AI 说明时设置：

```bash
LLM_PROVIDER=deepseek DEEPSEEK_API_KEY=... python3 scripts/run_pipeline.py
```

`.env.example` 会列出当前支持的全部本地环境变量。API key 只能通过本地环境变量或未提交的 `.env` 注入，不要写入代码、文档正文或提交记录。

`make ci-local` 会运行 Python lint、Python format check、后端测试、端到端 smoke 验收、数据源元数据检查和前端构建；这些检查与 GitHub Actions 的 `main` push 和 pull request 门禁保持一致。

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
- `GET /api/progress`
- `GET /api/pipeline`
- `GET /api/tasks`
- `GET /api/tasks/pipeline-latest`
- `GET /api/data/status`
- `GET /api/akshare/universe`
- `GET /api/akshare/trial`
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

`GET /api/akshare/universe` 会返回当前 AKShare 股票池解析门禁状态；manual 模式检查手工标的，`csi800` / `hs300_csi500` 模式会尝试解析沪深 300 + 中证 500 成分股，只用于研究链路前置验收。

`GET /api/artifacts` 返回本地研究产物清单、缺失项、文件大小和更新时间，适合无页面排查 pipeline 是否生成了完整可用的结果。

`GET /api/progress` 返回阶段 0 到阶段 6 的完成度、当前阶段和每个阶段的产物证据，用于回答当前开发进度到哪。

`GET /api/settings` 会返回本地路径、运行模式、非敏感数据源配置、API key 是否配置，以及运行前预检结果；预检只暴露阻塞项和风险提示，不返回任何 secret 明文。

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
- `data/models/latest_model.json`
- `data/models/lightgbm-v1.txt`（安装 LightGBM 且默认模型训练成功时生成）
- `data/processed/latest_predictions.csv`
- `data/processed/historical_predictions.csv`
- `data/duckdb/swell_quant.duckdb`
- `data/reports/sample_backtest.json`
- `data/reports/sample_research_summary.md`
- `data/reports/sample_research_summary.json`
- `data/reports/sample_ai_research_summary.md`
- `data/reports/sample_ai_research_summary.json`
- `data/reports/pipeline_run.json`
- `data/reports/research_status.json`

训练入口默认尝试 LightGBM；未安装可选依赖时会显式降级到可复现规则 baseline。模型产物会写入 `latest_model.json` 作为报告、状态和页面的稳定入口，并记录目标模型、实际训练后端、LightGBM 依赖状态、特征重要性、时间序列评估口径，包括 5 个交易日标签 gap、train/valid/test 评估窗口、基础收益/动量/波动率/RSI/MACD 因子和测试指标。

DuckDB 当前采用本地单文件模式，pipeline 会把 raw/features/labels/predictions CSV 产物整表镜像到
`data/duckdb/swell_quant.duckdb`。v1 只支持单写入者本地研究场景，镜像步骤使用覆盖写入，避免样例
数据重复追加。

`python3 scripts/check_storage.py` 会校验 DuckDB 表是否存在、字段是否匹配预期 schema，以及 DuckDB 行数是否和源 CSV 行数一致；状态不是 `healthy` 时返回非零退出码，可作为无页面验收或 CI 门禁。

`python3 scripts/check_config.py` 会输出本地配置预检 JSON；配置非法时返回非零，警告项只提示不阻塞，适合无页面排查。

`python3 scripts/check_progress.py` 会输出阶段 0 到阶段 6 的完成度、当前阶段、下一步建议和每个阶段的证据计数；加 `--json` 可获取完整结构化进度。

`python3 scripts/check_acceptance.py` 会读取 `research_status.json` 中的验收门禁；未通过或尚未生成状态产物时返回非零退出码。

`python3 scripts/smoke_test.py` 会依次执行 pipeline、DuckDB 存储校验和验收门禁校验；任一环节失败都会返回非零退出码，适合作为本地端到端验收入口。

## 重要声明

本项目仅用于个人学习、研究和工程实验，不构成任何投资建议、交易建议或收益承诺。任何预测、回测、评分、报告和可视化结果都不能直接作为买入、卖出或持仓依据。

第一版不做自动交易，不接券商实盘接口，不提供下单能力。
