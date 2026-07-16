# 使用指南

一条完整研究链路怎么跑：**建库/采集 → 因子 → IC 评估 → 回测**。所有函数只经
`MarketStore` 的 as_of 接口取数，天然无未来函数。真实采集需要 akshare
（`pip install -e '.[dev,data]'`）；纯计算/测试只需 duckdb。

> 约定：`store` 为 `MarketStore` 实例；`ak` 为 `import akshare as ak`；示例用沪深300。

## 0. 打开一个库

```python
from swell_quant.marketdata import MarketStore
store = MarketStore("data/duckdb/marketdata.duckdb")  # 文件库；测试用 ":memory:"
# ... 用完 store.close()，或用 with MarketStore(path) as store: ...
```

## 1. 一次性/定期设置：日历 + 指数 + 成分股快照

回测的动态股票池、基准、交易日采样都依赖这三样，先备好。

```python
from datetime import date
from swell_quant.marketdata import (
    fetch_trade_calendar, fetch_index_bars_sina, snapshot_index_universe,
)

# 交易日历（as_of/lookback、日期采样的基准）
store.write_trade_calendar(fetch_trade_calendar(ak, start=date(2016, 1, 1), end=date(2026, 7, 10)))

# 指数日线（市值加权基准，如沪深300 = 新浪 "sh000300"）
store.write_index_bars([b for b in fetch_index_bars_sina("sh000300", ak) if b.date >= date(2016, 1, 1)])

# 成分股快照（含每股纳入日期，抗幸存者偏差）。定期重跑积累历史成分。
snapshot_index_universe(store, "000300", ak, snapshot_date=date(2026, 7, 10))
```

## 2. 采集数据

三条源相互独立、都幂等（重复跑安全）、单标的失败隔离、写 `ingestion_log` 审计。

```python
from swell_quant.marketdata import collect_bars, collect_fundamentals, collect_valuations

pool = store.get_universe("000300", date(2026, 7, 10))  # 今天的成分作采集池

# 行情（新浪，后复权因子；增量：重跑只补新交易日）
collect_bars(pool, store, ak, default_start="20160101", end_date="20260710")

# 财务（东财业绩报表，按报告期驱动，一次取全市场再按池过滤）
periods = [f"{y}{q}" for y in range(2016, 2027) for q in ("0331", "0630", "0930", "1231")]
collect_fundamentals(pool, store, ak, periods=[p for p in periods if p <= "20260710"])

# 估值（百度，PE/PB/总市值）。⚠️ period 是"相对今天"的跨度、非日期范围（见 §5）
collect_valuations(pool, store, ak, period="近一年")
```

## 3. 因子

统一 `Factor` 接口 `compute(store, symbols, as_of) -> {symbol: 值|None}`，值越大越优。

```python
from swell_quant.factors import (
    MomentumFactor, ReversalFactor, VolatilityFactor, ValueFactor, QualityFactor,
)
mom   = MomentumFactor(lookback=20)          # 动量
rev   = ReversalFactor(lookback=5)           # 短期反转（买输家）
lowv  = VolatilityFactor(lookback=20)        # 波动（组合里给负权重=低波动暴露）
value = ValueFactor(item="pe_ttm")           # 1/PE 盈利收益率
roe   = QualityFactor(item="roe")            # 质量（ROE），走财务 PIT
grow  = QualityFactor(item="net_profit_yoy") # 成长（净利润同比）

vals = mom.compute(store, pool, date(2025, 6, 30))   # 单日截面因子值
```

预处理（可组合，`FactorValues -> FactorValues`）：`winsorize_mad` 去极值、`zscore`
标准化、`standardize` 流水线、`neutralize_against`/`neutralize_by_group` 中性化。

## 4. IC 评估：因子有没有预测力

```python
from swell_quant.factors import sample_as_of_dates, evaluate_factor_series

dates = sample_as_of_dates(store, date(2017, 1, 1), date(2026, 5, 1), step=20)  # 月频截面点
summ = evaluate_factor_series(mom, store, pool, dates, horizon=20)
print(summ.rank_ic.mean, summ.rank_ic.ir, summ.rank_ic.positive_rate, summ.rank_ic.n)
# 单期噪声大；看多期均值/IR(信息比率)/胜率才算数。
```

## 5. 回测：打分 → Top-N 组合 → 净值/超额

```python
from swell_quant.factors import FactorPipeline, FactorWeight
from swell_quant.portfolio import backtest_composite, walk_forward_backtest

factors = [mom, lowv, roe, grow]
pipe = FactorPipeline(weights=(
    FactorWeight(mom, 1.0), FactorWeight(lowv, -1.0),   # 低波动 → 负权重
    FactorWeight(roe, 1.0), FactorWeight(grow, 1.0),
))

# 固定权重回测（动态池 + 双基准 + 成本）
r = backtest_composite(
    pipe, store, [], dates, top_n=50, horizon=20,
    universe_index="000300",        # 按调仓日动态取当时成分（抗幸存者偏差）；否则传 symbols
    benchmark_index="sh000300",     # 市值加权基准
    equal_weight_benchmark=True,    # 或用等权全池基准（剥离等权 tilt，纯看选股超额）
    cost_bps=10,                    # 单边费率(基点)，按换手扣成本
)
print(r.total_return, r.information_ratio, r.excess_hit_rate, r.max_drawdown)
print(r.annualized_return(252 / 20), r.annualized_sharpe(252 / 20))  # 年化：ppy = 252/horizon

# 样本外 walk-forward（权重只由过去 IC 决定 → 无窥探；回答"edge 是真是假"）
oos = walk_forward_backtest(
    factors, store, [], dates, train_size=24, top_n=50, horizon=20,
    universe_index="000300", equal_weight_benchmark=True, cost_bps=10,
)
# CLI 等价：swell-quant backtest --factors '[...]' --start ... --end ... \
#   --walk-forward --train-size 24   # 输出另含各因子样本外 RankIC(mean/IR/t_stat)
```

**基准怎么选**：对 `benchmark_index`（市值加权）"跑赢"可能只是等权 tilt；对
`equal_weight_benchmark`（同池等权）的超额才是**纯选股 alpha**。判断因子有没有用，看后者。

## 6. 坑与注意事项

- **数据源**：东财 kline 被本机代理封禁，故行情走新浪、估值走百度；但东财**业绩报表**
  `stock_yjbb_em` 可用。见 [[akshare-eastmoney-blocked]] 记忆。
- **估值 period 是相对今天**（近一年/近三年/…/全部），不是日期范围。回补更早历史用更宽
  的 period；否则 as_of 落在覆盖区外取不到值。大票池采集慢/易限流，需分批。
- **财务 knowledge_date** 用法定披露截止日保守估计（Q1→4/30…年报→次年4/30），非源里
  不可靠的"最新公告日"。
- **动态池**依赖 §1 的成分股快照；单一"今天"快照只能修**纳入侧**前瞻，退出侧
  survivorship 需定期快照积累。
- **成本现实性**：`cost_bps=10`（单边）对 A 股偏乐观（印花税+滑点，现实≥20-30bps）。
  高换手信号（如周频反转）会被成本吃光——务必带成本看。

## 完整设计与决策

见 [data-module-decisions.md](data-module-decisions.md)（数据模块的存储/PIT/防未来函数/
幸存者偏差等全部决策）。
