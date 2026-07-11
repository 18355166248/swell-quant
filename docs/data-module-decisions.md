# 数据模块设计决策（Data Module Decisions）

> 本文是数据模块的最终蓝图与决策记录，从“进水口（数据源）→ 蓄水池（存储）→ 水龙头（as_of 服务）”一条完整链路。
> 新模块以独立包 `marketdata/` 承载；旧 `src/swell_quant/data/`、`src/swell_quant/storage/`（CSV→DuckDB 镜像）作为过渡期“参考零件箱”，新系统一行不依赖它，每个新模块验证通过后即删除对应旧代码。

## 0. 分层总览

```
外部数据源 (AKShare: Sina / Tencent，Eastmoney 在本机被代理封禁)
        │  source 层：把外部源翻译成“标准记录”
        ▼
标准记录 (BarRecord / FundamentalRecord / CorporateActionRecord / ...)
        │  store 层：把标准记录落地成表，并按 as_of 服务出去
        ▼
DuckDB（列存、单文件、零运维）
        │  Repository（MarketStore）：干净读写 API，裸 SQL 不外泄
        ▼
上层（因子 / 模型 / 回测）只调 Repository，只拿标准记录
```

两条对称原则：

- **source 层**只跟“外部源”和“标准记录”打交道，永不碰存储引擎。
- **store 层**只跟“标准记录”和“表”打交道，永不碰数据源。

## 1. 标准记录（source 层产物）

记录只存**客观事实**，派生量（复权价、比率）一律不入记录、由上层或视图计算。

- `BarRecord`：`symbol, date, open, high, low, close, volume, amount, adj_factor, source`
  - OHLC 为**不复权真实价**；`adj_factor` 为**后复权累计因子**（见 §2、§7-A）。
- `FundamentalRecord`：`symbol, event_date, knowledge_date, item, value, source`（双时间轴，EAV 长表）。
- `CorporateActionRecord`：`symbol, ex_date, action, value, knowledge_date, source`。
- 其余：估值、指数行情、成分股快照、交易日历（见 §3）。

## 2. 复权决策：存事实 + 视图派生（已确认的升级）

早前存储阶段选的是“后复权 + 不复权**双存**两列”；标准模型阶段确立了更根本的原则——**只存客观事实，复权是派生**。二者取后者：

| | 双存（早前） | 存事实 + 视图（已采用） |
|---|---|---|
| 存什么 | raw 价 + hfq 价两列 | **只存 raw 价 + adj_factor** |
| 后复权价怎么来 | 存着 | **视图计算** `close * adj_factor` |
| 除权日新分红 | hfq 列要重算（易不一致） | 只更新 adj_factor，视图自动对 |
| 你能读到什么 | 两种价都能拿 | **两种价都能拿**（hfq 是视图） |

**关键保证不变**：升级后仍可同时读到不复权价与后复权价；只是后复权价变成**视图**（`close * adj_factor`），不是存下来的列。唯一“存储的事实”是 raw 价与 adj_factor，后复权价永远由二者算出、**永不失同步**。

> 为什么必须是**后复权（hfq）**而不是前复权（qfq）见 §7-A——这是让存储成立的前提，不是随意选择。

## 3. 表设计（DDL 示意）

```sql
-- 行情：只存事实(raw + adj_factor)，freq 分表为未来分钟线预留
CREATE TABLE stock_bar_1d (
  symbol VARCHAR, date DATE,
  open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,   -- 不复权真实价
  volume BIGINT, amount DOUBLE,
  adj_factor DOUBLE,                                    -- 后复权累计因子
  source VARCHAR,
  PRIMARY KEY (symbol, date)
);

-- 后复权价 = 视图(派生，不存)
CREATE VIEW stock_bar_1d_hfq AS
  SELECT symbol, date,
         open*adj_factor AS open, high*adj_factor AS high,
         low*adj_factor AS low,   close*adj_factor AS close,
         volume, amount
  FROM stock_bar_1d;

-- 财务：双时间轴，PK 含 knowledge_date → 保留财报修正历史
CREATE TABLE stock_fundamental (
  symbol VARCHAR, event_date DATE, knowledge_date DATE,
  item VARCHAR, value DOUBLE, source VARCHAR,
  PRIMARY KEY (symbol, event_date, knowledge_date, item)
);

-- 公司行为：双时间轴
CREATE TABLE corporate_action (
  symbol VARCHAR, ex_date DATE, action VARCHAR,
  value DOUBLE, knowledge_date DATE, source VARCHAR,
  PRIMARY KEY (symbol, ex_date, action, knowledge_date)
);

-- 估值
CREATE TABLE stock_valuation (
  symbol VARCHAR, date DATE,
  pe DOUBLE, pe_ttm DOUBLE, pb DOUBLE, ps DOUBLE, dv_ratio DOUBLE, total_mv DOUBLE,
  source VARCHAR,
  PRIMARY KEY (symbol, date)
);

-- 指数行情
CREATE TABLE index_bar (
  index_code VARCHAR, date DATE,
  open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT, amount DOUBLE,
  source VARCHAR,
  PRIMARY KEY (index_code, date)
);

-- 成分股快照（历史成分随时间变化）
CREATE TABLE universe_member (
  snapshot_date DATE, index_code VARCHAR, symbol VARCHAR,
  source VARCHAR,
  PRIMARY KEY (snapshot_date, index_code, symbol)
);

-- 交易日历
CREATE TABLE trade_calendar (
  date DATE, is_open BOOLEAN,
  PRIMARY KEY (date)
);

-- 治理表
CREATE TABLE schema_version (version INTEGER, applied_at TIMESTAMP, note VARCHAR);
CREATE TABLE ingestion_log (
  batch_id VARCHAR, table_name VARCHAR, source VARCHAR,
  started_at TIMESTAMP, finished_at TIMESTAMP,
  row_count BIGINT, status VARCHAR, message VARCHAR
);
```

## 4. 三个核心机制

**① 幂等 upsert**：`INSERT ... ON CONFLICT DO UPDATE`（按主键）。同一批重复灌入，行数不增、值被更新——增量采集“重复跑安全”的底层保障。

**② `as_of` 查询（存储层的灵魂）**：

- 行情 `get_bars(symbols, as_of, lookback=N)`：`WHERE date <= as_of ORDER BY date DESC LIMIT N`（配合 trade_calendar）。
- 财务 `get_fundamentals(as_of)`：**point-in-time**——`WHERE knowledge_date <= as_of`，再按 `(symbol, item)` 取 `event_date/knowledge_date` 最新的一条（窗口函数）。一句 SQL 杜绝财务未来函数。

**③ 增量支持**：`get_max_date(table, symbol)` 查“库里最新到哪天”，供采集服务算增量窗口。

## 5. 对外接口（Repository / MarketStore）

```python
class MarketStore:
    def write_bars(self, records: list[BarRecord]) -> None: ...        # 幂等
    def get_bars(self, symbols, as_of, lookback) -> list[BarRecord]: ...
    def get_bars_hfq(self, symbols, as_of, lookback) -> list[BarRecord]: ...  # 读视图
    def write_fundamentals(self, records) -> None: ...
    def get_fundamentals(self, symbols, as_of) -> list[FundamentalRecord]: ...  # PIT
    def get_max_date(self, table, symbol) -> date | None: ...
```

上层只调这些，不写裸 SQL。**测试用内存 DuckDB（`:memory:`）**：秒级、不依赖文件与网络——落地“独立可测”。

不抽象存储引擎（不做“可插拔引擎”的空复杂度），但用 Repository 模式隔离裸 SQL：接口预留、机制不预建。

## 6. 长期主义三块

1. **Schema 版本与迁移**：`schema_version` 表 + 有序迁移脚本，改结构不丢历史数据。
2. **性能与未来**：DuckDB 单文件足够；按 `(symbol, date)` 聚簇；未来分钟线走独立表 `stock_bar_1m` + Parquet 冷存分区，不冲击日线；金额精度第一版 DOUBLE，敏感时升 DECIMAL。
3. **审计**：`ingestion_log` 让任何数据可追溯到批次；DuckDB 单文件天然可快照归档，保证回测/实盘可复现。

---

## 7. 待办与开放问题（“看下还有什么问题”）

这些是设计闭环后、动工前必须先想清楚的真实风险，不是走过场。

### 7-A. adj_factor 必须是“起点锚定的后复权因子”（决定存储是否成立）★最关键

存事实+视图能成立，**前提**是 adj_factor 满足一个性质：**新分红发生时，历史 adj_factor 不被改写**。

- **后复权（hfq）**锚定序列起点：新的除权发生在 D 日，只影响 `date >= D` 的因子，`date < D` 的因子不变 → 历史事实不可变，追加数据安全。**满足。**
- **前复权（qfq）**锚定“今天”：每次新分红把**全部历史**重新缩放 → 历史被改写。**绝不能存**，qfq 只能作为纯展示变换、永不落库。

**风险**：AKShare 不同接口给的 adj_factor 归一化方式不一（有的起点=1 递增，有的末点=1）。若拿到的是末点锚定，追加新数据会改写老因子，破坏 PIT。
**动工第一件事**：核对所选接口返回的因子是**起点锚定**；若不是，在 source 层归一化为起点锚定再入库，并加一条测试：灌入含新除权的增量后，历史行 adj_factor 保持不变。

**✅ 已用真实 Sina 数据核对（600519，2024）**：
- 后复权因子 = hfq收盘/raw收盘 是**上市日锚定**（2024 年窗口起点因子已是 8.07，不是 1.0；上市日 2001-08-27 才 = 1.0）。→ **绝不能按采集窗口重锚定**，否则会把 8.07 压回 1.0、破坏跨批次一致。`build_bar_records` 已确保不重锚。
- 除权日（2024-06-27 分红）因子只抬升其**之后**的值（8.0718→8.239），历史保持不变 → 免疫未来函数，与 §7-A 测试吻合。
- ⚠️ **噪声发现**：源把 hfq 收盘只留 2 位小数，hfq/raw 相除带 ~1e-6 浮点噪声 → 同一天不同窗口取值可能微差（8.071839 vs 8.071836），**破坏幂等 upsert**。
- **✅ 更优来源**：`ak.stock_zh_a_daily(symbol, adjust="hfq-factor")` 直接给**稀疏台阶因子**（仅除权日各一行，上市日=1.0，高精度、无相除噪声）。任意日因子 = 前向填充（取 date ≤ 目标日的最近一条）。→ **决定改用 hfq-factor + 前向填充**替代 hfq/raw 相除，兼得精确与幂等。`build_bar_records`（相除法）保留为已测的纯函数备选。

### 7-B. 历史成分股 = 幸存者偏差地雷

`ak.index_stock_cons` 只给**当前**成分股，不给历史。用当前成分回测过去，会系统性高估收益（幸存者偏差）。
`universe_member` 的 `snapshot_date` 结构已为 PIT 成分预留，但**数据来源缺口真实存在**。
**建议**：v1 明确接受此限制并在报告里标注；同时从现在起**按快照定期落库**（每次采集写一份当日成分），随时间自建历史成分——这是唯一低成本、可积累的解法。

### 7-C. 财务/公司行为的 knowledge_date 来源要逐项确认

**✅ 已落地（财务）**：真实核对发现东财业绩报表 `stock_yjbb_em` 的“最新公告日期”是**公司最近一次
公告日**、非本行报告期的原始公告日（2024Q1 数据大量显示 2025-04），用作 knowledge_date 会破坏 PIT。
故**弃用该字段**，改用“报告期末 + **法定披露截止日**”做保守估计（Q1→4/30、半年→8/31、Q3→10/31、
年报→次年4/30），source 标注 `yjbb_em_est`。这是 PIT 安全方向（只会更晚、不泄露未来）。真实验证：
600519 的 ROE 在 2025-04-30 前后由 2024Q3 切到 2025Q1，PIT 可见性正确。未来若接入带真实公告日的源，
可无缝替换 knowledge_date、精度更高。

原始说明：

`stock_yjbb_em`（业绩报表）带公告日期，可作 knowledge_date（前期已验证）。但估值、其它财务项不一定都带公告日期。
**动工前**：对每个要入库的 `item` 确认能否拿到真实公告日；拿不到的，用“事件期末 + 保守披露滞后”兜底，并在 `source` 里标注是估计值，避免把估计当事实。

### 7-D. 交易日历来源 ✅ 已落地

`as_of + lookback` 的正确性依赖真实交易日历。已用 `ak.tool_trade_date_hist_sina` 落库
`trade_calendar`，并接入 `collect_bars`：有日历时用 `latest_trading_day(<= end)` 精确判定
“已最新”，精确跳过非交易日尾窗（不再依赖空响应兜底）。真实验证：2024 年 242 个交易日，
end=周日时零请求精确 skip。**仍待补**：把 `get_bars` 的 lookback 也改为按交易日历计数
（当前按库中已存行计数，日线连续时等价）。

### 7-E. 与旧存储的迁移边界

现有 `src/swell_quant/storage/`（CSV→DuckDB 镜像）与 `data/duckdb/swell_quant.duckdb` 是旧演示存储。
**决策**：新库用**独立文件**（如 `data/duckdb/marketdata.duckdb`），与旧库物理隔离，互不干扰；新链路验证通过后再删旧 storage 与对应表。避免“同一文件里新旧表混居”带来的迁移风险。

### 7-F. EAV 长表 vs 宽表（财务）

`item VARCHAR, value DOUBLE` 的长表灵活、加指标不改表，但无类型安全、查询要 pivot。第一版接受长表（灵活性优先）；若后续固定指标集稳定，可在其上建**物化宽视图**给因子层，兼顾灵活与好查。此为可延后优化，不阻塞动工。

---

## 实现进度（TDD，包 `src/swell_quant/marketdata/`）

| 层 | 文件 | 内容 | 测试 |
|---|---|---|---|
| source | `records.py` | `BarRecord` 标准记录（只存客观事实） | — |
| source | `adjust.py` | `normalize_adj_factor` 起点锚定防御工具 | 6 |
| source | `source_bars.py` | `build_bars_from_factor_steps`（推荐：台阶因子+前向填充）、`build_bar_records`（相除备选）、`fetch_bars`、`fetch_bars_sina`（真实新浪路径）、`sina_symbol` | 12 |
| store | `store.py` | `MarketStore`：`stock_bar_1d` 表 + `stock_bar_1d_hfq` 视图 + 幂等 upsert + `get_bars`/`get_bars_hfq`(as_of/lookback) + `get_max_date` | 10 |
| store | `store.py` | 财务：`FundamentalRecord` + `stock_fundamental` 双时间轴表 + 幂等 `write_fundamentals` + **PIT** `get_fundamentals(as_of)`（防财务未来函数，含财报修正历史） | 7 |
| store | `store.py` | 估值：`ValuationRecord` + `stock_valuation` 长表 + 幂等 `write_valuations` + `get_valuations(as_of, lookback)` | （见估值） |
| source | `source_valuation.py` | `fetch_valuations_baidu`（百度 `stock_zh_valuation_baidu`，逐指标合并，纯6位代码） | 8 |
| service | `collect.py` | `collect_valuations`：估值池化采集，增量（拉整段留新观测）、失败隔离、审计 | 2 |
| store | `store.py` | 治理：`ingestion_log` 审计表 + `record_ingestion`/`get_ingestion_log` | （见采集） |
| source | `source_calendar.py` | `fetch_trade_calendar`（AKShare `tool_trade_date_hist_sina`） | 4 |
| store | `store.py` | 交易日历：`trade_calendar` 表 + `write_trade_calendar`/`is_trading_day`/`latest_trading_day` | （见日历） |
| source | `frames.py` | 共享帧解析工具（iter_rows/value/to_float/parse_date） | — |
| service | `collect.py` | `collect_bars`：股票池采集，**增量**（`get_max_date`+日期钳制）、单票失败隔离、批次审计；**有日历时精确判定“已最新”** | 12 |
| e2e | `test_marketdata_integration.py` | 台阶因子 → 合成 → 落库 → as_of 读出；验证后复权视图消除除权跳空 | 1 |

共 62 个 marketdata 测试，全绿；旧代码零回归。store 层用内存 DuckDB 测试，不依赖网络。

> **估值表设计调整**：§3 曾把 `stock_valuation` 画成宽表（pe/pb/ps… 各一列）；实现改为
> **长表/EAV**（`symbol, date, item, value`），与财务表一致，也贴合百度“单指标一序列”的真实
> 形态、天然容忍缺指标。数据源为**百度**（`stock_zh_valuation_baidu`，东财被代理封禁）；A股用
> 纯 6 位代码；默认指标 pe_ttm/pb/total_mv（市销率部分标的不可用，暂不纳入）。真实验证：
> 600519+000001 采 2190 行，重采 0 行（幂等）。
>
> **注意（真实使用发现）**：百度估值的 `period`（近一年/近三年/…/全部）是**相对今天**的时间跨度，
> 不是日期范围。回补更早历史需用更宽的 period（如“全部”）；否则 as_of 落在覆盖区间之外会取不到估值。
>
> **规模瓶颈**：百度估值一次一指标一股票，300 只 × 3 指标 = 900 次请求，慢且易被限流/中断。大票池
> 采集时应分批、加重试/断点续采，或改用能批量返回全市场估值的源。行情（新浪）与财务（东财业绩报表，
> 一次返回全市场一期）都无此问题。

**✅ 真实数据端到端验证**：`fetch_bars_sina('600519', 2024H1)` 经真实新浪拉到 140 根日线 → 落 DuckDB 文件库 → 重复灌仍 140 行（幂等）→ 后复权视图 raw 1421.28 × 因子 8.239 = 11709.97（算对）。行情主线在真实数据上跑通。

**✅ 采集服务真实验证**（600519/000001/300750）：run1 采 57 行；run2 同窗口 0 行全 skipped（增量幂等）；run3 扩到 7 月只增量补新交易日。真实数据暴露并已修两处：
- 新浪空窗口会返回窗口外最近一行 → 采集**钳制 `date <= end_date`** 保证可复现。
- 增量尾窗常落在非交易日 → 空响应归为 **skipped 而非 failed**（缺 trade_calendar 的兜底，见 §7-D，日历就位后可更精确）。

**store 层仍待补**：公司行为表（corporate_action）、估值/指数/成分股/trade_calendar 表、治理表（schema_version/ingestion_log）、真实文件库 `marketdata.duckdb` 接线。

## 决策状态

- [x] 复权：存事实 + 视图派生（后复权），替代早前“双存”——**已确认**。
- [x] 双时间轴（event_date + knowledge_date）防财务未来函数——已确认。
- [x] Repository 模式隔离 SQL、内存 DuckDB 可测——已确认。
- [x] 治理表（schema_version / ingestion_log）——已确认。
- [x] 7-A 因子锚定核对——**已用真实 Sina 数据验证**：因子上市日锚定、免疫未来函数；改用 `hfq-factor` 台阶因子 + 前向填充以求精确幂等（见 §7-A）。
- [ ] 7-B 成分股快照策略（接受 v1 限制 + 定期落库自建历史）。
- [ ] 7-C 各 item 的 knowledge_date 来源确认。
- [x] 7-D 交易日历——已落库 `trade_calendar` 并接入采集精确跳过（真实数据验证，见 §7-D）。
- [ ] 7-E 新旧库物理隔离 + 旧 storage 退役路径。
