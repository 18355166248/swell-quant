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

## 关键风险

- 未来函数：标签和因子必须严格按时间切分。
- 数据泄漏：训练集不能使用验证/测试日期之后的数据。
- 复权和停牌：必须记录处理策略，否则回测会失真。
- 回测偏差：手续费、滑点、涨跌停、幸存者偏差都要逐步纳入。
- LLM 误导：报告必须基于结构化结果，不允许凭空给交易结论。
