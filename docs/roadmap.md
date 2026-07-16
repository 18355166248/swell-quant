# 路线图

本项目的规划此前散落在 README、AGENTS 和各 docs 里，这里集中收拢。原则不变：
**先把偏差诚实暴露出来，再谈找 alpha**；不越 [AGENTS.md](../AGENTS.md) 的红线。

## 现状（已跑通）

- **研究内核**：`marketdata → factors → portfolio` 三层闭环，全程只经 `MarketStore`
  的 as_of / point-in-time 接口取数，从底层杜绝未来函数。
- **抗偏差机制**：成分股快照（含每股纳入日期）、per-rebalance-date 动态池、交易成本、
  双基准（市值加权 + 等权全池）、walk-forward 样本外验证、MAD/z-score/中性化预处理。
- **诚实结论**：沪深300 100 只、2016–2026、90 个样本外期验证下，四个简单因子
  RankIC ≈ 0，对等权全池的选股超额为负——见 [README.md](../README.md)。
- **可视化**：只读 FastAPI bridge + React/TS/shadcn 看板，含 Overview / Backtest /
  Instrument（持仓/单标的研究）三页；Instrument 支持自带估值通道 + 蛋卷指数 PE 一键刷新。

## 近期：AI 工作流层

研究内核已经足够严谨，当前最缺的是"AI 可自主执行研究"的一层：把研究过程
命令化、文档化、可沉淀。按优先级推进：

1. **P1 数据与研究入口命令化（已完成）**——把 marketdata / factors / portfolio 的核心能力
   包一层 CLI（输出 JSON）：`data bars / trade-days / securities / valuation`、
   `factor ic`、`backtest walk-forward`。全部走 `MarketStore` 的 as_of 接口，
   天然带 PIT 保证。CLI 与后续 MCP tool 共享同一层 service 函数，
   提前兑现中期"MCP/HTTP 集成"的一半工作量。
2. **P2 本地口径文档 + 字段表**——面向 AI 检索的主题速查文档：数据口径
   （复权锚定、knowledge_date 规则、停牌处理）、因子定义与参数、回测口径
   （成本模型、双基准含义）、结论评估标准。目标是"AI 写策略先查文档再下笔，
   不靠记忆瞎编参数"。
3. **P3 研究工作台**——`workspace/` 三件套：
   - `preferences.md` 硬规则当宪法：红线、结论必须过双基准 + 样本外、
     禁止只报样本内数字、多重检验纪律（试过的因子必须全部记录）。
   - `research-log/` 一会话一文件：方法、参数、中间观察、下一步——防 p-hacking。
   - `findings/` 沉淀 + 升级闸门：样本外 RankIC、对等权全池超额、最少验证期数
     三条同时满足，才允许从 research-log 升入 findings。
4. **P4 研究 SOP 固化为项目 skill**——`/research-factor`：查口径文档 → 读
   preferences → 拉数据 → 跑 IC + 双基准 + walk-forward → 写 research-log
   （达标则升 findings）。
5. **P5 纸面组合跟踪（中期）**——不碰红线（不下单、不接券商），只做纸面组合
   每日快照：findings 里的策略按规则生成目标持仓，记录虚拟净值/换手，
   回看真实后续行情下的表现；看板加对应页面。

明确**不做**的：不引入聚宽/远程内核依赖（自有 DuckDB + PIT 更可审计）；
不做"找潜在涨停票"类话术功能（与"诚实暴露偏差"的定位相反）。

## 近期：找真 alpha

当前四因子无可信 alpha，下一步沿 README 结尾给的路线走：

1. **修幸存者偏差（退出侧）**——定期重跑 `snapshot_index_universe` 积累历史成分，
   让动态池覆盖真实的纳入/退出，而非单张"今天"快照只修纳入侧。
2. **中性化验证**——已有 `neutralize_against` / `neutralize_by_group` 原语，
   需系统性验证行业/市值中性化后因子的增量 IC。
3. **更强因子**——在动量/价值/波动/质量之外，探索有理论支撑的新因子并按同一套
   IC + 双基准 + 样本外流程诚实评估。

这三个实验是 P3/P4 工作台的**第一批用户**：用新流程跑，工作台的价值立刻可验证。

## 中期：集成与看板

- **对外集成**：本项目不把代码写入 `swell-lobster`，通过 **MCP 或 HTTP API** 集成
  （只读 FastAPI bridge 已是这一步的铺垫，后续按需扩接口）。见 [AGENTS.md](../AGENTS.md)。
- **看板完善**：因子 IC 报告、样本外结果的可视化呈现。

## 长期 / 暂不做

引入外部框架有明确的触发条件，未到条件不提前引入（见
[open-source-references.md](./open-source-references.md)）：

- 因子/模型变复杂 → 评估 **Qlib** 的分层。
- 需要批量参数扫描 → 评估 **vectorbt**。
- 需要事件驱动策略 → 评估 **Backtrader**。
- 需要实盘 / 多资产执行 → 重新评估 **Lean** 或专门交易系统。
- **RL 交易策略（FinRL）** 仅作后续研究参考，v1 不采用。

## 红线（不随规划松动）

除非有新的明确计划和安全评审，**不新增**自动下单、实盘交易、券商登录、资金账户操作能力；
所有用户可见预测/报告须标注"仅用于研究，不构成投资建议"。详见 [AGENTS.md](../AGENTS.md)。
