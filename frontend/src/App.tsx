import { useMemo, useState, type ReactNode } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Empty,
  InputNumber,
  Layout,
  Menu,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Timeline,
  Typography,
  message,
} from "antd";
import {
  BarChartOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SettingOutlined,
  StockOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { api, type PredictionQuery, type TaskTrigger } from "./api/client";
import type {
  AcceptanceStatus,
  ArtifactStatus,
  BacktestPoint,
  BacktestSummary,
  DataQuality,
  DataQualityIssue,
  DataStatus,
  DuckDBStorageStatus,
  FeatureSummary,
  LabelSummary,
  LatestBacktest,
  LatestModel,
  LatestPredictions,
  LocalSettings,
  ModelSummary,
  PipelineRun,
  Prediction,
  ReportDetail,
  ReportSummary,
  ResearchStatus,
  StockFeature,
  StockPrediction,
  StockPrices,
  StockSummary,
  TaskDetail,
  TaskSummary,
} from "./types/api";

const { Header, Sider, Content } = Layout;
const { Title, Text, Paragraph } = Typography;

type PageKey =
  | "dashboard"
  | "acceptance"
  | "data"
  | "tasks"
  | "models"
  | "predictions"
  | "backtests"
  | "stocks"
  | "reports"
  | "settings";

interface PredictionFilters {
  date: string;
  modelVersion: string;
  topN: number;
}

function formatPercent(value?: number): string {
  if (value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : value.toFixed(4);
}

function formatFileSize(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

function statusColor(status?: string): string {
  if (status === "success") {
    return "green";
  }
  if (status === "failed") {
    return "red";
  }
  if (status === "busy") {
    return "orange";
  }
  return "default";
}

function storageStatusColor(status?: string): string {
  if (status === "healthy") {
    return "green";
  }
  if (status === "inconsistent" || status === "schema_mismatch") {
    return "red";
  }
  if (status === "incomplete" || status === "missing") {
    return "orange";
  }
  return "default";
}

function buildEquityOption(points: BacktestPoint[]) {
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["组合净值", "基准净值", "超额净值"] },
    grid: { top: 44, left: 48, right: 24, bottom: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => point.date),
    },
    yAxis: {
      type: "value",
      min: "dataMin",
      axisLabel: {
        formatter: (value: number) => value.toFixed(2),
      },
    },
    series: [
      {
        name: "组合净值",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((point) => point.portfolio_value),
      },
      {
        name: "基准净值",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((point) => point.benchmark_value),
      },
      {
        name: "超额净值",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((point) => point.excess_value),
      },
    ],
  };
}

function buildScoreOption(predictions: Prediction[]) {
  return {
    tooltip: { trigger: "axis" },
    grid: { top: 28, left: 44, right: 20, bottom: 34 },
    xAxis: {
      type: "category",
      data: predictions.map((row) => row.symbol),
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => value.toFixed(2),
      },
    },
    series: [
      {
        name: "预测分数",
        type: "bar",
        data: predictions.map((row) => row.score),
        itemStyle: { color: "#1f6feb" },
      },
    ],
  };
}

function buildStockPriceOption(data?: StockPrices) {
  const prices = data?.prices ?? [];
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["收盘价", "基准收盘"] },
    grid: { top: 44, left: 48, right: 24, bottom: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: prices.map((row) => row.date),
    },
    yAxis: {
      type: "value",
      min: "dataMin",
      axisLabel: {
        formatter: (value: number) => value.toFixed(0),
      },
    },
    series: [
      {
        name: "收盘价",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: prices.map((row) => row.close),
      },
      {
        name: "基准收盘",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: prices.map((row) => row.benchmark_close),
      },
    ],
  };
}

function buildStockFactorOption(features: StockFeature[]) {
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["5 日动量", "1 日收益", "成交量变化"] },
    grid: { top: 44, left: 48, right: 24, bottom: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: features.map((row) => row.date),
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => value.toFixed(2),
      },
    },
    series: [
      {
        name: "5 日动量",
        type: "line",
        showSymbol: false,
        data: features.map((row) => row.momentum_5d),
      },
      {
        name: "1 日收益",
        type: "line",
        showSymbol: false,
        data: features.map((row) => row.return_1d),
      },
      {
        name: "成交量变化",
        type: "line",
        showSymbol: false,
        data: features.map((row) => row.volume_change_1d),
      },
    ],
  };
}

function predictionColumns() {
  return [
    { title: "排名", dataIndex: "rank", width: 76, sorter: (a: Prediction, b: Prediction) => a.rank - b.rank },
    { title: "代码", dataIndex: "symbol", width: 120 },
    { title: "日期", dataIndex: "date", width: 120 },
    {
      title: "预测分数",
      dataIndex: "score",
      align: "right" as const,
      sorter: (a: Prediction, b: Prediction) => a.score - b.score,
      render: (value: number) => value.toFixed(4),
    },
    {
      title: "1 日收益",
      dataIndex: "return_1d",
      align: "right" as const,
      render: formatNumber,
    },
    {
      title: "5 日动量",
      dataIndex: "momentum_5d",
      align: "right" as const,
      render: formatNumber,
    },
    {
      title: "成交量变化",
      dataIndex: "volume_change_1d",
      align: "right" as const,
      render: formatNumber,
    },
  ];
}

function PageTitle({
  title,
  description,
  extra,
}: {
  title: string;
  description: string;
  extra?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <Title level={2}>{title}</Title>
        <Text type="secondary">{description}</Text>
      </div>
      {extra}
    </div>
  );
}

function DashboardPage({
  status,
  acceptance,
  dataStatus,
  model,
  models,
  quality,
  predictions,
  backtest,
  pipeline,
  report,
}: {
  status?: ResearchStatus;
  acceptance?: AcceptanceStatus;
  dataStatus?: DataStatus;
  model?: LatestModel;
  models: ModelSummary[];
  quality?: ResearchStatus["data_quality"];
  predictions: Prediction[];
  backtest?: LatestBacktest;
  pipeline?: PipelineRun;
  report?: string;
}) {
  const acceptanceStatus = acceptance ?? status?.acceptance;
  const acceptanceChecks = acceptanceStatus?.checks ?? [];
  return (
    <>
      <PageTitle
        title="研究工作台"
        description="查看离线研究链路、预测排名、回测结果和报告状态。"
        extra={<Tag color={statusColor(pipeline?.status)}>pipeline: {pipeline?.status ?? "unknown"}</Tag>}
      />

      <Row gutter={[16, 16]} className="metric-row">
        <Col xs={24} md={12} xl={6}>
          <Card>
            <Statistic
              title="数据行数"
              value={dataStatus?.row_count ?? quality?.row_count ?? 0}
              prefix={<DatabaseOutlined />}
            />
            <Text type="secondary">
              {dataStatus?.symbol_count ?? quality?.symbol_count ?? 0} 只标的，
              {dataStatus?.issue_count ?? quality?.issue_count ?? 0} 个质量问题
            </Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card>
            <Statistic title="最新预测" value={predictions.length} suffix="条" />
            <Text type="secondary">
              模型：{model?.model_version ?? predictions[0]?.model_version ?? status?.model.model_version ?? "-"}
            </Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card>
            <Statistic title="组合累计收益" value={formatPercent(backtest?.cumulative_return)} />
            <Text type="secondary">基准：{formatPercent(backtest?.benchmark_return)}</Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card>
            <Statistic title="超额收益" value={formatPercent(backtest?.excess_return)} />
            <Text type="secondary">回测：{backtest?.backtest_id ?? status?.backtest.backtest_id ?? "-"}</Text>
          </Card>
        </Col>
      </Row>

      <Card
        title="验收门禁"
        extra={
          <Tag color={acceptanceStatus?.passed ? "green" : "red"}>
            {acceptanceStatus?.status ?? "unknown"}
          </Tag>
        }
      >
        {acceptanceChecks.length > 0 ? (
          <Table<ResearchStatus["acceptance"]["checks"][number]>
            rowKey="key"
            size="small"
            pagination={false}
            dataSource={acceptanceChecks}
            columns={[
              { title: "检查项", dataIndex: "name" },
              {
                title: "状态",
                dataIndex: "status",
                width: 90,
                render: (value: string) => (
                  <Tag color={value === "passed" ? "green" : "red"}>
                    {value === "passed" ? "通过" : "失败"}
                  </Tag>
                ),
              },
              { title: "说明", dataIndex: "message" },
            ]}
          />
        ) : (
          <Empty description="暂无验收结果" />
        )}
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card title="最近预测 Top N">
            {predictions.length > 0 ? (
              <Table<Prediction>
                rowKey={(row) => `${row.date}-${row.symbol}-${row.rank}`}
                size="middle"
                pagination={false}
                dataSource={predictions}
                columns={predictionColumns()}
              />
            ) : (
              <Empty description="暂无预测结果" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="回测净值曲线">
            {backtest?.equity_curve?.length ? (
              <ReactECharts className="equity-chart" option={buildEquityOption(backtest.equity_curve)} />
            ) : (
              <Empty description="暂无回测曲线" />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="数据质量">
            <Space direction="vertical" size={8}>
              <Tag color={(dataStatus?.quality_passed ?? quality?.passed) ? "green" : "red"}>
                {(dataStatus?.quality_passed ?? quality?.passed) ? "质量检查通过" : "存在质量问题"}
              </Tag>
              <Text>
                覆盖区间：{dataStatus?.start_date ?? quality?.start_date ?? "-"} 至{" "}
                {dataStatus?.end_date ?? quality?.end_date ?? "-"}
              </Text>
              <Text type="secondary">当前样例链路使用可复现本地数据，后续会替换为真实 A 股日频数据源。</Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="模型状态">
            {models.length > 0 ? (
              <Table<ModelSummary>
                rowKey="model_version"
                size="small"
                pagination={false}
                dataSource={models}
                columns={[
                  { title: "版本", dataIndex: "model_version" },
                  { title: "类型", dataIndex: "model_type", width: 130 },
                  { title: "特征", dataIndex: "feature_count", width: 80, align: "right" },
                  { title: "预测日", dataIndex: "prediction_date", width: 120 },
                ]}
              />
            ) : (
              <Empty description="暂无模型产物" />
            )}
            <Descriptions className="model-summary" column={1} size="small">
              <Descriptions.Item label="训练区间">
                {model?.train_start ?? "-"} 至 {model?.train_end ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="样本行数">{model?.row_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="特征列表">
                {model?.feature_names?.join(", ") ?? "-"}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <Card title="研究报告预览">
            {report ? (
              <Paragraph className="report-preview">{report.split("\n").slice(0, 10).join("\n")}</Paragraph>
            ) : (
              <Empty description="暂无研究报告" />
            )}
          </Card>
        </Col>
      </Row>
    </>
  );
}

function AcceptancePage({
  acceptance,
  artifactStatus,
  pipeline,
  isRunning,
  onRunPipeline,
}: {
  acceptance?: AcceptanceStatus;
  artifactStatus?: ArtifactStatus;
  pipeline?: PipelineRun;
  isRunning: boolean;
  onRunPipeline: () => void;
}) {
  const checks = acceptance?.checks ?? [];
  const artifacts = artifactStatus?.artifacts ?? [];
  const passedCount = checks.filter((check) => check.status === "passed").length;
  return (
    <>
      <PageTitle
        title="验收门禁"
        description="检查离线研究链路是否达到当前阶段可用标准。"
        extra={
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            loading={isRunning}
            onClick={onRunPipeline}
          >
            运行 Pipeline
          </Button>
        }
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="验收状态"
              value={acceptance?.status ?? "unknown"}
              prefix={acceptance?.passed ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="通过检查" value={passedCount} suffix={`/ ${acceptance?.check_count ?? 0}`} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="失败检查" value={acceptance?.failed_count ?? 0} />
            <Text type="secondary">pipeline: {pipeline?.status ?? "unknown"}</Text>
          </Card>
        </Col>
      </Row>
      <Card title="检查项明细">
        {checks.length > 0 ? (
          <Table<AcceptanceStatus["checks"][number]>
            rowKey="key"
            size="middle"
            pagination={false}
            dataSource={checks}
            columns={[
              { title: "检查项", dataIndex: "name" },
              { title: "Key", dataIndex: "key", width: 210 },
              {
                title: "状态",
                dataIndex: "status",
                width: 100,
                render: (value: string) => (
                  <Tag color={value === "passed" ? "green" : "red"}>
                    {value === "passed" ? "通过" : "失败"}
                  </Tag>
                ),
              },
              { title: "说明", dataIndex: "message" },
            ]}
          />
        ) : (
          <Empty description="暂无验收结果" />
        )}
      </Card>
      <Card
        title="关键产物"
        extra={
          <Tag color={artifactStatus?.status === "complete" ? "green" : "red"}>
            {artifactStatus?.status ?? "unknown"}
          </Tag>
        }
      >
        {artifacts.length > 0 ? (
          <Table<ArtifactStatus["artifacts"][number]>
            rowKey="name"
            size="middle"
            pagination={false}
            dataSource={artifacts}
            columns={[
              { title: "产物", dataIndex: "name", width: 180 },
              { title: "路径", dataIndex: "path" },
              {
                title: "大小",
                dataIndex: "size_bytes",
                align: "right",
                width: 120,
                render: formatFileSize,
              },
              {
                title: "更新时间",
                dataIndex: "updated_at",
                width: 180,
                render: formatDateTime,
              },
              {
                title: "状态",
                dataIndex: "exists",
                width: 100,
                render: (exists: boolean) => (
                  <Tag color={exists ? "green" : "red"}>{exists ? "存在" : "缺失"}</Tag>
                ),
              },
            ]}
          />
        ) : (
          <Empty description="暂无产物状态" />
        )}
      </Card>
      <Alert
        className="page-alert"
        type="info"
        showIcon
        message="研究用途声明"
        description={acceptance?.disclaimer ?? "仅用于研究，不构成投资建议"}
      />
    </>
  );
}

function TasksPage({
  tasks,
  taskDetail,
  onRunTask,
  isRunning,
}: {
  tasks: TaskSummary[];
  taskDetail?: TaskDetail;
  onRunTask: (task: TaskTrigger) => void;
  isRunning: boolean;
}) {
  const steps = taskDetail?.steps ?? [];
  const taskTriggers: Array<{ key: TaskTrigger; label: string }> = [
    { key: "pipeline", label: "完整 pipeline" },
    { key: "data_update", label: "更新数据" },
    { key: "model_train", label: "训练模型" },
    { key: "prediction_run", label: "生成预测" },
    { key: "backtest_run", label: "运行回测" },
    { key: "report_generate", label: "生成报告" },
  ];
  const timelineItems = steps.map((step) => ({
    color: step.status === "success" ? "green" : step.status === "failed" ? "red" : "gray",
    dot: step.status === "success" ? <CheckCircleOutlined /> : step.status === "failed" ? <CloseCircleOutlined /> : undefined,
    children: (
      <Space direction="vertical" size={2}>
        <Space>
          <Text strong>{step.name}</Text>
          <Tag color={statusColor(step.status)}>{step.status}</Tag>
          <Text type="secondary">{step.duration_seconds.toFixed(4)}s</Text>
        </Space>
        <Text type="secondary">{step.message}</Text>
      </Space>
    ),
  }));

  return (
    <>
      <PageTitle
        title="任务中心"
        description="查看离线 pipeline 的最近运行步骤、耗时、产物路径和失败位置。"
        extra={
          <Space wrap>
            {taskTriggers.map((trigger) => (
              <Button
                key={trigger.key}
                icon={<ReloadOutlined />}
                loading={isRunning}
                onClick={() => onRunTask(trigger.key)}
              >
                {trigger.label}
              </Button>
            ))}
          </Space>
        }
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="任务列表">
            <Table<TaskSummary>
              rowKey="id"
              size="small"
              dataSource={tasks}
              pagination={false}
              columns={[
                { title: "任务", dataIndex: "id" },
                {
                  title: "状态",
                  dataIndex: "status",
                  width: 92,
                  render: (status: string) => <Tag color={statusColor(status)}>{status}</Tag>,
                },
              ]}
            />
            <Divider />
            <Descriptions column={1} size="small">
              <Descriptions.Item label="类型">{taskDetail?.type ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="开始时间">{taskDetail?.started_at ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="结束时间">{taskDetail?.ended_at ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="耗时">
                {taskDetail?.duration_seconds === null || taskDetail?.duration_seconds === undefined
                  ? "-"
                  : `${taskDetail.duration_seconds.toFixed(4)}s`}
              </Descriptions.Item>
              <Descriptions.Item label="失败阶段">{taskDetail?.failed_step ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="输出">{taskDetail?.output_path ?? "-"}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} xl={16}>
          <Card title="步骤明细">
            {timelineItems.length > 0 ? <Timeline items={timelineItems} /> : <Empty description="暂无 pipeline 记录" />}
          </Card>
        </Col>
      </Row>
    </>
  );
}

function DataPage({
  dataStatus,
  duckdbStorage,
  quality,
  features,
  labels,
}: {
  dataStatus?: DataStatus;
  duckdbStorage?: DuckDBStorageStatus;
  quality?: DataQuality;
  features?: FeatureSummary;
  labels?: LabelSummary;
}) {
  const issues = quality?.issues ?? [];
  const featureRows = features?.feature_names.map((featureName) => ({
    featureName,
    nonNullCount: features.non_null_counts[featureName] ?? 0,
    coverage: features.row_count > 0 ? (features.non_null_counts[featureName] ?? 0) / features.row_count : 0,
  })) ?? [];
  const labelRate = labels?.labeled_row_count && labels.labeled_row_count > 0
    ? labels.positive_count / labels.labeled_row_count
    : 0;
  return (
    <>
      <PageTitle
        title="数据"
        description="查看 A 股日频样例数据的覆盖范围、质量门禁和异常明细。"
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="数据行数" value={dataStatus?.row_count ?? quality?.row_count ?? 0} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="标的数量" value={dataStatus?.symbol_count ?? quality?.symbol_count ?? 0} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="质量问题" value={dataStatus?.issue_count ?? quality?.issue_count ?? 0} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card>
            <Statistic title="质量状态" value={(dataStatus?.quality_passed ?? quality?.passed) ? "通过" : "需检查"} />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="数据口径">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="市场">{dataStatus?.market ?? "A_SHARE_DAILY"}</Descriptions.Item>
              <Descriptions.Item label="股票池">{dataStatus?.universe ?? "sample_a_share"}</Descriptions.Item>
              <Descriptions.Item label="股票池名称">{dataStatus?.universe_name ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="v1 目标股票池">
                {dataStatus?.target_universe ?? "-"}（约 {dataStatus?.target_universe_size ?? "-"} 只）
              </Descriptions.Item>
              <Descriptions.Item label="基准">
                {dataStatus?.benchmark_name ?? "-"}（{dataStatus?.benchmark ?? "-"}）
              </Descriptions.Item>
              <Descriptions.Item label="基准兜底">{dataStatus?.benchmark_fallback ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="复权口径">{dataStatus?.adjustment ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="更新方式">{dataStatus?.update_mode ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="开始日期">
                {dataStatus?.start_date ?? quality?.start_date ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="结束日期">
                {dataStatus?.end_date ?? quality?.end_date ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="声明">
                {dataStatus?.disclaimer ?? "仅用于研究，不构成投资建议"}
              </Descriptions.Item>
            </Descriptions>
            {dataStatus?.benchmark_same_source ? (
              <Alert
                className="page-alert"
                type="warning"
                showIcon
                message="基准同源说明"
                description={dataStatus.benchmark_note}
              />
            ) : null}
          </Card>
        </Col>
        <Col xs={24} xl={16}>
          <Card title="DuckDB 本地存储">
            <Descriptions column={2} size="small">
              <Descriptions.Item label="状态">
                <Tag color={storageStatusColor(duckdbStorage?.status)}>
                  {duckdbStorage?.status ?? "unknown"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="总行数">{duckdbStorage?.total_rows ?? 0}</Descriptions.Item>
              <Descriptions.Item label="缺失表">
                {duckdbStorage?.missing_tables.length ? duckdbStorage.missing_tables.join(", ") : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="不一致表">
                {duckdbStorage?.inconsistent_tables.length ? duckdbStorage.inconsistent_tables.join(", ") : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="字段异常表">
                {duckdbStorage?.schema_mismatch_tables.length ? duckdbStorage.schema_mismatch_tables.join(", ") : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="文件大小">
                {duckdbStorage?.file_size_bytes ? `${duckdbStorage.file_size_bytes} bytes` : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="路径">{duckdbStorage?.path ?? "-"}</Descriptions.Item>
            </Descriptions>
            <Table
              rowKey="name"
              size="small"
              dataSource={duckdbStorage?.tables ?? []}
              pagination={false}
              columns={[
                { title: "表名", dataIndex: "name" },
                {
                  title: "状态",
                  dataIndex: "exists",
                  width: 90,
                  render: (exists: boolean) => (
                    <Tag color={exists ? "green" : "red"}>{exists ? "存在" : "缺失"}</Tag>
                  ),
                },
                { title: "DuckDB 行数", dataIndex: "row_count", align: "right", render: (value) => value ?? "-" },
                {
                  title: "CSV 行数",
                  dataIndex: "source_row_count",
                  align: "right",
                  render: (value) => value ?? "-",
                },
                {
                  title: "一致性",
                  dataIndex: "row_count_matches",
                  width: 90,
                  render: (matches) => {
                    if (matches === null || matches === undefined) {
                      return "-";
                    }
                    return <Tag color={matches ? "green" : "red"}>{matches ? "一致" : "不一致"}</Tag>;
                  },
                },
                {
                  title: "字段",
                  dataIndex: "schema_matches",
                  width: 90,
                  render: (matches) => {
                    if (matches === null || matches === undefined) {
                      return "-";
                    }
                    return <Tag color={matches ? "green" : "red"}>{matches ? "匹配" : "异常"}</Tag>;
                  },
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <Card title="质量问题明细">
            {issues.length > 0 ? (
              <Table<DataQualityIssue>
                rowKey={(row, index) => `${row.code}-${row.symbol ?? "all"}-${row.date ?? index}`}
                size="middle"
                dataSource={issues}
                pagination={{ pageSize: 8, hideOnSinglePage: true }}
                columns={[
                  { title: "代码", dataIndex: "code", width: 150 },
                  {
                    title: "级别",
                    dataIndex: "severity",
                    width: 100,
                    render: (severity: string) => (
                      <Tag color={severity === "error" ? "red" : "orange"}>{severity}</Tag>
                    ),
                  },
                  { title: "标的", dataIndex: "symbol", width: 120, render: (value) => value ?? "-" },
                  { title: "日期", dataIndex: "date", width: 120, render: (value) => value ?? "-" },
                  { title: "说明", dataIndex: "message" },
                ]}
              />
            ) : (
              <Empty description="暂无质量问题" />
            )}
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="因子覆盖">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="行数">{features?.row_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="标的数量">{features?.symbol_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="日期范围">
                {features?.start_date ?? "-"} 至 {features?.end_date ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="声明">
                {features?.disclaimer ?? "仅用于研究，不构成投资建议"}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} xl={16}>
          <Card title="特征非空率">
            <Table
              rowKey="featureName"
              size="middle"
              dataSource={featureRows}
              pagination={false}
              columns={[
                { title: "特征名", dataIndex: "featureName" },
                { title: "非空行数", dataIndex: "nonNullCount", width: 120, align: "right" },
                {
                  title: "覆盖率",
                  dataIndex: "coverage",
                  width: 120,
                  align: "right",
                  render: formatPercent,
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
      <Card title="最近因子样本">
        <Table
          rowKey={(row: FeatureSummary["latest_samples"][number]) => `${row.date}-${row.symbol}`}
          size="middle"
          dataSource={features?.latest_samples ?? []}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          columns={[
            { title: "日期", dataIndex: "date", width: 120 },
            { title: "代码", dataIndex: "symbol", width: 120 },
            { title: "收盘价", dataIndex: "close", align: "right", render: (value: number) => value.toFixed(4) },
            { title: "1 日收益", dataIndex: "return_1d", align: "right", render: formatNumber },
            { title: "5 日动量", dataIndex: "momentum_5d", align: "right", render: formatNumber },
            { title: "MA5", dataIndex: "ma_5", align: "right", render: formatNumber },
            { title: "成交量变化", dataIndex: "volume_change_1d", align: "right", render: formatNumber },
          ]}
        />
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="标签覆盖">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="行数">{labels?.row_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="可训练标签">{labels?.labeled_row_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="未成熟标签">{labels?.unlabeled_row_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="跑赢样本">{labels?.positive_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="未跑赢样本">{labels?.negative_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="跑赢占比">{formatPercent(labelRate)}</Descriptions.Item>
              <Descriptions.Item label="预测 horizon">{labels?.horizon_days ?? "-"} 日</Descriptions.Item>
              <Descriptions.Item label="标签窗口">{labels?.label_window ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="入场价">{labels?.entry_price ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="出场价">{labels?.exit_price ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="日期范围">
                {labels?.start_date ?? "-"} 至 {labels?.end_date ?? "-"}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} xl={16}>
          <Card title="最近标签样本">
            <Table
              rowKey={(row: LabelSummary["latest_samples"][number]) => `${row.date}-${row.symbol}`}
              size="middle"
              dataSource={labels?.latest_samples ?? []}
              pagination={{ pageSize: 8, hideOnSinglePage: true }}
              columns={[
                { title: "日期", dataIndex: "date", width: 120 },
                { title: "代码", dataIndex: "symbol", width: 120 },
                { title: "未来 5 日收益", dataIndex: "future_5d_return", align: "right", render: formatNumber },
                { title: "基准 5 日收益", dataIndex: "benchmark_5d_return", align: "right", render: formatNumber },
                {
                  title: "是否跑赢",
                  dataIndex: "outperform_benchmark_5d",
                  width: 110,
                  render: (value: number | null) => (value === null ? "-" : value === 1 ? "是" : "否"),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
      <Alert
        className="page-alert"
        type="info"
        showIcon
        message="数据说明"
        description="标签使用 T+1 开盘到 T+5 收盘的未来持有期收益，只能作为监督训练和离线评估目标，不允许进入同日特征或预测排序。"
      />
    </>
  );
}

function ModelsPage({
  models,
  model,
  selectedModelVersion,
  onSelectModel,
}: {
  models: ModelSummary[];
  model?: LatestModel;
  selectedModelVersion: string;
  onSelectModel: (modelVersion: string) => void;
}) {
  const featureRows = model?.feature_names.map((featureName, index) => ({
    featureName,
    index: index + 1,
  })) ?? [];
  const metricRows = Object.entries(model?.metrics ?? {}).map(([name, value]) => ({
    name,
    value: typeof value === "number" ? formatNumber(value) : (value ?? "-"),
  }));
  return (
    <>
      <PageTitle
        title="模型"
        description="查看模型版本、训练区间、特征列表和本地产物路径。"
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card title="模型列表">
            <Table<ModelSummary>
              rowKey="model_version"
              size="middle"
              dataSource={models}
              pagination={false}
              onRow={(record) => ({
                onClick: () => onSelectModel(record.model_version),
              })}
              rowClassName={(record) =>
                record.model_version === selectedModelVersion ? "selected-table-row" : ""
              }
              columns={[
                { title: "版本", dataIndex: "model_version" },
                { title: "类型", dataIndex: "model_type", width: 130 },
                { title: "特征", dataIndex: "feature_count", width: 80, align: "right" },
                { title: "预测日", dataIndex: "prediction_date", width: 120 },
                {
                  title: "评估",
                  dataIndex: "evaluation_status",
                  width: 120,
                  render: (value: string) => (
                    <Tag color={value === "ready" ? "green" : "orange"}>{value}</Tag>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card title="模型详情">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="模型版本">{model?.model_version ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="模型类型">{model?.model_type ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="训练区间">
                {model?.train_start ?? "-"} 至 {model?.train_end ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="预测日期">{model?.prediction_date ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="训练样本行数">{model?.row_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="特征数量">{model?.feature_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="标签 Gap">{model?.label_gap_days ?? "-"} 个交易日</Descriptions.Item>
              <Descriptions.Item label="评估状态">{model?.evaluation_status ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="评估训练窗">
                {model?.evaluation_train_start ?? "-"} 至 {model?.evaluation_train_end ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="验证窗">
                {model?.validation_start ?? "-"} 至 {model?.validation_end ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="测试窗">
                {model?.test_start ?? "-"} 至 {model?.test_end ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="产物路径">{model?.path ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{model?.updated_at ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="声明">
                {model?.disclaimer ?? "仅用于研究，不构成投资建议"}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
      <Card title="特征列表">
        {featureRows.length > 0 ? (
          <Table
            rowKey="featureName"
            size="middle"
            dataSource={featureRows}
            pagination={false}
            columns={[
              { title: "#", dataIndex: "index", width: 80, align: "right" },
              { title: "特征名", dataIndex: "featureName" },
            ]}
          />
        ) : (
          <Empty description="暂无特征列表" />
        )}
      </Card>
      <Card title="评估指标">
        {metricRows.length > 0 ? (
          <Table
            rowKey="name"
            size="middle"
            dataSource={metricRows}
            pagination={false}
            columns={[
              { title: "指标", dataIndex: "name" },
              { title: "值", dataIndex: "value", width: 180, align: "right" },
            ]}
          />
        ) : (
          <Empty description="暂无评估指标" />
        )}
      </Card>
      <Alert
        className="page-alert"
        type="info"
        showIcon
        message="模型说明"
        description="当前 baseline 是可复现规则模型，用于验证离线链路；后续接入 LightGBM 后沿用相同模型版本和特征追踪口径。"
      />
    </>
  );
}

function PredictionsPage({
  predictions,
  filters,
  appliedFilters,
  dateOptions,
  modelOptions,
  onFiltersChange,
}: {
  predictions: Prediction[];
  filters: PredictionFilters;
  appliedFilters?: LatestPredictions["filters"];
  dateOptions: string[];
  modelOptions: string[];
  onFiltersChange: (filters: PredictionFilters) => void;
}) {
  return (
    <>
      <PageTitle
        title="预测"
        description="按交易日、模型版本和 Top N 查询预测排名。预测分数仅用于研究，不构成投资建议。"
      />
      <Card className="filter-card" title="筛选条件">
        <Space wrap>
          <Select
            className="date-filter"
            allowClear
            showSearch
            placeholder="交易日"
            value={filters.date || undefined}
            options={dateOptions.map((date) => ({ label: date, value: date }))}
            onChange={(value) => onFiltersChange({ ...filters, date: value ?? "" })}
          />
          <Select
            className="model-filter"
            allowClear
            placeholder="模型版本"
            value={filters.modelVersion || undefined}
            options={modelOptions.map((modelVersion) => ({ label: modelVersion, value: modelVersion }))}
            onChange={(value) => onFiltersChange({ ...filters, modelVersion: value ?? "" })}
          />
          <InputNumber
            className="topn-filter"
            min={0}
            max={100}
            value={filters.topN}
            onChange={(value) => onFiltersChange({ ...filters, topN: value ?? 10 })}
          />
          <Tag color="blue">生效日期：{appliedFilters?.date ?? "latest"}</Tag>
          <Tag color="blue">生效模型：{appliedFilters?.model_version ?? "all"}</Tag>
          <Tag color="blue">Top N：{appliedFilters?.top_n ?? filters.topN}</Tag>
        </Space>
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={9}>
          <Card title="预测分数分布">
            {predictions.length > 0 ? (
              <ReactECharts className="score-chart" option={buildScoreOption(predictions)} />
            ) : (
              <Empty description="暂无预测结果" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={15}>
          <Card title="Top N 排名">
            <Table<Prediction>
              rowKey={(row) => `${row.date}-${row.symbol}-${row.rank}`}
              size="middle"
              dataSource={predictions}
              columns={predictionColumns()}
              pagination={{ pageSize: 10, hideOnSinglePage: true }}
            />
          </Card>
        </Col>
      </Row>
      <Alert
        className="page-alert"
        type="info"
        showIcon
        message="研究口径"
        description="当前 baseline 使用动量、短期收益和成交量变化构造可复现预测分数；后续真实模型接入后仍需展示模型版本、数据日期和停牌涨跌停处理。"
      />
    </>
  );
}

function BacktestsPage({
  backtests,
  backtest,
  selectedBacktestId,
  onSelectBacktest,
}: {
  backtests: BacktestSummary[];
  backtest?: LatestBacktest;
  selectedBacktestId: string;
  onSelectBacktest: (backtestId: string) => void;
}) {
  return (
    <>
      <PageTitle title="回测" description="查看最近 Top N 回测指标、净值曲线和历史回测口径。" />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="累计收益" value={formatPercent(backtest?.cumulative_return)} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="基准收益" value={formatPercent(backtest?.benchmark_return)} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="超额收益" value={formatPercent(backtest?.excess_return)} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="交易次数" value={backtest?.trade_count ?? 0} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="年化收益" value={formatPercent(backtest?.annualized_return)} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="最大回撤" value={formatPercent(backtest?.max_drawdown)} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="夏普比率" value={formatNumber(backtest?.sharpe_ratio)} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="胜率" value={formatPercent(backtest?.win_rate)} /></Card>
        </Col>
      </Row>
      <Card title="逐期回测明细">
        <Table<BacktestPoint>
          rowKey={(row) => `${row.signal_date}-${row.date}`}
          size="middle"
          dataSource={backtest?.equity_curve ?? []}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          columns={[
            { title: "信号日", dataIndex: "signal_date", width: 120 },
            { title: "成交日", dataIndex: "date", width: 120 },
            {
              title: "组合收益",
              dataIndex: "portfolio_return",
              align: "right",
              render: formatPercent,
              sorter: (a, b) => a.portfolio_return - b.portfolio_return,
            },
            {
              title: "基准收益",
              dataIndex: "benchmark_return",
              align: "right",
              render: formatPercent,
              sorter: (a, b) => a.benchmark_return - b.benchmark_return,
            },
            {
              title: "组合净值",
              dataIndex: "portfolio_value",
              align: "right",
              render: (value: number) => value.toFixed(4),
            },
            {
              title: "基准净值",
              dataIndex: "benchmark_value",
              align: "right",
              render: (value: number) => value.toFixed(4),
            },
            {
              title: "超额净值",
              dataIndex: "excess_value",
              align: "right",
              render: (value: number) => value.toFixed(4),
            },
          ]}
        />
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="回测列表">
            <Table<BacktestSummary>
              rowKey="backtest_id"
              size="small"
              dataSource={backtests}
              pagination={false}
              onRow={(record) => ({
                onClick: () => onSelectBacktest(record.backtest_id),
              })}
              rowClassName={(record) =>
                record.backtest_id === selectedBacktestId ? "selected-table-row" : ""
              }
              columns={[
                { title: "ID", dataIndex: "backtest_id" },
                {
                  title: "超额",
                  dataIndex: "excess_return",
                  width: 96,
                  align: "right",
                  render: formatPercent,
                },
                {
                  title: "回撤",
                  dataIndex: "max_drawdown",
                  width: 96,
                  align: "right",
                  render: formatPercent,
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="净值曲线">
            {backtest?.equity_curve?.length ? (
              <ReactECharts className="large-chart" option={buildEquityOption(backtest.equity_curve)} />
            ) : (
              <Empty description="暂无回测曲线" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={6}>
          <Card title="回测参数">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="回测 ID">{backtest?.backtest_id ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="模型版本">{backtest?.model_version ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="Top N">{backtest?.top_n ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="手续费率">{formatPercent(backtest?.fee_rate)}</Descriptions.Item>
              <Descriptions.Item label="滑点率">{formatPercent(backtest?.slippage_rate)}</Descriptions.Item>
              <Descriptions.Item label="成交价">{backtest?.execution_price ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="持有期">{backtest?.holding_period ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="调仓规则">{backtest?.rebalance_rule ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="开始日期">{backtest?.start_date ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="结束日期">{backtest?.end_date ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="平均换手率">{formatPercent(backtest?.turnover_rate)}</Descriptions.Item>
              <Descriptions.Item label="声明">{backtest?.disclaimer ?? "仅用于研究，不构成投资建议"}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
    </>
  );
}

function StocksPage({
  symbol,
  symbols,
  stockSummaries,
  onSymbolChange,
  summary,
  prices,
  features,
  stockPredictions,
  isLoading,
}: {
  symbol: string;
  symbols: string[];
  stockSummaries: StockSummary[];
  onSymbolChange: (symbol: string) => void;
  summary?: StockSummary;
  prices?: StockPrices;
  features: StockFeature[];
  stockPredictions: StockPrediction[];
  isLoading: boolean;
}) {
  return (
    <>
      <PageTitle
        title="单股"
        description="查看单只标的的行情覆盖、因子走势和历史预测表现。历史预测仅用于研究解释。"
        extra={
          <Select
            className="symbol-select"
            value={symbol}
            options={symbols.map((item) => ({ label: item, value: item }))}
            onChange={onSymbolChange}
          />
        }
      />
      <Spin spinning={isLoading}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12} xl={6}>
            <Card><Statistic title="价格行数" value={summary?.price_row_count ?? 0} /></Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card><Statistic title="历史预测" value={summary?.prediction_row_count ?? 0} suffix="条" /></Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card><Statistic title="开始日期" value={summary?.start_date ?? "-"} /></Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card><Statistic title="结束日期" value={summary?.end_date ?? "-"} /></Card>
          </Col>
        </Row>

        <Card title="股票池覆盖">
          <Table<StockSummary>
            rowKey="symbol"
            size="middle"
            dataSource={stockSummaries}
            pagination={{ pageSize: 8, hideOnSinglePage: true }}
            onRow={(record) => ({
              onClick: () => onSymbolChange(record.symbol),
            })}
            rowClassName={(record) => (record.symbol === symbol ? "selected-table-row" : "")}
            columns={[
              { title: "代码", dataIndex: "symbol", width: 140 },
              {
                title: "价格行数",
                dataIndex: "price_row_count",
                width: 120,
                align: "right",
                sorter: (a, b) => a.price_row_count - b.price_row_count,
              },
              {
                title: "历史预测",
                dataIndex: "prediction_row_count",
                width: 120,
                align: "right",
                sorter: (a, b) => a.prediction_row_count - b.prediction_row_count,
              },
              { title: "开始日期", dataIndex: "start_date", width: 130, render: (value) => value ?? "-" },
              { title: "结束日期", dataIndex: "end_date", width: 130, render: (value) => value ?? "-" },
            ]}
          />
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={12}>
            <Card title="价格走势">
              {prices?.prices.length ? (
                <ReactECharts className="large-chart" option={buildStockPriceOption(prices)} />
              ) : (
                <Empty description="暂无价格数据" />
              )}
            </Card>
          </Col>
          <Col xs={24} xl={12}>
            <Card title="因子走势">
              {features.length ? (
                <ReactECharts className="large-chart" option={buildStockFactorOption(features)} />
              ) : (
                <Empty description="暂无因子数据" />
              )}
            </Card>
          </Col>
        </Row>

        <Card title="历史预测">
          <Table<StockPrediction>
            rowKey={(row) => `${row.date}-${row.rank}-${row.score}`}
            size="middle"
            dataSource={stockPredictions}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            columns={[
              { title: "日期", dataIndex: "date", width: 120 },
              { title: "模型版本", dataIndex: "model_version", width: 160 },
              {
                title: "排名",
                dataIndex: "rank",
                width: 90,
                sorter: (a, b) => a.rank - b.rank,
              },
              {
                title: "预测分数",
                dataIndex: "score",
                align: "right",
                sorter: (a, b) => a.score - b.score,
                render: (value: number) => value.toFixed(4),
              },
              {
                title: "1 日收益",
                dataIndex: "return_1d",
                align: "right",
                render: formatNumber,
              },
              {
                title: "5 日动量",
                dataIndex: "momentum_5d",
                align: "right",
                render: formatNumber,
              },
              {
                title: "成交量变化",
                dataIndex: "volume_change_1d",
                align: "right",
                render: formatNumber,
              },
            ]}
          />
        </Card>
        <Alert
          className="page-alert"
          type="info"
          showIcon
          message="研究声明"
          description={summary?.disclaimer ?? "仅用于研究，不构成投资建议"}
        />
      </Spin>
    </>
  );
}

function ReportsPage({
  reports,
  report,
  selectedReportId,
  onSelectReport,
  status,
  qualityIssues,
}: {
  reports: ReportSummary[];
  report?: ReportDetail;
  selectedReportId: string;
  onSelectReport: (reportId: string) => void;
  status?: ResearchStatus;
  qualityIssues: DataQualityIssue[];
}) {
  const riskItems = [
    `当前模型版本：${status?.model.model_version ?? "-"}`,
    `数据覆盖：${status?.data_quality.start_date ?? "-"} 至 ${status?.data_quality.end_date ?? "-"}`,
    `数据质量问题：${status?.data_quality.issue_count ?? 0} 个`,
    "历史回测不代表未来表现，预测结果不能作为交易依据。",
  ];

  return (
    <>
      <PageTitle title="报告" description="展示离线研究报告和结构化风险提示。" />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={6}>
          <Card title="报告列表">
            <Table<ReportSummary>
              rowKey="report_id"
              size="small"
              dataSource={reports}
              pagination={false}
              onRow={(record) => ({
                onClick: () => onSelectReport(record.report_id),
              })}
              rowClassName={(record) =>
                record.report_id === selectedReportId ? "selected-table-row" : ""
              }
              columns={[
                { title: "报告", dataIndex: "title" },
                {
                  title: "状态",
                  dataIndex: "report_id",
                  width: 80,
                  render: () => <Tag color="green">可读</Tag>,
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={11}>
          <Card title="报告正文">
            {report?.body ? (
              <Paragraph className="report-body">{report.body}</Paragraph>
            ) : (
              <Empty description="暂无研究报告" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={7}>
          <Card title="结构化依据">
            <Space direction="vertical" size={10}>
              <Text>报告 ID：{report?.report_id ?? "-"}</Text>
              <Text>模型版本：{report?.model_version ?? status?.model.model_version ?? "-"}</Text>
              <Text>回测 ID：{report?.backtest_id ?? status?.backtest.backtest_id ?? "-"}</Text>
              {riskItems.map((item) => (
                <Text key={item}>{item}</Text>
              ))}
            </Space>
            <Divider />
            <Title level={5}>数据质量问题</Title>
            {qualityIssues.length > 0 ? (
              <Space direction="vertical" size={8}>
                {qualityIssues.map((issue) => (
                  <Alert key={`${issue.code}-${issue.symbol}-${issue.date}`} type="warning" message={issue.message} />
                ))}
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无质量问题" />
            )}
          </Card>
        </Col>
      </Row>
    </>
  );
}

function SettingsPage({
  settings,
  artifactStatus,
}: {
  settings?: LocalSettings;
  artifactStatus?: ArtifactStatus;
}) {
  const artifacts = artifactStatus?.artifacts ?? settings?.artifacts ?? [];
  return (
    <>
      <PageTitle title="设置" description="查看本地研究环境、数据目录、API key 配置状态和关键产物是否存在。" />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card title="服务状态">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="服务">{settings?.service.name ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="模式">{settings?.service.mode ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="数据目录">{settings?.paths.data_dir ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="DuckDB">{settings?.paths.duckdb_path ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="声明">
                {settings?.service.disclaimer ?? "仅用于研究，不构成投资建议"}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card title="配置与产物">
            <Row gutter={[16, 16]} className="settings-key-row">
              <Col xs={24} md={12}>
                <Card size="small">
                  <Statistic
                    title="DeepSeek Key"
                    value={settings?.api_keys.deepseek_configured ? "已配置" : "未配置"}
                  />
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card size="small">
                  <Statistic
                    title="OpenAI Key"
                    value={settings?.api_keys.openai_configured ? "已配置" : "未配置"}
                  />
                </Card>
              </Col>
            </Row>
            <Table
              rowKey="name"
              size="middle"
              dataSource={artifacts}
              pagination={false}
              columns={[
                { title: "产物", dataIndex: "name", width: 180 },
                { title: "路径", dataIndex: "path" },
                {
                  title: "大小",
                  dataIndex: "size_bytes",
                  align: "right",
                  width: 120,
                  render: formatFileSize,
                },
                {
                  title: "更新时间",
                  dataIndex: "updated_at",
                  width: 180,
                  render: formatDateTime,
                },
                {
                  title: "状态",
                  dataIndex: "exists",
                  width: 120,
                  render: (exists: boolean) => (
                    <Tag color={exists ? "green" : "orange"}>{exists ? "存在" : "缺失"}</Tag>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
      <Alert
        className="page-alert"
        type="info"
        showIcon
        message="安全说明"
        description="设置页只展示 API key 是否配置，不展示任何 secret 明文。"
      />
    </>
  );
}

function App() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [activePage, setActivePage] = useState<PageKey>("dashboard");
  const [selectedSymbol, setSelectedSymbol] = useState("000300.SH");
  const [selectedBacktestId, setSelectedBacktestId] = useState("sample-topn-baseline");
  const [selectedReportId, setSelectedReportId] = useState("sample-research-summary");
  const [selectedModelVersion, setSelectedModelVersion] = useState("baseline-rule-v1");
  const [predictionFilters, setPredictionFilters] = useState<PredictionFilters>({
    date: "",
    modelVersion: "",
    topN: 10,
  });

  const statusQuery = useQuery({ queryKey: ["status"], queryFn: api.getStatus });
  const acceptanceQuery = useQuery({ queryKey: ["acceptance"], queryFn: api.getAcceptance });
  const artifactsQuery = useQuery({ queryKey: ["artifacts"], queryFn: api.getArtifacts });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const pipelineQuery = useQuery({ queryKey: ["pipeline"], queryFn: api.getPipeline });
  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: api.getTasks });
  const taskDetailQuery = useQuery({
    queryKey: ["tasks", "pipeline-latest"],
    queryFn: () => api.getTaskDetail("pipeline-latest"),
  });
  const dataStatusQuery = useQuery({ queryKey: ["data-status"], queryFn: api.getDataStatus });
  const duckdbStorageQuery = useQuery({ queryKey: ["duckdb-storage"], queryFn: api.getDuckDBStorage });
  const qualityQuery = useQuery({ queryKey: ["data-quality"], queryFn: api.getDataQuality });
  const featuresQuery = useQuery({ queryKey: ["features"], queryFn: api.getFeatures });
  const labelsQuery = useQuery({ queryKey: ["labels"], queryFn: api.getLabels });
  const latestModelQuery = useQuery({ queryKey: ["model", "latest"], queryFn: api.getLatestModel });
  const modelsQuery = useQuery({ queryKey: ["models"], queryFn: api.getModels });
  const modelDetailQuery = useQuery({
    queryKey: ["models", selectedModelVersion],
    queryFn: () => api.getModel(selectedModelVersion),
    enabled: selectedModelVersion.length > 0,
  });
  const predictionsQuery = useQuery({
    queryKey: ["predictions", "latest"],
    queryFn: api.getLatestPredictions,
  });
  const predictionQueryParams: PredictionQuery = {
    date: predictionFilters.date || null,
    modelVersion: predictionFilters.modelVersion || null,
    topN: predictionFilters.topN,
  };
  const predictionsListQuery = useQuery({
    queryKey: ["predictions", "list", predictionQueryParams],
    queryFn: () => api.getPredictions(predictionQueryParams),
  });
  const backtestQuery = useQuery({
    queryKey: ["backtest", "latest"],
    queryFn: api.getLatestBacktest,
  });
  const backtestsQuery = useQuery({ queryKey: ["backtests"], queryFn: api.getBacktests });
  const backtestDetailQuery = useQuery({
    queryKey: ["backtests", selectedBacktestId],
    queryFn: () => api.getBacktest(selectedBacktestId),
    enabled: selectedBacktestId.length > 0,
  });
  const reportQuery = useQuery({ queryKey: ["report"], queryFn: api.getReport });
  const reportsQuery = useQuery({ queryKey: ["reports"], queryFn: api.getReports });
  const reportDetailQuery = useQuery({
    queryKey: ["reports", selectedReportId],
    queryFn: () => api.getReportDetail(selectedReportId),
    enabled: selectedReportId.length > 0,
  });
  const stocksQuery = useQuery({ queryKey: ["stocks"], queryFn: api.getStocks });
  const stockSummaryQuery = useQuery({
    queryKey: ["stocks", selectedSymbol, "summary"],
    queryFn: () => api.getStockSummary(selectedSymbol),
    enabled: selectedSymbol.length > 0,
  });
  const stockPricesQuery = useQuery({
    queryKey: ["stocks", selectedSymbol, "prices"],
    queryFn: () => api.getStockPrices(selectedSymbol),
    enabled: selectedSymbol.length > 0,
  });
  const stockFeaturesQuery = useQuery({
    queryKey: ["stocks", selectedSymbol, "features"],
    queryFn: () => api.getStockFeatures(selectedSymbol),
    enabled: selectedSymbol.length > 0,
  });
  const stockPredictionsQuery = useQuery({
    queryKey: ["stocks", selectedSymbol, "predictions"],
    queryFn: () => api.getStockPredictions(selectedSymbol),
    enabled: selectedSymbol.length > 0,
  });

  const runPipelineMutation = useMutation({
    mutationFn: api.runTask,
    onSuccess: async (payload) => {
      if (payload.status === "busy") {
        messageApi.warning(`${payload.requested_task ?? "pipeline"} 正在运行，请稍后刷新。`);
        return;
      }
      messageApi.success(`${payload.requested_task ?? "pipeline"} 已完成，本地研究产物已刷新。`);
      await queryClient.invalidateQueries();
    },
    onError: (error) => {
      messageApi.error(`pipeline 执行失败：${error.message}`);
    },
  });

  const status = statusQuery.data;
  const quality = qualityQuery.data;
  const predictions = useMemo(() => predictionsQuery.data?.predictions ?? [], [predictionsQuery.data]);
  const predictionRows = useMemo(
    () => predictionsListQuery.data?.predictions ?? predictions,
    [predictions, predictionsListQuery.data],
  );
  const modelVersionOptions = useMemo(() => {
    const versions = [
      ...(predictionsListQuery.data?.model_versions ?? []),
      ...(modelsQuery.data?.models.map((model) => model.model_version) ?? []),
      latestModelQuery.data?.model_version,
      ...predictionRows.map((row) => row.model_version),
    ];
    return Array.from(new Set(versions.filter((version): version is string => Boolean(version))));
  }, [latestModelQuery.data, modelsQuery.data, predictionRows, predictionsListQuery.data]);
  const predictionDateOptions = useMemo(() => {
    const dates = [
      ...(predictionsListQuery.data?.available_dates ?? []),
      ...predictionRows.map((row) => row.date),
    ];
    return Array.from(new Set(dates.filter(Boolean)));
  }, [predictionRows, predictionsListQuery.data]);
  const stockSymbols = useMemo(() => {
    const listedSymbols = stocksQuery.data?.stocks.map((row) => row.symbol) ?? [];
    // 以股票列表 API 为主，预测和状态只作为旧产物缺字段时的兼容兜底。
    const symbols = [
      ...listedSymbols,
      ...predictions.map((row) => row.symbol),
      ...(status?.predictions.top.map((row) => row.symbol) ?? []),
      selectedSymbol,
    ];
    return Array.from(new Set(symbols.filter(Boolean)));
  }, [predictions, selectedSymbol, status, stocksQuery.data]);
  const backtest = backtestQuery.data;
  const pipeline = pipelineQuery.data;
  const report = reportQuery.data;
  const isLoading =
    statusQuery.isLoading ||
    acceptanceQuery.isLoading ||
    artifactsQuery.isLoading ||
    qualityQuery.isLoading ||
    tasksQuery.isLoading ||
    taskDetailQuery.isLoading ||
    dataStatusQuery.isLoading ||
    duckdbStorageQuery.isLoading ||
    featuresQuery.isLoading ||
    labelsQuery.isLoading ||
    predictionsQuery.isLoading ||
    latestModelQuery.isLoading ||
    modelsQuery.isLoading ||
    modelDetailQuery.isLoading ||
    backtestsQuery.isLoading ||
    backtestDetailQuery.isLoading ||
    backtestQuery.isLoading ||
    predictionsListQuery.isLoading ||
    reportQuery.isLoading ||
    reportsQuery.isLoading ||
    reportDetailQuery.isLoading ||
    stocksQuery.isLoading ||
    settingsQuery.isLoading;
  const isStockLoading =
    stockSummaryQuery.isLoading ||
    stockPricesQuery.isLoading ||
    stockFeaturesQuery.isLoading ||
    stockPredictionsQuery.isLoading;

  const hasError =
    statusQuery.isError ||
    acceptanceQuery.isError ||
    artifactsQuery.isError ||
    qualityQuery.isError ||
    tasksQuery.isError ||
    taskDetailQuery.isError ||
    dataStatusQuery.isError ||
    duckdbStorageQuery.isError ||
    featuresQuery.isError ||
    labelsQuery.isError ||
    predictionsQuery.isError ||
    latestModelQuery.isError ||
    modelsQuery.isError ||
    modelDetailQuery.isError ||
    backtestsQuery.isError ||
    backtestDetailQuery.isError ||
    backtestQuery.isError ||
    predictionsListQuery.isError ||
    reportQuery.isError ||
    reportsQuery.isError ||
    reportDetailQuery.isError ||
    stocksQuery.isError ||
    settingsQuery.isError;

  const pageContent = {
    dashboard: (
      <DashboardPage
        status={status}
        acceptance={acceptanceQuery.data}
        dataStatus={dataStatusQuery.data}
        model={latestModelQuery.data}
        models={modelsQuery.data?.models ?? []}
        quality={quality}
        predictions={predictions}
        backtest={backtest}
        pipeline={pipeline}
        report={report}
      />
    ),
    acceptance: (
      <AcceptancePage
        acceptance={acceptanceQuery.data}
        artifactStatus={status?.artifact_status}
        pipeline={pipeline}
        isRunning={runPipelineMutation.isPending}
        onRunPipeline={() => runPipelineMutation.mutate("pipeline")}
      />
    ),
    data: (
      <DataPage
        dataStatus={dataStatusQuery.data}
        duckdbStorage={duckdbStorageQuery.data}
        quality={qualityQuery.data}
        features={featuresQuery.data}
        labels={labelsQuery.data}
      />
    ),
    tasks: (
      <TasksPage
        tasks={tasksQuery.data?.tasks ?? []}
        taskDetail={taskDetailQuery.data}
        isRunning={runPipelineMutation.isPending}
        onRunTask={(task) => runPipelineMutation.mutate(task)}
      />
    ),
    models: (
      <ModelsPage
        models={modelsQuery.data?.models ?? []}
        model={modelDetailQuery.data ?? latestModelQuery.data}
        selectedModelVersion={selectedModelVersion}
        onSelectModel={setSelectedModelVersion}
      />
    ),
    predictions: (
      <PredictionsPage
        predictions={predictionRows}
        filters={predictionFilters}
        appliedFilters={predictionsListQuery.data?.filters}
        dateOptions={predictionDateOptions}
        modelOptions={modelVersionOptions}
        onFiltersChange={setPredictionFilters}
      />
    ),
    backtests: (
      <BacktestsPage
        backtests={backtestsQuery.data?.backtests ?? []}
        backtest={backtestDetailQuery.data ?? backtest}
        selectedBacktestId={selectedBacktestId}
        onSelectBacktest={setSelectedBacktestId}
      />
    ),
    stocks: (
      <StocksPage
        symbol={selectedSymbol}
        symbols={stockSymbols}
        stockSummaries={stocksQuery.data?.stocks ?? []}
        onSymbolChange={setSelectedSymbol}
        summary={stockSummaryQuery.data}
        prices={stockPricesQuery.data}
        features={stockFeaturesQuery.data?.features ?? []}
        stockPredictions={stockPredictionsQuery.data?.predictions ?? []}
        isLoading={isStockLoading}
      />
    ),
    reports: (
      <ReportsPage
        reports={reportsQuery.data?.reports ?? []}
        report={reportDetailQuery.data}
        selectedReportId={selectedReportId}
        onSelectReport={setSelectedReportId}
        status={status}
        qualityIssues={quality?.issues ?? []}
      />
    ),
    settings: <SettingsPage settings={settingsQuery.data} artifactStatus={artifactsQuery.data} />,
  } satisfies Record<PageKey, ReactNode>;

  return (
    <Layout className="app-shell">
      {contextHolder}
      <Sider width={220} theme="light" className="sidebar">
        <div className="brand">
          <ExperimentOutlined />
          <span>Swell Quant</span>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[activePage]}
          onClick={(item) => setActivePage(item.key as PageKey)}
          items={[
            { key: "dashboard", icon: <BarChartOutlined />, label: "工作台" },
            { key: "acceptance", icon: <CheckCircleOutlined />, label: "验收" },
            { key: "data", icon: <DatabaseOutlined />, label: "数据" },
            { key: "tasks", icon: <SyncOutlined />, label: "任务" },
            { key: "models", icon: <ExperimentOutlined />, label: "模型" },
            { key: "predictions", icon: <LineChartOutlined />, label: "预测" },
            { key: "backtests", icon: <DatabaseOutlined />, label: "回测" },
            { key: "stocks", icon: <StockOutlined />, label: "单股" },
            { key: "reports", icon: <FileTextOutlined />, label: "报告" },
            { key: "settings", icon: <SettingOutlined />, label: "设置" },
          ]}
        />
      </Sider>
      <Layout>
        <Header className="topbar">
          <Space size={16} wrap>
            <Tag color="blue">A 股日频研究</Tag>
            <Text strong>仅用于研究，不构成投资建议</Text>
            <Text type="secondary">模型：{status?.model.model_version ?? "-"}</Text>
            <Text type="secondary">最近生成：{status?.pipeline.ended_at ?? "-"}</Text>
          </Space>
          <Button
            icon={<ReloadOutlined />}
            loading={runPipelineMutation.isPending}
            onClick={() => runPipelineMutation.mutate("pipeline")}
          >
            运行 pipeline
          </Button>
        </Header>
        <Content className="content">
          {hasError ? (
            <Alert
              className="page-alert"
              type="warning"
              showIcon
              message="部分本地产物暂不可读"
              description="请先启动后端 API，并运行 python3 scripts/run_pipeline.py 或点击运行 pipeline。"
            />
          ) : null}

          <Spin spinning={isLoading}>{pageContent[activePage]}</Spin>
        </Content>
      </Layout>
    </Layout>
  );
}

export default App;
