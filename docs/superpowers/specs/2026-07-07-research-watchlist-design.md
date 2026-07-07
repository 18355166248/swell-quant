# 设计：预测页「研究参考清单」（Watchlist）

- 日期：2026-07-07
- 状态：待评审
- 范围：前端研究看板增强（阶段 5 迭代）

## 背景

用户希望看板能更「可落地」——不只给一堆预测分数，而是能落到「这几只值得关注、为什么上榜、风险在哪」。当前预测页（`frontend/src/pages/researchPages.tsx` 内 `PredictionsPage`）以表格展示 Top N 的 `rank / symbol / score / 关键因子`，加一张按标的的分数柱状图，缺少「相对置信度」「因子归因」「风险提示」的整合视图。

本设计把现有 Top N 预测升级为一份**研究参考清单**（watchlist），补齐这三块，但严格守住项目定位。

## 定位与边界（合规底线）

[plan.md](../../plan.md) 明确：项目**不提供买卖建议**，v1 不做「直接用 LLM 判断买入/卖出」，报告**不输出确定性投资建议**，所有页面常驻「仅用于研究，不构成投资建议」。

本功能定位为**研究参考清单，不是荐股信号**：

| 做（研究参考） | 不做（投资建议） |
| --- | --- |
| Top N 候选 + 预测分数 + 相对置信度 | 明确的「买入/卖出」指令 |
| 因子归因（为什么上榜） | 目标价、仓位、买卖点 |
| 启发式风险提示 | 「稳赚/推荐/必涨」类措辞 |
| 保留研究用途声明与免责 | 让 LLM 直接生成买卖决策 |

措辞规范：使用「关注 / 候选 / 参考」，禁止「买入 / 卖出 / 推荐 / 建议 / 稳赚」。清单卡片顶部保留免责声明。

## 目标

- 在预测页新增「研究参考清单」卡片，把 Top N 预测整合为带**相对置信度**、**因子归因**、**风险提示**的可读清单。
- 相对置信度与因子归因**纯前端派生**，复用页面已读取的 `predictionRows`，不新增接口。
- 保留现有 Top N 表格与分数图，清单不替代它们。

## 非目标

- 不输出任何买卖指令、目标价、仓位建议。
- 不新增后端字段或接口（精确停牌/涨跌停风险标记依赖后端数据，列为后续项，见「后续演进」）。
- 不改动其它页面（Dashboard、Backtests、Stocks 等）。
- 不引入 LLM 生成清单文本（沿用阶段 6「LLM 只解释、不生成预测分数」的口径）。

## 方案

复用预测页已有的 `predictionRows`（`Prediction[]`），新增纯前端派生逻辑与展示卡片。

现有 `Prediction` 字段：`rank, symbol, date, model_version, score, return_1d, momentum_5d, volume_change_1d`。

### 1. 派生工具函数 `buildWatchlist`

- 位置：新增 `frontend/src/utils/watchlist.ts`（与 `charts.ts` 并列）。
- 签名：`buildWatchlist(rows: Prediction[], topN = 10): WatchlistItem[]`。
- 派生 `WatchlistItem`：

```ts
interface WatchlistItem {
  rank: number;
  symbol: string;
  score: number;
  confidence: number;      // 0..1，score 在当日全池中的分位
  confidenceLevel: "high" | "medium" | "low";
  factors: FactorTag[];    // 因子归因，按强度排序
  riskHints: RiskHint[];   // 启发式风险提示，可能为空
}
interface FactorTag { name: string; value: number; direction: "up" | "down"; }
interface RiskHint { code: string; label: string; }
```

- **相对置信度**：对**全部**传入 `rows` 的 `score` 做 min-max 归一（`(score - min) / (max - min)`，`max === min` 时置 0.5），得到 0..1 的相对位置；再按阈值映射 `confidenceLevel`（`>= 0.8` high、`>= 0.5` medium、否则 low）。语义是「在当日预测池中的相对强弱」，非胜率、非概率——tooltip 显式说明。
- **因子归因**：从 `momentum_5d / return_1d / volume_change_1d` 取非空项，按 |value| 排序，生成 `FactorTag`（`direction` 由正负号定），最多取前 3 条。全为空时 `factors` 为空数组。
- **风险提示（启发式）**：仅基于现有字段的粗略提示，**明确标注为启发式、非精确判定**：
  - `return_1d` 绝对值 ≥ 0.095 → `{ code: "limit_move", label: "接近涨跌停幅度" }`。
  - `volume_change_1d` 绝对值 ≥ 2 → `{ code: "volume_spike", label: "成交量异动" }`。
  - 字段为空不生成对应提示。
- 取前 `topN` 条（按 `rank` 升序；`rows` 已按 rank 排序时保持稳定）。
- `rows` 为空返回 `[]`，不抛异常。

### 2. 预测页渲染

- 位置：`PredictionsPage` 内，Top N 表格**上方**新增 `Card title="研究参考清单"`。
- `predictionRows.length > 0` 时渲染清单，每条含：排名、代码、分数、置信度（`Tag` 或进度条 + 文案）、因子标签（`Tag` 组，涨绿跌红或箭头）、风险提示（`Tag color="warning"`，无则不显示）。
- 卡片顶部放一行说明：「清单基于模型预测分数的相对强弱，仅用于研究，不构成投资建议。风险提示为启发式，不替代停牌/涨跌停的精确判定。」
- `predictionRows` 为空时维持现有空状态，不渲染清单。
- 桌面端 1366px 可读；清单条数受 `topN` 限制，避免一次渲染过大。

## 数据流

`GET /api/predictions/latest`（或筛选后的 `/api/predictions`）→ `predictionRows` → 同时供现有表格、分数图与 `buildWatchlist` 使用。无新增请求、无状态变更。

## 错误与边界处理

- 空数据：不渲染清单，保留现有空状态。
- 全池分数相同：置信度统一置 0.5、level = medium，不除零。
- 因子/风险字段为空：对应标签/提示不生成，不补零、不误报。
- 候选数少于 `topN`：全量展示。

## 测试

新增 `frontend/src/utils/watchlist.test.ts`，覆盖：

- 置信度归一：最高分 → 1、最低分 → 0；`max === min` → 全部 0.5。
- `confidenceLevel` 阈值映射正确（high/medium/low 边界）。
- 因子归因：按 |value| 排序、方向正确、空字段不产出、最多 3 条。
- 风险提示：`return_1d ≥ 0.095` 触发 `limit_move`；`volume_change_1d ≥ 2` 触发 `volume_spike`；字段空不触发。
- Top N 截断与空数组返回 `[]`。
- （可选）`researchPages.test.tsx` 补一条：预测有数据时渲染「研究参考清单」卡片且含免责文案。

验收：`npm run build` 与前端单测（vitest）通过。

## 改动清单

- `frontend/src/utils/watchlist.ts`：新增 `buildWatchlist` 与相关类型。
- `frontend/src/utils/watchlist.test.ts`：新增单测。
- `frontend/src/pages/researchPages.tsx`：`PredictionsPage` 新增「研究参考清单」卡片。
- （可选）`frontend/src/pages/researchPages.test.tsx`：补渲染断言。

## 后续演进（本次非目标）

- **精确风险标记**：后端在预测产物中附加每标的 `is_suspended / limit_up / limit_down / 数据缺口` 字段（当前该判定仅存在于回测层 `rejected_trades`），前端用真实标记替换启发式提示。
- **拥挤度 / 换手拥挤提示**：需额外因子数据。
- **历史命中回顾**：结合 `stock_predictions` 展示清单历史表现，仍作研究解释，不作建议。

## 风险与声明

- 纯前端展示增强，不改变模型、预测或回测口径。
- 清单仅可视化既有预测分数与因子，**不构成任何投资建议**；看板研究用途声明维持不变。
- 措辞门禁：清单相关文案禁止出现买入/卖出/推荐/建议/稳赚等交易指令性词汇。
