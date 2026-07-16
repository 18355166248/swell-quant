# Swell Quant

A-share 多因子量化研究系统（个人自建）。从数据采集到因子评估、组合回测、样本外验证，
一条完整、可测、可信的研究链路。设计目标不是"跑出漂亮回测"，而是**能诚实地告诉你一个
信号到底有没有用**。

## 架构

三个独立的包，数据向上单向流动：

```
marketdata → factors → portfolio
（数据层）    （因子层）  （组合/回测层）
```

- **`swell_quant.marketdata`** — 数据层
  - 采集：行情（新浪，后复权因子起点锚定）、财务（东财业绩报表，knowledge_date 用法定披露截止日保守估计）、估值（百度）、指数、成分股快照、交易日历。
  - 存储：`MarketStore`（DuckDB），只存客观事实，后复权价为视图派生；`as_of` / point-in-time 查询，从底层杜绝未来函数。
  - 采集服务：增量、单标的失败隔离、`ingestion_log` 审计。
  - 设计与决策记录见 [docs/data-module-decisions.md](docs/data-module-decisions.md)。

- **`swell_quant.factors`** — 因子层
  - 因子：动量、价值、波动率、质量/成长；统一 `Factor` 接口，只经 `as_of` 取数。
  - 预处理：MAD 去极值、z-score 标准化。
  - 合成：多因子加权打分。
  - 评估：单期与多期 IC / RankIC、IC 信息比率、胜率。

- **`swell_quant.portfolio`** — 组合与回测
  - Top-N 等权组合、净值曲线、交易成本（换手率驱动）。
  - 基准对照：市值加权指数 **与** 等权全池（后者剥离等权 tilt，隔离纯选股超额）。
  - 超额收益、信息比率、年化收益/夏普、最大回撤。
  - **walk-forward 样本外验证**：权重只由过去 IC 决定，回答"edge 是真是假"。

## 安装

```bash
python -m pip install -e '.[dev]'      # 核心 + 测试
python -m pip install -e '.[dev,data]' # 需要真实采集（akshare）时再加 data
```

需要 Python ≥ 3.11。存储引擎 DuckDB 为核心依赖，测试用内存库、不依赖网络。

## 快速上手

```python
from datetime import date
from swell_quant.marketdata import MarketStore, collect_bars
from swell_quant.factors import MomentumFactor, sample_as_of_dates
from swell_quant.portfolio import walk_forward_backtest
import akshare as ak

with MarketStore("data/duckdb/marketdata.duckdb") as store:
    collect_bars(["600519", "000001"], store, ak,
                 default_start="20240101", end_date="20241231")
    dates = sample_as_of_dates(store, date(2024, 3, 1), date(2024, 12, 1), step=20)
    result = walk_forward_backtest([MomentumFactor(20)], store, ["600519", "000001"],
                                   dates, train_size=6, top_n=1, horizon=20)
    print(result.total_return, result.information_ratio)
```

**完整端到端流程**（建库/采集 → 因子 → IC 评估 → 带动态池/基准/成本的回测）见
[docs/usage-guide.md](docs/usage-guide.md)。

## CLI（面向 AI/脚本，JSON 输出）

```bash
swell-quant data summary                          # 库内数据概览
swell-quant data bars --symbols 600519 --as-of 2024-12-31 --lookback 20 --adjust hfq
swell-quant data trade-days --start 2024-01-01 --end 2024-03-01
swell-quant factor ic --name momentum --start 2024-03-01 --end 2024-12-01
swell-quant backtest --factors '[{"name":"momentum","lookback":20}]' \
  --start 2024-03-01 --end 2024-12-01
```

CLI 与只读 HTTP API 共享 `swell_quant.service` 服务层，口径一致；数据全部走
`MarketStore` 的 as_of / point-in-time 接口。研究口径速查见
[docs/research-conventions.md](docs/research-conventions.md)，研究工作台
（偏好宪法 / 研究日志 / 结论库）见 [workspace/](workspace/preferences.md)。

## 一个诚实的研究结论

用 100 只沪深300 成分、2016–2026、90 个样本外期做过完整验证：

- 四个简单因子（动量/低波/质量/成长）**全样本 RankIC ≈ 0**——没有可信的选股 alpha。
- 样本内回测的天文收益（+17323%）是**幸存者偏差 + 样本内拟合**的假象。
- 对等权全池基准，因子选股的超额**为负**——所谓"跑赢沪深300"全部来自等权 tilt。

系统的价值正在于**它能把这些偏差诚实地暴露出来**，而不是用漂亮数字骗人。要继续找真
alpha，路线是：修幸存者偏差（定期成分股快照）+ 中性化 + 更强因子。

## 开发

```bash
make test          # pytest
make lint          # ruff check
make format-check  # ruff format --check
```
