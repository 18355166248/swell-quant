# 测试与质量门禁

本文档记录当前阶段已经落地的本地检查、CI 门禁和重点测试覆盖范围。所有检查只用于研究系统工程质量，不代表任何投资收益或交易可行性。

## 一键门禁

提交前优先运行：

```bash
make ci-local
```

`make ci-local` 会依次执行：

1. `make lint`：`ruff check .`，检查 Python 静态问题。
2. `make format-check`：`ruff format --check .`，检查 Python 格式。
3. `make test`：`python3 -m pytest`，运行后端单元和集成测试。
4. `make config`：输出配置预检，检查数据源、股票池、日期区间和本地路径。
5. `make akshare-universe`：验证当前 AKShare 股票池模式能解析出可用标的；默认 manual 模式不联网，`csi800` 模式用于真实数据源前置验收。
6. `make smoke`：运行离线 pipeline，并校验 DuckDB 存储和研究验收门禁。
7. `make data-source`：检查最新数据采集元数据，暴露限量试跑和单标的采集失败 warning。
8. `make akshare-trial-dry-run`：预演真实 AKShare 小规模试跑并写入 dry-run 摘要，不访问外部数据源。
9. `make akshare-trial-status`：检查最近一次试跑摘要是否可读且通过。
10. `make progress`：输出阶段 0 到阶段 6 的完成度，确认当前进度证据仍可计算。
11. `make frontend-test`：`npm test`，运行前端单元测试。
12. `make frontend-build`：运行前端 TypeScript 检查和 Vite 构建。

GitHub Actions 在 `main` push 和 pull request 上运行同等门禁。

## 分层检查

| 命令 | 覆盖范围 |
| --- | --- |
| `make pipeline` | 生成样例行情、质量报告、因子、标签、模型、预测、回测、DuckDB 镜像和研究报告。 |
| `make config` | 校验本地数据源、股票池、AKShare 日期区间、DuckDB 路径和 LLM 配置风险。 |
| `make akshare-universe` | 校验 AKShare 股票池解析；目标股票池模式下要求解析数量达到最低门槛。 |
| `make akshare-trial` | 使用 csi800 股票池和 20 只标的上限串联真实 AKShare 小规模试跑、数据源门禁、总验收和进度检查，并写入 `data/reports/akshare_trial_run.json`。 |
| `make akshare-trial-dry-run` | 预演真实试跑步骤并写入 dry-run 摘要，不访问 AKShare。 |
| `make akshare-trial-status` | 只读检查最近一次真实 AKShare 试跑摘要，缺少或失败时返回非零。 |
| `make data-source` | 校验 `data/raw/data_source.json`，区分通过、warning 和阻断失败。 |
| `make progress` | 汇总阶段 0 到阶段 6 的完成度、当前阶段和每阶段证据计数。 |
| `make storage` | 校验 DuckDB 文件、表存在性、字段 schema、DuckDB 行数与 CSV 行数一致性。 |
| `make acceptance` | 校验研究状态里的 pipeline、数据质量、DuckDB、训练样本切分、预测、回测和关键产物完整性门禁，并在状态快照中暴露产物大小与更新时间用于排查。 |
| `make smoke` | 串联 pipeline、storage 和 acceptance，作为无页面端到端验收入口。 |
| `make frontend-test` | 校验前端共享展示工具、图表配置、表格列构造器、PageTitle 和页面级 render 测试，避免页面拆分时展示口径漂移。 |
| `make frontend-build` | 校验前端类型和生产构建。 |

## 关键测试覆盖

- 数据质量：重复日期、缺失价格、异常成交量和基础覆盖范围。
- 因子计算：收益率、动量、均线、波动率、RSI 和 MACD 都只使用历史序列，避免未来函数。
- 标签生成：未来 5 日收益和基准收益使用 T+1 开盘到 T+5 收盘窗口，只作为监督标签，不进入同日特征。
- 模型 baseline：固定规则可复现，模型元数据写入特征列表、训练区间、5 个交易日标签 gap、评估窗口、测试指标和研究声明。
- 训练样本：状态快照校验训练/验证/测试切分都非空，并暴露样本规模、正负样本比例和特征缺失计数。
- 回测：Top N 调仓、次日开盘价成交、手续费、滑点、停牌、涨停买入受限、无法成交原因、年化收益、最大回撤、逐期回撤曲线、相对基准曲线、夏普、胜率、换手率和确定性净值曲线。
- DuckDB 存储：CSV 镜像到本地单文件 DuckDB，检查表行数和 schema。
- 产物完整性：模型、预测、回测、报告、pipeline 运行记录和 DuckDB 文件都必须存在。
- API：本地只读 API 路由、pipeline 触发锁、列表和详情接口。
- 前端：Vitest 覆盖共享展示工具的数字/时间格式化、状态颜色映射和交易拒绝原因展示；图表配置覆盖预测分数、净值、回撤、相对收益、单股行情和因子走势；表格列构造器覆盖预测、验收检查、产物、任务和模型列表列；PageTitle 覆盖页面标题、说明和操作区渲染；页面级 render 测试覆盖研究用途声明、空状态、关键表格列标题稳定，以及设置页不展示 secret 明文；构建检查覆盖页面类型、API 类型和生产 bundle。

## 当前边界

- v1 仍使用可复现样例数据，不代表真实 A 股全量数据采集已经完成。
- 默认模型会尝试 LightGBM；未安装可选依赖时显式降级到规则 baseline。
- 回测结果仅用于工程链路验证，不构成投资建议或收益承诺。
