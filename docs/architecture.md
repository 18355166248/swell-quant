# 架构设计

## 总体架构

```txt
React 研究看板
        ↓
FastAPI Backend
        ↓
Research Services
  ├── Data Ingestion
  ├── Feature Pipeline
  ├── Model Training
  ├── Prediction Ranking
  ├── Backtest Engine
  └── AI Report Service
        ↓
DuckDB + File Artifacts
```

第一版采用 Python FastAPI + DuckDB + React。原因是量化核心依赖 pandas、LightGBM、AKShare 等 Python 生态，DuckDB 适合本地日频研究数据，React 适合构建交互式研究看板。

## 后端分层

### API 层

职责：

- 暴露数据更新、训练、预测、回测、报告查询接口。
- 统一参数校验和错误返回。
- 不承载因子计算、训练和回测细节。

### 数据层

职责：

- 从 AKShare 拉取 A 股日频行情。
- 清洗复权、停牌、缺失、重复数据。
- 写入 DuckDB。
- 记录数据任务日志。

DuckDB v1 使用策略：

- 采用单机文件模式，数据库文件放在 `data/duckdb/` 下，v1 默认只支持单用户本地研究。
- 后端统一封装一个写入入口，同一时间只允许一个数据更新、因子生成、训练或回测写任务执行；读请求可以读取已经落盘的稳定结果。
- 行情、因子和标签表都以 `symbol/date` 作为核心唯一键，增量更新先写临时表，再按键覆盖目标表，避免重复追加。
- 常用查询围绕 `date`、`symbol`、`model_version`、`backtest_id` 组织；DuckDB 主要依赖列式扫描和排序后的表结构，v1 不提前设计复杂索引。
- 封装 `backup_duckdb()`，在数据更新、训练和回测任务结束后自动复制 DuckDB 文件或导出关键表到 `data/processed/`，避免依赖人工判断是否备份。

### 因子层

职责：

- 基于清洗后的日频行情生成基础技术因子。
- 维护因子版本和字段列表。
- 保证滚动窗口只使用历史数据。

### 模型层

职责：

- 按时间切分训练、验证、测试集。
- 训练 LightGBM 模型。
- 保存模型产物、训练参数、特征列表和评估结果。
- 生成预测分数和股票排名。

### 回测层

职责：

- 基于预测排名构建 Top N 组合。
- 模拟调仓、手续费、滑点、停牌和基础交易限制。
- 输出净值、回撤和指标。

### AI 报告层

职责：

- 调用 DeepSeek 或 OpenAI 生成研究报告。
- 只解释已有数据、模型输出和回测结果。
- 不生成原始预测分数，不输出确定性买卖建议。

## 数据目录

建议结构：

```txt
data/
  raw/          # 原始下载数据
  processed/    # 清洗后数据快照
  duckdb/       # DuckDB 数据库
  models/       # LightGBM 模型文件和元数据
  reports/      # AI 报告和回测报告
```

## 前端分层

```txt
frontend/src/
  pages/
    Dashboard/
    Predictions/
    Backtests/
    StockDetail/
    Reports/
  components/
    charts/
    tables/
    layout/
  api/
  types/
```

前端第一版重点是研究效率，不做营销页。首页直接进入看板，显示数据状态、模型状态和最近回测摘要。

v1 前端选型：

- React + TypeScript + Vite。
- UI 组件优先使用 Ant Design，降低表格、表单、日期选择和空状态的实现成本。
- 图表库优先使用 ECharts，覆盖净值曲线、回撤曲线、K 线、因子走势和指标对比。
- 状态管理先使用 React Query 管理服务端状态，局部 UI 状态使用 React 内置 state；暂不引入全局状态库。
- 前端只展示研究结果和任务状态，不承载训练、回测和报告生成的核心逻辑。

## API 草案

第一版可保留以下能力边界：

- `POST /api/data/update`：触发数据更新。
- `GET /api/data/status`：查看数据状态。
- `POST /api/models/train`：触发模型训练。
- `GET /api/models/latest`：查看最新模型。
- `POST /api/predictions/run`：生成预测排名。
- `GET /api/predictions/latest`：查看最新预测。
- `POST /api/backtests/run`：运行回测。
- `GET /api/backtests/{id}`：查看回测详情。
- `POST /api/reports/generate`：生成 AI 报告。
- `GET /api/reports/{id}`：查看报告。

## 任务触发

v1 先采用手动触发为主：

- 用户在前端或命令行触发数据更新、训练、预测、回测和报告生成。
- 阶段 1 即建立 `scripts/run_pipeline.py` 骨架，先串联已完成步骤，后续逐步接入因子、标签、训练和回测，降低阶段 4.5 的集成成本。
- 后端记录任务状态、开始时间、结束时间、输入参数、输出产物路径和失败原因。
- 暂不内置常驻调度器；需要每日更新时，优先通过外部 cron 调用 HTTP API 或 CLI。
- 同类写任务串行执行，避免 DuckDB 单文件写入冲突；前端展示排队、运行中、成功和失败状态。

## 关键风险

- 未来函数：标签和因子必须严格按时间切分。
- 数据泄漏：训练集不能使用验证/测试日期之后的数据。
- 复权和停牌：必须记录处理策略，否则回测会失真。
- 基准同源：初始股票池与中证 800 基准高度重合，报告必须说明跑赢结果是在同源股票池内相对市值加权指数的表现。
- 回测偏差：手续费、滑点、涨跌停、幸存者偏差都要逐步纳入。
- LLM 误导：报告必须基于结构化结果，不允许凭空给交易结论。
