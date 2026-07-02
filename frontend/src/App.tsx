import { useMemo, useState, type ReactNode } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Empty,
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
import { api } from "./api/client";
import type {
  BacktestPoint,
  BacktestSummary,
  DataQualityIssue,
  DataStatus,
  LatestBacktest,
  LatestModel,
  LocalSettings,
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
  | "tasks"
  | "predictions"
  | "backtests"
  | "stocks"
  | "reports"
  | "settings";

function formatPercent(value?: number): string {
  if (value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : value.toFixed(4);
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
  dataStatus,
  model,
  quality,
  predictions,
  backtest,
  pipeline,
  report,
}: {
  status?: ResearchStatus;
  dataStatus?: DataStatus;
  model?: LatestModel;
  quality?: ResearchStatus["data_quality"];
  predictions: Prediction[];
  backtest?: LatestBacktest;
  pipeline?: PipelineRun;
  report?: string;
}) {
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

function TasksPage({
  tasks,
  taskDetail,
  onRunPipeline,
  isRunning,
}: {
  tasks: TaskSummary[];
  taskDetail?: TaskDetail;
  onRunPipeline: () => void;
  isRunning: boolean;
}) {
  const steps = taskDetail?.steps ?? [];
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
          <Button icon={<ReloadOutlined />} loading={isRunning} onClick={onRunPipeline}>
            运行 pipeline
          </Button>
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

function PredictionsPage({ predictions }: { predictions: Prediction[] }) {
  return (
    <>
      <PageTitle
        title="预测"
        description="查看最近交易日 Top N 排名、预测分数和基础因子。预测分数仅用于研究，不构成投资建议。"
      />
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
      </Row>
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
              <Descriptions.Item label="开始日期">{backtest?.start_date ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="结束日期">{backtest?.end_date ?? "-"}</Descriptions.Item>
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
  onSymbolChange,
  summary,
  prices,
  features,
  stockPredictions,
  isLoading,
}: {
  symbol: string;
  symbols: string[];
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

function SettingsPage({ settings }: { settings?: LocalSettings }) {
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
              dataSource={settings?.artifacts ?? []}
              pagination={false}
              columns={[
                { title: "产物", dataIndex: "name", width: 180 },
                { title: "路径", dataIndex: "path" },
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

  const statusQuery = useQuery({ queryKey: ["status"], queryFn: api.getStatus });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const pipelineQuery = useQuery({ queryKey: ["pipeline"], queryFn: api.getPipeline });
  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: api.getTasks });
  const taskDetailQuery = useQuery({
    queryKey: ["tasks", "pipeline-latest"],
    queryFn: () => api.getTaskDetail("pipeline-latest"),
  });
  const dataStatusQuery = useQuery({ queryKey: ["data-status"], queryFn: api.getDataStatus });
  const qualityQuery = useQuery({ queryKey: ["data-quality"], queryFn: api.getDataQuality });
  const latestModelQuery = useQuery({ queryKey: ["model", "latest"], queryFn: api.getLatestModel });
  const predictionsQuery = useQuery({
    queryKey: ["predictions", "latest"],
    queryFn: api.getLatestPredictions,
  });
  const predictionsListQuery = useQuery({
    queryKey: ["predictions", "list", 10],
    queryFn: () => api.getPredictions(10),
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
    mutationFn: api.runPipeline,
    onSuccess: async (payload) => {
      if (payload.status === "busy") {
        messageApi.warning("pipeline 正在运行，请稍后刷新。");
        return;
      }
      messageApi.success("pipeline 已完成，本地研究产物已刷新。");
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
    qualityQuery.isLoading ||
    tasksQuery.isLoading ||
    taskDetailQuery.isLoading ||
    dataStatusQuery.isLoading ||
    predictionsQuery.isLoading ||
    latestModelQuery.isLoading ||
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
    qualityQuery.isError ||
    tasksQuery.isError ||
    taskDetailQuery.isError ||
    dataStatusQuery.isError ||
    predictionsQuery.isError ||
    latestModelQuery.isError ||
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
        dataStatus={dataStatusQuery.data}
        model={latestModelQuery.data}
        quality={quality}
        predictions={predictions}
        backtest={backtest}
        pipeline={pipeline}
        report={report}
      />
    ),
    tasks: (
      <TasksPage
        tasks={tasksQuery.data?.tasks ?? []}
        taskDetail={taskDetailQuery.data}
        isRunning={runPipelineMutation.isPending}
        onRunPipeline={() => runPipelineMutation.mutate()}
      />
    ),
    predictions: <PredictionsPage predictions={predictionRows} />,
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
    settings: <SettingsPage settings={settingsQuery.data} />,
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
            { key: "tasks", icon: <SyncOutlined />, label: "任务" },
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
            onClick={() => runPipelineMutation.mutate()}
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
