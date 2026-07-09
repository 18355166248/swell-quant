# Swell Quant 使用教程

本文说明如何在本机生成数据、启动后台、打开研究看板，并查看“可关注 / 需复核 / 暂缓观察”的研究动作分层。

> 所有输出仅用于研究，不构成投资建议。系统不会输出买入、卖出、仓位、目标价或收益承诺。

## 1. 第一次准备

在仓库根目录执行：

```bash
cp .env.example .env
```

安装依赖按本机环境选择；如果已经能运行 `make ci-local`，可以跳过。

```bash
python3 -m pip install -e ".[data,modeling]"
cd frontend
npm install
cd ..
```

默认模型目标是 LightGBM；如果本机没有安装 LightGBM，pipeline 会自动降级为规则 baseline，并在模型元数据里标记 `rule_baseline_fallback`。

## 2. 生成研究数据

### 样例数据

最快验证整条链路：

```bash
make pipeline
make acceptance
```

这会生成本地样例行情、因子、标签、模型、预测、回测、报告和状态产物。

### 真实 AKShare 小规模试跑

第一次看真实行情建议用 20 只标的小规模试跑：

```bash
make akshare-trial
```

试跑完成后检查：

```bash
make akshare-trial-status
make data-source
make acceptance
```

关键判断：

- `real_data_verified=true`：真实行情试跑已通过。
- `acceptance_status=passed`：研究链路门禁通过。
- `data_source_status=warning` 仍可能可用；通常表示部分标的失败或启用了 `AKSHARE_MAX_SYMBOLS` 试跑上限。

### 基金真实数据试跑

基金模块目前把真实数据试跑和样例候选分开，避免网络失败或半成品数据污染样例页面：

```bash
make fund-trial-dry-run
FUND_SYMBOLS=510300,159915 FUND_START_DATE=20250101 FUND_END_DATE=20260708 make fund-trial
make fund-trial-status
```

关键判断：

- `real_data_verified=true`：基金净值真实试跑通过。
- `status=failed`：数据源、网络或字段解析失败；打开 `data/reports/fund_trial_run.json` 看 `steps[].error`。
- 当前只验证公开基金净值和基础名称信息，基金经理、持仓、行业暴露和费用细项仍需人工补充复核。

## 3. 启动后台 API

后台只读本地 `data/` 产物，不会自动下单，也不会连接券商。

```bash
python3 scripts/serve_api.py --host 127.0.0.1 --port 8765
```

健康检查：

```bash
curl http://127.0.0.1:8765/api/health
```

直接查看研究动作分层：

```bash
curl "http://127.0.0.1:8765/api/research-candidates/latest?top_n=10"
```

重点字段：

- `readiness.status`：研究链路门禁是否通过。
- `candidates[].research_action.label`：`可关注`、`需复核` 或 `暂缓观察`。
- `candidates[].research_action.reasons`：为什么进入这个分层。
- `candidates[].research_action.blockers`：还需要人工复核的问题。
- `candidates[].history`：同标的历史成熟样本回看，不代表未来表现。
- `disclaimer`：研究用途声明。

查看每日研究简报：

```bash
curl "http://127.0.0.1:8765/api/daily-brief"
```

重点字段：

- `status`：`ready` 表示简报依赖产物基本可读，`partial` 表示有缺失或关键产物不完整。
- `stocks.action_summary`：股票候选在 `可关注 / 需复核 / 暂缓观察` 三层中的数量。
- `funds.source.source_kind`：基金候选来自真实试跑产物还是样例数据。
- `review_items`：当天优先复核的问题清单。
- `next_actions`：后台建议的下一步研究动作；带 `task` 的动作可由前端触发现有 pipeline 任务，不带 `task` 的动作需要人工执行或复核。
- `access_issues`：简报读取失败的产物或原因。

查看基金候选和买前验证项：

```bash
curl "http://127.0.0.1:8765/api/funds/candidates?profile=balanced"
```

重点字段：

- `source.source_kind`：`real_data` 表示来自基金真实试跑产物，`sample` 表示已回退样例数据。
- `source.latest_nav_date` / `source.freshness`：最新净值日期和距今天多久，过期数据不能作为真实研究依据。
- `source.warning`：真实基金产物不完整时的回退原因。
- `candidates[].verification_label`：`可进入人工复核`、`需补充验证` 或 `暂不适合决策`。
- `candidates[].verification_checks`：收益、回撤、波动、费用、规模等检查摘要。
- `candidates[].verification_blockers`：样例数据、基金合同、费用口径、个人风险偏好等待补充问题。

查看基金真实数据试跑状态：

```bash
curl "http://127.0.0.1:8765/api/funds/trial"
```

重点字段：

- `env.FUND_SYMBOLS`：本次试跑基金代码。
- `steps[].succeeded_count` / `steps[].failed_count`：成功和失败数量。
- `steps[].error`：数据源失败原因。
- `real_data_verified`：是否已经有真实数据通过记录。

## 4. 启动前端看板

另开一个终端：

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 4173
```

浏览器打开：

```text
http://127.0.0.1:4173/
```

前端默认代理到 `127.0.0.1:8765` 的后台 API。

菜单现在对应独立路由，可以直接打开：

- 工作台：`http://127.0.0.1:4173/dashboard`
- 数据：`http://127.0.0.1:4173/data`
- 预测：`http://127.0.0.1:4173/predictions`
- 回测：`http://127.0.0.1:4173/backtests`
- 报告：`http://127.0.0.1:4173/reports`

## 5. 页面怎么看

### 工作台

先看链路是否可用：

- Pipeline 状态是否成功。
- 验收门禁是否通过。
- 数据行数、模型版本、回测摘要是否存在。

### 数据页

看当前数据来源和质量：

- 数据源健康中心：先看 A 股行情、数据新鲜度、DuckDB、股票真实试跑、基金真实试跑和关键产物是否正常。
- `data_source=sample`：样例数据，只能验证工程链路。
- `data_source=akshare`：真实 AKShare 数据。
- 成功标的数、失败标的数、质量等级和 warning。
- 数据新鲜度：如果显示“数据过期”，先更新数据，不要把旧数据当成当前市场。

### 预测页

这是看“小建议”的主页面。

重点看“研究参考清单”：

- `研究动作=可关注`：模型相对分数高、未触发启发式风险、历史成熟样本没有明显劣化。仍需人工复核。
- `研究动作=需复核`：模型分数可能靠前，但存在历史表现偏弱、样本不足、风险提示或门禁问题。
- `研究动作=暂缓观察`：相对置信度低，或核心门禁失败。
- 研究候选解释：点表格行查看该标的的分层理由、阻塞项、因子依据、风险提示、历史回看和复核清单。

不要只看排名。优先同时看：

- 相对置信度。
- 因子归因。
- 启发式风险。
- 历史回看。
- 研究动作里的 blockers。

### 回测页

检查历史回测是否可复现：

- 策略实验对比：先横向比较不同回测配置的累计收益、超额收益、最大回撤、胜率和换手。
- 回测区间。
- 累计收益、基准收益、超额收益。
- 最大回撤、胜率、换手率。
- 无法成交记录。

历史回测不代表未来收益。

### 基金页

基金页用于买基金前做研究框架校验，不输出申购、赎回、定投金额或仓位建议。

重点看：

- 数据来源：`真实试跑` 表示页面读取 `akshare_fund_*` 产物，`样例` 表示真实产物缺失或不完整。
- 最新净值日期：如果显示“数据过期”，先运行 `make fund-trial` 或检查 `make fund-trial-status`。
- 基金对比：一次选择 2-5 只，横向看近 1 年收益、最大回撤、波动率和总费率。
- 候选视图：稳健、均衡、进取三种排序。
- 研究分数：只用于候选排序，不代表收益预测。
- 基金详情：点候选行或在下拉框选基金，查看单只基金指标、净值走势和买前验证明细。
- 买前验证：优先看阻塞项，尤其是样例数据、基金合同、费用口径和个人风险偏好。

### 报告页

报告页会展示结构化研究摘要，并同步包含“研究动作分层摘要”。

- 每日研究简报：先看数据新鲜度、研究动作数量、基金候选、验收门禁和今日复核重点。
- 股票/基金候选：只汇总候选和验证状态，不代表买入、卖出、仓位或收益承诺。

如果 AI 报告关闭，报告仍会用规则化摘要输出核心结果。LLM 只做解释，不生成预测分数。

## 6. 常用命令

```bash
make config                 # 配置预检
make pipeline               # 按当前 .env 生成研究产物
make akshare-trial          # 真实 AKShare 20 只小规模试跑
make akshare-trial-status   # 查看最近真实试跑状态
make fund-trial             # 真实基金净值小规模试跑
make fund-trial-status      # 查看最近基金试跑状态
make data-source            # 查看数据源采集状态
make acceptance             # 查看研究链路门禁
make progress               # 查看阶段进度
make storage                # 检查 DuckDB 镜像
make frontend-build         # 前端构建检查
make ci-local               # 全量本地质量门禁
```

注意：`make ci-local` 默认会跑样例链路和 dry-run 检查。如果你刚跑完真实 AKShare 试跑，又想保留真实试跑产物用于页面查看，不要立刻用默认 `make pipeline` 覆盖回样例数据。

## 7. 直接看本地产物

常用文件：

- `data/reports/research_status.json`：总验收状态。
- `data/reports/pipeline_run.json`：最近 pipeline 步骤。
- `data/raw/data_source.json`：数据源、股票池、成功/失败标的。
- `data/processed/latest_predictions.csv`：最新预测排名。
- `data/processed/historical_predictions.csv`：历史预测。
- `data/reports/sample_backtest.json`：回测结果。
- `data/reports/sample_research_summary.md`：可读研究报告。
- `data/reports/sample_research_summary.json`：结构化报告 payload。
- `data/reports/akshare_trial_run.json`：AKShare 真实试跑摘要。
- `data/reports/fund_trial_run.json`：基金真实试跑摘要。

## 8. 常见问题

### 页面没有数据

先确认后台和产物：

```bash
make acceptance
python3 scripts/serve_api.py --host 127.0.0.1 --port 8765
curl http://127.0.0.1:8765/api/health
```

再启动前端：

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 4173
```

### 真实 AKShare 试跑失败

常见原因是网络、DNS、上游接口或代理问题。可以先看：

```bash
make akshare-trial-status
```

如果本机需要代理，可在 `.env` 或 shell 里设置：

```bash
AKSHARE_HTTP_PROXY=http://127.0.0.1:7897
```

### 为什么没有“可关注”

这是正常的保守行为。只有同时满足高相对置信度、未触发风险、历史成熟样本没有明显劣化、核心门禁通过，才会标记为 `可关注`。否则会落到 `需复核` 或 `暂缓观察`。

### 能不能当成投资建议

不能。这里的 `可关注` 只是研究复核优先级，不是买入建议。下单、仓位、目标价、止盈止损都不在本项目 v1 范围内。
