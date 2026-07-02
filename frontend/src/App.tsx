import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Layout,
  Menu,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import {
  BarChartOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { api } from "./api/client";
import type { BacktestPoint, Prediction } from "./types/api";

const { Header, Sider, Content } = Layout;
const { Title, Text, Paragraph } = Typography;

function formatPercent(value?: number): string {
  if (value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: number | null): string {
  return value === null ? "-" : value.toFixed(4);
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

function App() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();

  const statusQuery = useQuery({ queryKey: ["status"], queryFn: api.getStatus });
  const pipelineQuery = useQuery({ queryKey: ["pipeline"], queryFn: api.getPipeline });
  const qualityQuery = useQuery({ queryKey: ["data-quality"], queryFn: api.getDataQuality });
  const predictionsQuery = useQuery({
    queryKey: ["predictions", "latest"],
    queryFn: api.getLatestPredictions,
  });
  const backtestQuery = useQuery({
    queryKey: ["backtest", "latest"],
    queryFn: api.getLatestBacktest,
  });
  const reportQuery = useQuery({ queryKey: ["report"], queryFn: api.getReport });

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
  const predictions = predictionsQuery.data?.predictions ?? [];
  const backtest = backtestQuery.data;
  const pipeline = pipelineQuery.data;
  const isLoading =
    statusQuery.isLoading ||
    qualityQuery.isLoading ||
    predictionsQuery.isLoading ||
    backtestQuery.isLoading ||
    reportQuery.isLoading;

  const hasError =
    statusQuery.isError ||
    qualityQuery.isError ||
    predictionsQuery.isError ||
    backtestQuery.isError ||
    reportQuery.isError;

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
          selectedKeys={["dashboard"]}
          items={[
            { key: "dashboard", icon: <BarChartOutlined />, label: "工作台" },
            { key: "tasks", icon: <SyncOutlined />, label: "任务" },
            { key: "predictions", icon: <LineChartOutlined />, label: "预测" },
            { key: "reports", icon: <FileTextOutlined />, label: "报告" },
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
          <div className="page-title">
            <div>
              <Title level={2}>研究工作台</Title>
              <Text type="secondary">查看离线研究链路、预测排名、回测结果和报告状态。</Text>
            </div>
            <Tag color={pipeline?.status === "success" ? "green" : "orange"}>
              pipeline: {pipeline?.status ?? "unknown"}
            </Tag>
          </div>

          {hasError ? (
            <Alert
              type="warning"
              showIcon
              message="部分本地产物暂不可读"
              description="请先启动后端 API，并运行 python3 scripts/run_pipeline.py 或点击运行 pipeline。"
            />
          ) : null}

          <Spin spinning={isLoading}>
            <Row gutter={[16, 16]} className="metric-row">
              <Col xs={24} md={12} xl={6}>
                <Card>
                  <Statistic
                    title="数据行数"
                    value={quality?.row_count ?? 0}
                    prefix={<DatabaseOutlined />}
                  />
                  <Text type="secondary">
                    {quality?.symbol_count ?? 0} 只标的，{quality?.issue_count ?? 0} 个质量问题
                  </Text>
                </Card>
              </Col>
              <Col xs={24} md={12} xl={6}>
                <Card>
                  <Statistic title="最新预测" value={predictions.length} suffix="条" />
                  <Text type="secondary">模型：{predictions[0]?.model_version ?? "-"}</Text>
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
                  <Text type="secondary">回测：{backtest?.backtest_id ?? "-"}</Text>
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
                      columns={[
                        { title: "排名", dataIndex: "rank", width: 76, sorter: (a, b) => a.rank - b.rank },
                        { title: "代码", dataIndex: "symbol", width: 120 },
                        { title: "日期", dataIndex: "date", width: 120 },
                        {
                          title: "预测分数",
                          dataIndex: "score",
                          align: "right",
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
                      ]}
                    />
                  ) : (
                    <Empty description="暂无预测结果" />
                  )}
                </Card>
              </Col>
              <Col xs={24} xl={10}>
                <Card title="回测净值曲线">
                  {backtest?.equity_curve?.length ? (
                    <ReactECharts
                      className="equity-chart"
                      option={buildEquityOption(backtest.equity_curve)}
                    />
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
                    <Tag color={quality?.passed ? "green" : "red"}>
                      {quality?.passed ? "质量检查通过" : "存在质量问题"}
                    </Tag>
                    <Text>
                      覆盖区间：{quality?.start_date ?? "-"} 至 {quality?.end_date ?? "-"}
                    </Text>
                    <Text type="secondary">
                      当前样例链路使用可复现本地数据，后续会替换为真实 A 股日频数据源。
                    </Text>
                  </Space>
                </Card>
              </Col>
              <Col xs={24} xl={12}>
                <Card title="研究报告预览">
                  {reportQuery.data ? (
                    <Paragraph className="report-preview">
                      {reportQuery.data.split("\n").slice(0, 10).join("\n")}
                    </Paragraph>
                  ) : (
                    <Empty description="暂无研究报告" />
                  )}
                </Card>
              </Col>
            </Row>
          </Spin>
        </Content>
      </Layout>
    </Layout>
  );
}

export default App;
