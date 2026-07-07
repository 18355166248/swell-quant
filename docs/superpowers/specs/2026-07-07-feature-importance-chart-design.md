# 设计：Models 页特征重要性横向条形图

- 日期：2026-07-07
- 状态：已评审，待实现
- 范围：前端研究看板增强（阶段 5 迭代）

## 背景

研究看板 Models 页已展示模型版本、训练区间、特征列表、评估指标和特征重要性。其中「特征重要性」卡片（`frontend/src/pages/researchPages.tsx` 内 `ModelsPage`）当前仅用表格展示 `rank / feature_name / importance / raw_importance / importance_type`，需要逐行阅读才能判断因子权重排序。

模型元数据 `data/models/latest_model.json` 已写入 `feature_importance` 字段，前端类型为 `ModelFeatureImportance[]`：

```ts
interface ModelFeatureImportance {
  feature_name: string;
  rank: number;
  importance: number;
  raw_importance: number;
  split_count?: number;
  importance_type: string;
}
```

特征重要性是量化模型看板最直观的可视化之一。横向条形图能一眼看出哪些因子权重高，补齐当前只有数字表格的短板。

## 目标

- 在「特征重要性」卡片中，于现有表格**上方**新增一个横向条形图，直观呈现各因子相对权重与排序。
- 保留原有表格，继续承载 `raw_importance`、`importance_type` 等精确字段，图表不替代表格。
- 不改动后端和 API；数据复用页面已读取的 `importanceRows`。

## 非目标

- 不新增后端字段或接口。
- 不改动其它页面（Dashboard、Predictions、Backtests、Stocks 等）的图表。
- 不做图表主题体系重构；沿用现有 echarts 配色与 `ReactECharts` 封装。

## 方案

采纳方案 A：新增独立的 `buildFeatureImportanceOption` 图表配置函数，Models 页在特征重要性卡片内渲染。

### 备选方案与取舍

- 方案 B（图表替换表格）：丢失 `raw_importance`、`importance_type` 等精确数据，不采纳。
- 方案 C（垂直条形图，同 `buildScoreOption`）：特征名较长、数量偏多，垂直排布可读性差，不采纳。

## 组件设计

### 1. 图表配置函数 `buildFeatureImportanceOption`

- 位置：`frontend/src/utils/charts.ts`，与现有 `buildScoreOption` 等函数并列。
- 签名：`buildFeatureImportanceOption(rows: ModelFeatureImportance[], topN = 15)`。
- 行为：
  - 按 `rank` 升序取前 `topN` 条（`rank` 越小越重要）。
  - 生成横向条形图 option：`yAxis` 为 `category` 类型、数据为特征名；`xAxis` 为 `value` 类型、数据为 `importance`；`series[0].type = "bar"`。
  - 为让最重要的因子显示在顶部，`yAxis` 数据按「重要性从低到高」排列（echarts 横向条形图从下往上绘制），即对取好的 Top N 再做一次反序。
  - 沿用主色 `#1f6feb`；`tooltip.trigger = "axis"`；`grid` 参照现有函数留出左侧标签空间（特征名较长，`left` 适当加大）。
  - `rows` 为空数组时返回 `series[0].data` 为空的合法 option，不抛异常。

### 2. Models 页渲染

- 位置：`frontend/src/pages/researchPages.tsx` 内 `ModelsPage` 的「特征重要性」卡片。
- 当 `importanceRows.length > 0` 时，卡片内先渲染 `<ReactECharts option={buildFeatureImportanceOption(importanceRows)} />`，再渲染原有表格；`importanceRows` 为空时维持现有 `<Empty description="暂无特征重要性" />`，不渲染图表。
- 图表沿用现有 className 约定（参考 `large-chart` / `score-chart`），保证桌面端可读高度。

## 数据流

`GET /api/models/latest` → `LatestModel.feature_importance` → `ModelsPage` 内 `importanceRows` → 同时供表格和 `buildFeatureImportanceOption` 使用。无新增请求，无状态变更。

## 错误与边界处理

- 空数据：`importanceRows` 为空 → 不渲染图表，保留 `<Empty>`。
- 因子数少于 `topN`：全量展示，不补零。
- `importance` 为 0 或负值：按原值绘制，不特殊处理（当前模型产物 importance 非负）。
- 特征名过长：由横向布局与 `grid.left` 容纳；必要时 echarts 自动省略。

## 测试

在 `frontend/src/utils/charts.test.ts` 补 `buildFeatureImportanceOption` 单测，覆盖：

- 横向轴配置正确：`yAxis.type === "category"`、`xAxis.type === "value"`。
- series 数据映射正确：`series[0].type === "bar"`，数据长度与截断后条数一致。
- Top N 截断：传入超过 `topN` 条时只保留前 `topN`。
- 顶部为最重要因子：`yAxis.data` 末位对应 `rank` 最小的特征名。
- 空数组：返回合法 option 且 `series[0].data` 为空。

验收：`npm run build` 与前端单测（vitest）通过；`docsConsistency.test.ts` 若涉及文档一致性不受影响。

## 改动清单

- `frontend/src/utils/charts.ts`：新增 `buildFeatureImportanceOption`。
- `frontend/src/utils/charts.test.ts`：新增对应单测。
- `frontend/src/pages/researchPages.tsx`：`ModelsPage` 特征重要性卡片内插入 `ReactECharts`。

## 风险与声明

- 纯前端展示增强，不改变模型、预测或回测口径。
- 图表仅可视化既有 `feature_importance`，不构成任何投资建议；看板研究用途声明维持不变。
