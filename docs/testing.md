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
4. `make smoke`：运行离线 pipeline，并校验 DuckDB 存储和研究验收门禁。
5. `make frontend-build`：运行前端 TypeScript 检查和 Vite 构建。

GitHub Actions 在 `main` push 和 pull request 上运行同等门禁。

## 分层检查

| 命令 | 覆盖范围 |
| --- | --- |
| `make pipeline` | 生成样例行情、质量报告、因子、标签、模型、预测、回测、DuckDB 镜像和研究报告。 |
| `make storage` | 校验 DuckDB 文件、表存在性、字段 schema、DuckDB 行数与 CSV 行数一致性。 |
| `make acceptance` | 校验研究状态里的 pipeline、数据质量、DuckDB、预测、回测和关键产物完整性门禁，并在状态快照中暴露产物大小与更新时间用于排查。 |
| `make smoke` | 串联 pipeline、storage 和 acceptance，作为无页面端到端验收入口。 |
| `make frontend-build` | 校验前端类型和生产构建。 |

## 关键测试覆盖

- 数据质量：重复日期、缺失价格、异常成交量和基础覆盖范围。
- 因子计算：滚动窗口只使用历史序列，避免未来函数。
- 标签生成：未来 5 日收益和基准收益使用 T+1 开盘到 T+5 收盘窗口，只作为监督标签，不进入同日特征。
- 模型 baseline：固定规则可复现，模型元数据写入特征列表、训练区间、5 个交易日标签 gap、评估窗口、测试指标和研究声明。
- 回测：Top N 调仓、次日开盘价成交、手续费、滑点、停牌、涨停买入受限、无法成交原因、年化收益、最大回撤、夏普、胜率、换手率和确定性净值曲线。
- DuckDB 存储：CSV 镜像到本地单文件 DuckDB，检查表行数和 schema。
- 产物完整性：模型、预测、回测、报告、pipeline 运行记录和 DuckDB 文件都必须存在。
- API：本地只读 API 路由、pipeline 触发锁、列表和详情接口。
- 前端：构建检查覆盖页面类型、API 类型、验收页产物状态和生产 bundle。

## 当前边界

- v1 仍使用可复现样例数据，不代表真实 A 股全量数据采集已经完成。
- 当前模型是规则 baseline，不是最终 LightGBM 模型。
- 回测结果仅用于工程链路验证，不构成投资建议或收益承诺。
