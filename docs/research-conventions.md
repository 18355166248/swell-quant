# 研究口径速查（面向 AI 检索）

写策略/跑实验前**先查本表再下笔**，不靠记忆瞎编参数。每条口径都给出代码出处，
有疑问以代码为准。所有研究产物仅用于研究，不构成投资建议。

## 数据口径

| 口径                | 规则                                                                                                                          | 出处                                |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| 取数原则            | 一切取数只经 `MarketStore` 的 `as_of` / point-in-time 接口，从底层杜绝未来函数                                                | `marketdata/store.py`               |
| 复权                | 库内只存原始价 + **起点锚定**复权因子（首日 = 1.0，对未来新分红不变）；后复权价为视图派生（`get_bars_hfq`）                   | `marketdata/adjust.py`              |
| 财务 knowledge_date | 不用东财“最新公告日期”（会破坏 PIT），用**报告期末 + 法定披露截止日**保守估计：Q1→4/30、半年报→8/31、Q3→10/31、年报→次年 4/30 | `marketdata/source_fundamentals.py` |
| 财务修正            | 财报修正是新的一行（不同 knowledge_date），历史保留；`get_fundamentals` 只取 as_of 当天可见的最新一条                         | `marketdata/store.py`               |
| ROE / 同比          | 百分数原值（10.57 表示 10.57%），非小数                                                                                       | `source_fundamentals.py`            |
| 成分股池            | `get_universe(index, as_of)`：按快照 + 每股纳入日期回放；回测按调仓日动态取池（抗幸存者偏差，退出侧仍依赖快照积累）           | `store.get_universe`                |
| 交易日              | 一律用 `store.trading_days` / `sample_as_of_dates`，不要自己按自然日推                                                        | `factors/evaluate.py`               |

## 因子口径

| 因子       | 定义                             | 参数              |
| ---------- | -------------------------------- | ----------------- |
| momentum   | lookback 日收益（后复权）        | lookback，默认 20 |
| reversal   | 短期反转（取负的近端收益）       | lookback，默认 5  |
| volatility | 收益波动率，**低波给负权重使用** | lookback，默认 20 |
| value      | 1 / 估值（如 1/PE_TTM）          | item，默认 pe_ttm |
| quality    | 财务指标原值（如 ROE）           | item，默认 roe    |

预处理可用原语：`winsorize_mad`（MAD 去极值）、`zscore`、`neutralize_against` /
`neutralize_by_group`（行业/市值中性化）。见 `factors/preprocess.py`。

## 回测口径

| 口径     | 规则                                                                                                                                           |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| 组合构建 | 综合打分 → Top-N 等权 → 持有 horizon 日；`rebalance_dates` 按 step=horizon 采样，避免持有期重叠                                                |
| 成本     | `cost_bps` 为单边费率（基点）；每期成本 = 换手率 × cost_bps/10000，从毛收益扣除；默认 10 bps                                                   |
| 基准     | 双基准二选一：`equal_weight`（等权全池，剥离等权 tilt，看**纯选股超额**）或 `index`（市值加权指数如 sh000300）。报告超额必须说明对的是哪个基准 |
| 动态池   | `universe_index` 非空时按调仓日取当时成分；等权基准用同一动态池，保持同池对照                                                                  |
| 年化     | periods_per_year = 252 / horizon                                                                                                               |

## 结论评估标准（findings 升级闸门）

一个因子/策略结论要从 `workspace/research-log/` 升入 `workspace/findings/`，
必须**三条同时满足**：

1. **样本外**：walk-forward 样本外 RankIC 均值显著异于 0（权重只由过去 IC 决定）；
2. **双基准**：对**等权全池**基准仍有正超额（只赢市值加权指数不算数）；
3. **样本量**：样本外验证期数 ≥ 30，且跨越至少两种市场状态（牛/熊/震荡任二）。

附加纪律：试过的所有因子/参数组合必须全部记录在 research-log（防多重检验
p-hacking）；禁止只报样本内数字。

## 入口

- CLI：`swell-quant data|factor|backtest ...`（JSON 输出，见 `src/swell_quant/cli.py`）
- HTTP：只读 FastAPI bridge（`src/swell_quant/api/server.py`）
- 两者共享 `src/swell_quant/service.py`，口径一致。
