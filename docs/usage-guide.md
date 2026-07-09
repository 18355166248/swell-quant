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

- `data_source=sample`：样例数据，只能验证工程链路。
- `data_source=akshare`：真实 AKShare 数据。
- 成功标的数、失败标的数、质量等级和 warning。

### 预测页

这是看“小建议”的主页面。

重点看“研究参考清单”：

- `研究动作=可关注`：模型相对分数高、未触发启发式风险、历史成熟样本没有明显劣化。仍需人工复核。
- `研究动作=需复核`：模型分数可能靠前，但存在历史表现偏弱、样本不足、风险提示或门禁问题。
- `研究动作=暂缓观察`：相对置信度低，或核心门禁失败。

不要只看排名。优先同时看：

- 相对置信度。
- 因子归因。
- 启发式风险。
- 历史回看。
- 研究动作里的 blockers。

### 回测页

检查历史回测是否可复现：

- 回测区间。
- 累计收益、基准收益、超额收益。
- 最大回撤、胜率、换手率。
- 无法成交记录。

历史回测不代表未来收益。

### 报告页

报告页会展示结构化研究摘要，并同步包含“研究动作分层摘要”。

如果 AI 报告关闭，报告仍会用规则化摘要输出核心结果。LLM 只做解释，不生成预测分数。

## 6. 常用命令

```bash
make config                 # 配置预检
make pipeline               # 按当前 .env 生成研究产物
make akshare-trial          # 真实 AKShare 20 只小规模试跑
make akshare-trial-status   # 查看最近真实试跑状态
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
