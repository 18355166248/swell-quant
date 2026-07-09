import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Empty,
  InputNumber,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Timeline,
  Typography,
} from "antd";
import { Fragment, useMemo, useState } from "react";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import ReactECharts from "echarts-for-react";
import type { TaskTrigger } from "../api/client";
import { PageTitle } from "../components/PageTitle";
import {
  buildDrawdownOption,
  buildEquityOption,
  buildFeatureImportanceOption,
  buildRelativeReturnOption,
  buildScoreOption,
  buildStockFactorOption,
  buildStockPriceOption,
} from "../utils/charts";
import {
  formatNumber,
  formatPercent,
  preflightStatusColor,
  rejectedTradeReasonLabel,
  statusColor,
  storageStatusColor,
} from "../utils/display";
import {
  buildArtifactColumns,
  buildCheckColumns,
  buildModelSummaryColumns,
  buildPredictionColumns,
  buildTaskSummaryColumns,
} from "../utils/tableColumns";
import type {
  AcceptanceStatus,
  AkshareTrialRun,
  AkshareUniverseStatus,
  ArtifactStatus,
  BacktestPoint,
  BacktestSummary,
  DailyBrief,
  DataTrialRun,
  DataTrialStep,
  DataFreshness,
  DataQuality,
  DataQualityIssue,
  DataStatus,
  DuckDBStorageStatus,
  FeatureSummary,
  FundCandidate,
  FundNav,
  FundNavPoint,
  FundSourceSummary,
  FundSummary,
  FundTrialRun,
  LabelSummary,
  LatestBacktest,
  LatestModel,
  LatestPredictions,
  LocalSettings,
  ModelSummary,
  PipelineRun,
  ProjectProgress,
  ProjectProgressStage,
  Prediction,
  ResearchCandidate,
  RejectedTrade,
  ReportDetail,
  ReportSummary,
  ResearchStatus,
  StockFeature,
  StockPrediction,
  StockPrices,
  StockSummary,
  TaskDetail,
  TaskSummary,
  TrainingSamplesSummary,
} from "../types/api";

const { Title, Text, Paragraph } = Typography;

export interface PredictionFilters {
  date: string;
  modelVersion: string;
  topN: number;
}

interface ResearchRoadmapItem {
  key: string;
  title: string;
  priority: "P0" | "P1" | "P2";
  status: "done" | "next" | "planned";
  evidence: string;
  outcome: string;
}

const ROADMAP_PRIORITY_COLOR: Record<ResearchRoadmapItem["priority"], string> = {
  P0: "red",
  P1: "blue",
  P2: "default",
};

const ROADMAP_STATUS_META: Record<
  ResearchRoadmapItem["status"],
  { color: string; label: string }
> = {
  done: { color: "green", label: "已完成" },
  next: { color: "orange", label: "下一步" },
  planned: { color: "default", label: "规划中" },
};

// 评估指标的中文标签；未列出的指标 key 原样展示。
const METRIC_LABELS: Record<string, string> = {
  positive_rate: "跑赢占比",
  evaluation_status: "评估状态",
  test_prediction_dates: "测试预测日数",
  top1_outperform_rate: "Top1 跑赢率",
  top3_outperform_rate: "Top3 跑赢率",
  labeled_row_count: "标注样本数",
  training_row_count: "训练样本数",
  validation_row_count: "验证样本数",
  test_row_count: "测试样本数",
  evaluation_date_count: "评估日数",
  ic_date_count: "IC 有效日数",
  ic_mean: "IC 均值",
  rank_ic_mean: "RankIC 均值",
  ic_ir: "IC 信息比 (IC_IR)",
  rank_ic_positive_rate: "RankIC 为正占比",
  long_short_spread: "多空分层超额",
  walk_forward_status: "滚动样本外状态",
  walk_forward_fold_count: "滚动折数",
  walk_forward_test_date_count: "滚动样本外测试日数",
  walk_forward_top1_outperform_rate: "滚动 Top1 跑赢率",
  walk_forward_top3_outperform_rate: "滚动 Top3 跑赢率",
  walk_forward_ic_mean: "滚动 IC 均值",
  walk_forward_rank_ic_mean: "滚动 RankIC 均值",
  walk_forward_ic_ir: "滚动 IC 信息比",
  walk_forward_rank_ic_positive_rate: "滚动 RankIC 为正占比",
  walk_forward_long_short_spread: "滚动多空分层超额",
};

function buildResearchRoadmap(progress?: ProjectProgress): ResearchRoadmapItem[] {
  const akshareTrialVerified = progress?.akshare_trial?.real_data_verified === true;
  const allStagesComplete = progress?.status === "complete";
  const hasDryRunOnly = progress?.akshare_trial?.trial_kind === "dry_run" && !akshareTrialVerified;

  // 路线图只汇总当前研发动作，不把未验证能力标记为可用研究结论。
  return [
    {
      key: "real_stock_trial",
      title: "A 股真实数据小规模试跑",
      priority: "P0",
      status: akshareTrialVerified ? "done" : hasDryRunOnly ? "next" : "planned",
      evidence: akshareTrialVerified
        ? "已有真实数据通过记录"
        : hasDryRunOnly
          ? "已完成 dry-run，下一步跑真实 AKShare 试采集"
          : "先完成试跑预演，再进入真实数据验证",
      outcome: "把候选日期从样例链路推进到真实公开行情链路",
    },
    {
      key: "fund_real_data_validation",
      title: "基金真实净值与候选验证",
      priority: "P0",
      status: "next",
      evidence: "任务中心已有基金试跑入口，需持续复核真实通过产物",
      outcome: "让基金页从样例比较升级为真实数据研究比较",
    },
    {
      key: "model_upgrade",
      title: "模型与样本外评估升级",
      priority: "P1",
      status: allStagesComplete ? "next" : "planned",
      evidence: allStagesComplete ? "离线闭环已完成，可进入模型增强" : "等待基础链路和验收稳定",
      outcome: "引入更强模型和更严格样本外评估，降低样例规则模型局限",
    },
    {
      key: "report_governance",
      title: "报告与研究动作治理",
      priority: "P1",
      status: "planned",
      evidence: "已有研究动作分层和每日简报，后续补审计历史与对比视图",
      outcome: "让每次候选变化都有来源、门禁、阻塞项和复核记录",
    },
    {
      key: "data_observability",
      title: "数据源可观测性与告警",
      priority: "P2",
      status: "planned",
      evidence: "已有新鲜度、质量、试跑摘要，缺少持续监控提示",
      outcome: "及时发现行情、基金净值、报告产物过期或缺失",
    },
  ];
}

export function DashboardPage({
  status,
  acceptance,
  dataStatus,
  model,
  models,
  quality,
  predictions,
  backtest,
  pipeline,
  progress,
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
  progress?: ProjectProgress;
  report?: string;
}) {
  const acceptanceStatus = acceptance ?? status?.acceptance;
  const acceptanceChecks = acceptanceStatus?.checks ?? [];
  const roadmapItems = buildResearchRoadmap(progress);
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
            <Statistic
              title="阶段完成度"
              value={progress ? `${progress.completed_stage_count}/${progress.stage_count}` : "-"}
            />
            <Text type="secondary">当前：{progress?.current_stage.name ?? "-"}</Text>
          </Card>
        </Col>
      </Row>

      <Card
        title="阶段进度"
        extra={
          <Tag color={progress?.status === "complete" ? "green" : "blue"}>
            {progress?.status ?? "unknown"}
          </Tag>
        }
      >
        {progress?.stages.length ? (
          <Space direction="vertical" size={12} className="full-width">
            {progress.next_actions.length > 0 ? (
              <Alert
                type={progress.status === "complete" ? "success" : "info"}
                showIcon
                message="下一步建议"
                description={progress.next_actions.join("；")}
              />
            ) : null}
            <Table<ProjectProgressStage>
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={progress.stages}
              columns={[
                { title: "阶段", dataIndex: "name", width: 220 },
                { title: "目标", dataIndex: "goal" },
                {
                  title: "状态",
                  dataIndex: "status",
                  width: 110,
                  render: (value: ProjectProgressStage["status"]) => (
                    <Tag color={value === "complete" ? "green" : value === "partial" ? "orange" : "default"}>
                      {value}
                    </Tag>
                  ),
                },
                {
                  title: "证据",
                  width: 120,
                  render: (_, row) => `${row.completed_count}/${row.required_count}`,
                },
              ]}
            />
          </Space>
        ) : (
          <Empty description="暂无阶段进度" />
        )}
      </Card>

      <Card title="后续功能路线图">
        <Paragraph type="secondary">
          只展示研究系统建设动作，不输出买入、卖出、仓位、目标价或收益承诺。
        </Paragraph>
        <Row gutter={[12, 12]}>
          {roadmapItems.map((item) => (
            <Col xs={24} md={12} xl={8} key={item.key}>
              <div className="roadmap-item">
                <Space direction="vertical" size={8} className="full-width">
                  <Space wrap>
                    <Tag color={ROADMAP_PRIORITY_COLOR[item.priority]}>{item.priority}</Tag>
                    <Tag color={ROADMAP_STATUS_META[item.status].color}>
                      {ROADMAP_STATUS_META[item.status].label}
                    </Tag>
                  </Space>
                  <Text strong>{item.title}</Text>
                  <Text type="secondary">{item.evidence}</Text>
                  <Text>{item.outcome}</Text>
                </Space>
              </div>
            </Col>
          ))}
        </Row>
      </Card>

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
            columns={buildCheckColumns<ResearchStatus["acceptance"]["checks"][number]>()}
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
                columns={buildPredictionColumns()}
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
                columns={buildModelSummaryColumns({ variant: "compact" })}
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

export function AcceptancePage({
  acceptance,
  artifactStatus,
  trainingSamples,
  pipeline,
  isRunning,
  onRunPipeline,
}: {
  acceptance?: AcceptanceStatus;
  artifactStatus?: ArtifactStatus;
  trainingSamples?: ResearchStatus["training_samples"];
  pipeline?: PipelineRun;
  isRunning: boolean;
  onRunPipeline: () => void;
}) {
  const checks = acceptance?.checks ?? [];
  const artifacts = artifactStatus?.artifacts ?? [];
  const passedCount = checks.filter((check) => check.status === "passed").length;
  const splitCounts = trainingSamples?.split_counts ?? {};
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
        <Col xs={24} md={12} xl={6}>
          <Card>
            <Statistic
              title="验收状态"
              value={acceptance?.status ?? "unknown"}
              prefix={acceptance?.passed ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card>
            <Statistic title="通过检查" value={passedCount} suffix={`/ ${acceptance?.check_count ?? 0}`} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card>
            <Statistic title="失败检查" value={acceptance?.failed_count ?? 0} />
            <Text type="secondary">pipeline: {pipeline?.status ?? "unknown"}</Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card>
            <Statistic title="训练样本" value={trainingSamples?.row_count ?? 0} suffix="条" />
            <Space size={4} wrap>
              <Tag color={trainingSamples?.status === "ready" ? "green" : "red"}>
                {trainingSamples?.status ?? "missing"}
              </Tag>
              <Text type="secondary">
                train {splitCounts.train ?? 0} / validation {splitCounts.validation ?? 0} / test{" "}
                {splitCounts.test ?? 0}
              </Text>
            </Space>
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
            columns={buildCheckColumns<AcceptanceStatus["checks"][number]>({ showKey: true })}
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
            columns={buildArtifactColumns<ArtifactStatus["artifacts"][number]>()}
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

export function TasksPage({
  tasks,
  taskDetail,
  akshareTrial,
  fundTrial,
  onRunTask,
  isRunning,
}: {
  tasks: TaskSummary[];
  taskDetail?: TaskDetail;
  akshareTrial?: AkshareTrialRun;
  fundTrial?: FundTrialRun;
  onRunTask: (task: TaskTrigger) => void;
  isRunning: boolean;
}) {
  const steps = taskDetail?.steps ?? [];
  const pipelineTaskTriggers: Array<{ key: TaskTrigger; label: string }> = [
    { key: "pipeline", label: "完整 pipeline" },
    { key: "data_update", label: "更新数据" },
    { key: "model_train", label: "训练模型" },
    { key: "prediction_run", label: "生成预测" },
    { key: "backtest_run", label: "运行回测" },
    { key: "report_generate", label: "生成报告" },
  ];
  const trialTaskTriggers: Array<{ key: TaskTrigger; label: string; danger?: boolean }> = [
    { key: "akshare_trial_dry_run", label: "股票试跑预演" },
    { key: "akshare_trial", label: "股票真实试跑", danger: true },
    { key: "fund_trial_dry_run", label: "基金试跑预演" },
    { key: "fund_trial", label: "基金真实试跑", danger: true },
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
          <Space direction="vertical" size={6} align="end">
            <Space wrap>
              <Text type="secondary">研究链路</Text>
              {pipelineTaskTriggers.map((trigger) => (
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
            <Space wrap>
              <Text type="secondary">真实数据试跑</Text>
              {trialTaskTriggers.map((trigger) => (
                <Button
                  key={trigger.key}
                  danger={trigger.danger}
                  icon={<ReloadOutlined />}
                  loading={isRunning}
                  onClick={() => onRunTask(trigger.key)}
                >
                  {trigger.label}
                </Button>
              ))}
            </Space>
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
              columns={buildTaskSummaryColumns()}
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
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <TrialRunCard
            title="最近股票真实试跑"
            trial={akshareTrial}
            runCommand="make akshare-trial"
            dryRunCommand="make akshare-trial-dry-run"
            statusCommand="make akshare-trial-status"
            emptyDescription="暂无股票真实试跑记录"
            envItems={[
              ["股票池", akshareTrial?.env?.AKSHARE_UNIVERSE_MODE],
              ["试跑上限", akshareTrial?.env?.AKSHARE_MAX_SYMBOLS],
              [
                "日期区间",
                `${akshareTrial?.env?.AKSHARE_START_DATE ?? "-"} 至 ${akshareTrial?.env?.AKSHARE_END_DATE ?? "-"}`,
              ],
            ]}
          />
        </Col>
        <Col xs={24} xl={12}>
          <TrialRunCard
            title="最近基金真实试跑"
            trial={fundTrial}
            runCommand="make fund-trial"
            dryRunCommand="make fund-trial-dry-run"
            statusCommand="make fund-trial-status"
            emptyDescription="暂无基金真实试跑记录"
            envItems={[
              ["基金代码", fundTrial?.env?.FUND_SYMBOLS],
              [
                "日期区间",
                `${fundTrial?.env?.FUND_START_DATE ?? "-"} 至 ${fundTrial?.env?.FUND_END_DATE ?? "-"}`,
              ],
            ]}
          />
        </Col>
      </Row>
    </>
  );
}

function TrialRunCard({
  title,
  trial,
  runCommand,
  dryRunCommand,
  statusCommand,
  emptyDescription,
  envItems,
}: {
  title: string;
  trial?: DataTrialRun;
  runCommand: string;
  dryRunCommand: string;
  statusCommand: string;
  emptyDescription: string;
  envItems: Array<[string, string | number | undefined]>;
}) {
  const trialSteps = trial?.steps ?? [];
  return (
    <Card
      title={title}
      extra={<Tag color={preflightStatusColor(trial?.status)}>{trial?.status ?? "missing"}</Tag>}
    >
      <Descriptions column={1} size="small" className="trial-command-summary">
        <Descriptions.Item label="生成命令">
          <Text code>{runCommand}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="预演命令">
          <Text code>{dryRunCommand}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="状态命令">
          <Text code>{statusCommand}</Text>
        </Descriptions.Item>
      </Descriptions>
      {trial?.status && trial.status !== "missing" ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="通过">
              {trial.passed === undefined ? "-" : String(trial.passed)}
            </Descriptions.Item>
            <Descriptions.Item label="真实数据验证">
              {trial.real_data_verified === undefined
                ? "-"
                : trial.real_data_verified
                  ? "已验证"
                  : "未验证，仅预演"}
            </Descriptions.Item>
            <Descriptions.Item label="最近真实通过">
              {trial.last_passed?.ended_at ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="试跑类型">{trial.trial_kind ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="耗时">
              {trial.duration_seconds === undefined ? "-" : `${trial.duration_seconds.toFixed(4)}s`}
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">{trial.started_at ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="结束时间">{trial.ended_at ?? "-"}</Descriptions.Item>
            {envItems.map(([label, value]) => (
              <Descriptions.Item key={label} label={label}>
                {value ?? "-"}
              </Descriptions.Item>
            ))}
            <Descriptions.Item label="产物路径">
              {trial.artifact_path ?? trial.path ?? "-"}
            </Descriptions.Item>
          </Descriptions>
          {trialSteps.length > 0 ? (
            <Table<DataTrialStep>
              rowKey={(row) => row.name}
              size="small"
              pagination={false}
              dataSource={trialSteps}
              columns={[
                { title: "步骤", dataIndex: "name" },
                {
                  title: "状态",
                  dataIndex: "status",
                  width: 110,
                  render: (status: string) => <Tag color={preflightStatusColor(status)}>{status}</Tag>,
                },
                {
                  title: "返回码",
                  dataIndex: "returncode",
                  width: 90,
                  render: (value) => value ?? "-",
                },
                {
                  title: "成功/失败",
                  width: 110,
                  render: (_, row) =>
                    row.succeeded_count === undefined && row.failed_count === undefined
                      ? "-"
                      : `${row.succeeded_count ?? 0}/${row.failed_count ?? 0}`,
                },
                {
                  title: "错误",
                  dataIndex: "error",
                  render: (value) => value ?? "-",
                },
              ]}
            />
          ) : null}
        </Space>
      ) : (
        <Empty description={emptyDescription} />
      )}
    </Card>
  );
}

export function DataPage({
  dataStatus,
  duckdbStorage,
  artifacts,
  akshareTrial,
  fundTrial,
  quality,
  features,
  labels,
}: {
  dataStatus?: DataStatus;
  duckdbStorage?: DuckDBStorageStatus;
  artifacts?: ArtifactStatus;
  akshareTrial?: DataTrialRun;
  fundTrial?: DataTrialRun;
  quality?: DataQuality;
  features?: FeatureSummary;
  labels?: LabelSummary;
}) {
  const issues = quality?.issues ?? [];
  const failedSymbols = dataStatus?.failed_symbols ?? [];
  const dataSourceWarnings = dataStatus?.data_source_warnings ?? [];
  const dataSourceFailures = dataStatus?.data_source_failures ?? [];
  const featureRows = features?.feature_names.map((featureName) => ({
    featureName,
    nonNullCount: features.non_null_counts[featureName] ?? 0,
    coverage: features.row_count > 0 ? (features.non_null_counts[featureName] ?? 0) / features.row_count : 0,
  })) ?? [];
  const labelRate = labels?.labeled_row_count && labels.labeled_row_count > 0
    ? labels.positive_count / labels.labeled_row_count
    : 0;
  const healthRows = [
    {
      key: "stock_source",
      item: "A 股行情数据",
      status: dataStatus?.data_source_status ?? "missing",
      detail: dataStatus
        ? `成功 ${dataStatus.succeeded_symbol_count}/${dataStatus.selected_symbol_count}，${dataStatus.freshness?.label ?? "新鲜度待确认"}`
        : "暂无数据源状态",
      action: "make akshare-trial / make data-source",
    },
    {
      key: "freshness",
      item: "数据新鲜度",
      status: dataStatus?.freshness?.status ?? "missing",
      detail: dataStatus?.freshness?.message ?? "暂无最新日期",
      action: "更新数据后复查数据页",
    },
    {
      key: "duckdb",
      item: "DuckDB 镜像",
      status: duckdbStorage?.status ?? "missing",
      detail: duckdbStorage
        ? `表 ${duckdbStorage.tables.length} 个，总行数 ${duckdbStorage.total_rows}`
        : "暂无 DuckDB 状态",
      action: "make storage",
    },
    {
      key: "akshare_trial",
      item: "股票真实试跑",
      status: akshareTrial?.status ?? "missing",
      detail: akshareTrial?.real_data_verified
        ? "已有真实通过记录"
        : `当前 ${akshareTrial?.trial_kind ?? "未试跑"}`,
      action: "make akshare-trial",
    },
    {
      key: "fund_trial",
      item: "基金真实试跑",
      status: fundTrial?.status ?? "missing",
      detail: fundTrial?.real_data_verified
        ? "已有真实通过记录"
        : `当前 ${fundTrial?.trial_kind ?? "未试跑"}`,
      action: "make fund-trial",
    },
    {
      key: "artifacts",
      item: "关键产物",
      status: artifacts?.status ?? "missing",
      detail: artifacts
        ? `缺失 ${artifacts.missing.length} 个，可选缺失 ${artifacts.optional_missing?.length ?? 0} 个`
        : "暂无产物清单",
      action: "make pipeline / make acceptance",
    },
  ];
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
            <Statistic
              title="数据新鲜度"
              value={dataStatus?.freshness?.label ?? "待确认"}
            />
            <Tag color={freshnessColor(dataStatus?.freshness?.status)}>
              {dataStatus?.freshness?.lag_days === null || dataStatus?.freshness?.lag_days === undefined
                ? "-"
                : `${dataStatus.freshness.lag_days} 天前`}
            </Tag>
          </Card>
        </Col>
      </Row>
      <Card title="数据源健康中心">
        <Table
          rowKey="key"
          size="small"
          pagination={false}
          dataSource={healthRows}
          columns={[
            { title: "检查项", dataIndex: "item", width: 150 },
            {
              title: "状态",
              dataIndex: "status",
              width: 130,
              render: (status: string) => <Tag color={healthStatusColor(status)}>{status}</Tag>,
            },
            { title: "说明", dataIndex: "detail" },
            {
              title: "操作入口",
              dataIndex: "action",
              width: 230,
              render: (value: string) => <Text code>{value}</Text>,
            },
          ]}
        />
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="数据口径">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="数据来源">{dataStatus?.data_source ?? "sample"}</Descriptions.Item>
              <Descriptions.Item label="市场">{dataStatus?.market ?? "A_SHARE_DAILY"}</Descriptions.Item>
              <Descriptions.Item label="股票池">{dataStatus?.universe ?? "sample_a_share"}</Descriptions.Item>
              <Descriptions.Item label="股票池名称">{dataStatus?.universe_name ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="配置标的">
                {dataStatus?.symbols?.length ? dataStatus.symbols.join(", ") : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="v1 目标股票池">
                {dataStatus?.target_universe ?? "-"}（约 {dataStatus?.target_universe_size ?? "-"} 只）
              </Descriptions.Item>
              <Descriptions.Item label="基准">
                {dataStatus?.benchmark_name ?? "-"}（{dataStatus?.benchmark ?? "-"}）
              </Descriptions.Item>
              <Descriptions.Item label="基准兜底">{dataStatus?.benchmark_fallback ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="复权口径">{dataStatus?.adjustment ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="更新方式">{dataStatus?.update_mode ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="配置日期">
                {dataStatus?.configured_start_date ?? "-"} 至 {dataStatus?.configured_end_date ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="开始日期">
                {dataStatus?.start_date ?? quality?.start_date ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="结束日期">
                {dataStatus?.end_date ?? quality?.end_date ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="新鲜度">
                {dataStatus?.freshness?.message ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="源更新时间">{dataStatus?.source_updated_at ?? "-"}</Descriptions.Item>
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
          <Card title="采集摘要">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Space wrap>
                <Tag color={preflightStatusColor(dataStatus?.data_source_status)}>
                  采集状态：{dataStatus?.data_source_status ?? "missing"}
                </Tag>
                <Tag color={dataStatus?.data_source_passed ? "green" : "red"}>
                  {dataStatus?.data_source_passed ? "可继续研究" : "需先修复采集"}
                </Tag>
              </Space>
              {dataSourceWarnings.length > 0 ? (
                <Alert
                  type="warning"
                  showIcon
                  message="采集提示"
                  description={dataSourceWarnings.join("；")}
                />
              ) : null}
              {dataSourceFailures.length > 0 ? (
                <Alert
                  type="error"
                  showIcon
                  message="采集阻断"
                  description={dataSourceFailures.join("；")}
                />
              ) : null}
            </Space>
            <Descriptions column={4} size="small">
              <Descriptions.Item label="解析标的">{dataStatus?.resolved_symbol_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="选择标的">{dataStatus?.selected_symbol_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="成功标的">{dataStatus?.succeeded_symbol_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="失败标的">{dataStatus?.failed_symbol_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="采集成功率">
                {dataStatus?.success_rate === undefined ? "-" : formatPercent(dataStatus.success_rate)}
              </Descriptions.Item>
              <Descriptions.Item label="质量等级">
                <Tag color={dataSourceQualityColor(dataStatus?.quality_level)}>
                  {dataStatus?.quality_level ?? "-"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="质量分">
                {dataStatus?.quality_score === undefined ? "-" : formatNumber(dataStatus.quality_score)}
              </Descriptions.Item>
              <Descriptions.Item label="试跑上限">{dataStatus?.max_symbols ?? "未限制"}</Descriptions.Item>
            </Descriptions>
            {failedSymbols.length > 0 ? (
              <Table
                rowKey="symbol"
                size="small"
                dataSource={failedSymbols}
                pagination={{ pageSize: 6, hideOnSinglePage: true }}
                columns={[
                  { title: "标的", dataIndex: "symbol", width: 140 },
                  { title: "失败原因", dataIndex: "reason" },
                ]}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无采集失败标的" />
            )}
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
            { title: "5 日波动", dataIndex: "volatility_5d", align: "right", render: formatNumber },
            { title: "RSI6", dataIndex: "rsi_6", align: "right", render: formatNumber },
            { title: "MACD 柱", dataIndex: "macd_hist", align: "right", render: formatNumber },
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

export function ModelsPage({
  models,
  model,
  trainingSamples,
  selectedModelVersion,
  onSelectModel,
}: {
  models: ModelSummary[];
  model?: LatestModel;
  trainingSamples?: TrainingSamplesSummary;
  selectedModelVersion: string;
  onSelectModel: (modelVersion: string) => void;
}) {
  const featureRows = model?.feature_names.map((featureName, index) => ({
    featureName,
    index: index + 1,
  })) ?? [];
  const metricRows = Object.entries(model?.metrics ?? {}).map(([name, value]) => ({
    name: METRIC_LABELS[name] ?? name,
    value: typeof value === "number" ? formatNumber(value) : (value ?? "-"),
  }));
  const importanceRows = model?.feature_importance ?? [];
  const splitRows = Object.entries(trainingSamples?.split_counts ?? {}).map(([split, count]) => ({
    split,
    count,
    share: trainingSamples?.row_count ? count / trainingSamples.row_count : 0,
  }));
  const missingRows = Object.entries(trainingSamples?.missing_feature_counts ?? {}).map(([featureName, count]) => ({
    featureName,
    count,
    share: trainingSamples?.row_count ? count / trainingSamples.row_count : 0,
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
              columns={buildModelSummaryColumns()}
            />
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card title="模型详情">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="模型版本">{model?.model_version ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="模型类型">{model?.model_type ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="目标模型">{model?.requested_model_type ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="训练后端">{model?.training_backend ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="依赖状态">{model?.dependency_status ?? "-"}</Descriptions.Item>
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
      <Card title="特征重要性">
        {importanceRows.length > 0 ? (
          <>
            <ReactECharts
              className="large-chart"
              option={buildFeatureImportanceOption(importanceRows)}
            />
            <Table
              rowKey="feature_name"
              size="middle"
              dataSource={importanceRows}
              pagination={false}
              columns={[
                { title: "排名", dataIndex: "rank", width: 90, align: "right" },
                { title: "特征名", dataIndex: "feature_name" },
                { title: "重要性", dataIndex: "importance", width: 140, align: "right", render: formatNumber },
                {
                  title: "原始值",
                  dataIndex: "raw_importance",
                  width: 140,
                  align: "right",
                  render: formatNumber,
                },
                { title: "类型", dataIndex: "importance_type", width: 160 },
              ]}
            />
          </>
        ) : (
          <Empty description="暂无特征重要性" />
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
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card title="训练样本">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="样本数">{trainingSamples?.row_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="标的数">{trainingSamples?.symbol_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="日期范围">
                {trainingSamples?.start_date ?? "-"} 至 {trainingSamples?.end_date ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="跑赢占比">
                {formatPercent(trainingSamples?.positive_rate ?? undefined)}
              </Descriptions.Item>
              <Descriptions.Item label="声明">
                {trainingSamples?.disclaimer ?? "仅用于研究，不构成投资建议"}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card title="样本切分">
            <Table
              rowKey="split"
              size="middle"
              dataSource={splitRows}
              pagination={false}
              columns={[
                { title: "Split", dataIndex: "split" },
                { title: "样本数", dataIndex: "count", width: 120, align: "right" },
                { title: "占比", dataIndex: "share", width: 120, align: "right", render: formatPercent },
              ]}
            />
          </Card>
        </Col>
      </Row>
      <Card title="特征缺失">
        <Table
          rowKey="featureName"
          size="middle"
          dataSource={missingRows}
          pagination={false}
          columns={[
            { title: "特征名", dataIndex: "featureName" },
            { title: "缺失数", dataIndex: "count", width: 120, align: "right" },
            { title: "缺失率", dataIndex: "share", width: 120, align: "right", render: formatPercent },
          ]}
        />
      </Card>
      <Card title="最近训练样本">
        <Table
          rowKey={(row: TrainingSamplesSummary["latest_samples"][number]) => `${row.date}-${row.symbol}`}
          size="middle"
          dataSource={trainingSamples?.latest_samples ?? []}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          columns={[
            { title: "日期", dataIndex: "date", width: 120 },
            { title: "代码", dataIndex: "symbol", width: 120 },
            { title: "Split", dataIndex: "split", width: 110 },
            { title: "未来收益", dataIndex: "future_5d_return", align: "right", render: formatPercent },
            { title: "基准收益", dataIndex: "benchmark_5d_return", align: "right", render: formatPercent },
            {
              title: "是否跑赢",
              dataIndex: "outperform_benchmark_5d",
              width: 110,
              render: (value: number) => (value === 1 ? "是" : "否"),
            },
          ]}
        />
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

export function PredictionsPage({
  predictions,
  candidates,
  filters,
  appliedFilters,
  dateOptions,
  modelOptions,
  onFiltersChange,
}: {
  predictions: Prediction[];
  candidates: ResearchCandidate[];
  filters: PredictionFilters;
  appliedFilters?: LatestPredictions["filters"];
  dateOptions: string[];
  modelOptions: string[];
  onFiltersChange: (filters: PredictionFilters) => void;
}) {
  const [selectedCandidateSymbol, setSelectedCandidateSymbol] = useState<string>("");
  const selectedCandidate =
    candidates.find((candidate) => candidate.symbol === selectedCandidateSymbol) ?? candidates[0];
  return (
    <>
      <PageTitle
        title="预测"
        description="按交易日、模型版本和 Top N 查询预测排名。预测分数仅用于研究，不构成投资建议。"
      />
      <Alert
        className="page-alert"
        type="warning"
        showIcon
        message="当前输出不是投资建议"
        description="系统只提供候选清单、相对分数、因子归因和风险提示，不输出买入、卖出、持仓比例、目标价或保证收益。进入可用研究阶段前，还需要真实数据稳定、样本外验证、回测复核和人工确认交易约束。"
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
      {candidates.length > 0 ? (
        <Card title="研究参考清单">
          <Paragraph type="secondary">
            清单由后端研究候选 API 生成，仅用于研究，不构成投资建议。风险提示为启发式，不替代停牌、涨跌停或交易约束的精确判定。
          </Paragraph>
          <Table<ResearchCandidate>
            rowKey={(row) => `${row.rank}-${row.symbol}`}
            size="small"
            pagination={false}
            dataSource={candidates}
            onRow={(record) => ({
              onClick: () => setSelectedCandidateSymbol(record.symbol),
            })}
            rowClassName={(record) =>
              selectedCandidate?.symbol === record.symbol ? "selected-table-row" : ""
            }
            columns={[
              { title: "排名", dataIndex: "rank", width: 80 },
              {
                title: "候选标的",
                dataIndex: "symbol",
                width: 170,
                render: (_value, row) => (
                  <Space direction="vertical" size={0}>
                    <Text>{row.symbol_name || row.symbol}</Text>
                    <Text type="secondary">{row.symbol}</Text>
                  </Space>
                ),
              },
              {
                title: "预测分数",
                dataIndex: "score",
                align: "right",
                width: 120,
                render: (value: number) => formatNumber(value),
              },
              {
                title: "相对置信度",
                dataIndex: "confidence",
                width: 150,
                render: (_value: number, row) => (
                  <Space size={6}>
                    <Tag color={watchlistConfidenceColor(row.confidence_level)}>
                      {watchlistConfidenceLabel(row.confidence_level)}
                    </Tag>
                    <Text type="secondary">{formatPercent(row.confidence)}</Text>
                  </Space>
                ),
              },
              {
                title: "因子归因",
                dataIndex: "factors",
                render: (_value, row) =>
                  row.factors.length > 0 ? (
                    <Space size={[4, 4]} wrap>
                      {row.factors.map((factor) => (
                        <Tag
                          color={factor.direction === "up" ? "green" : "red"}
                          key={`${row.symbol}-${factor.name}`}
                        >
                          {factor.name} {formatPercent(factor.value)}
                        </Tag>
                      ))}
                    </Space>
                  ) : (
                    <Text type="secondary">暂无因子</Text>
                  ),
              },
              {
                title: "启发式风险",
                dataIndex: "risk_hints",
                render: (_value, row) =>
                  row.risk_hints.length > 0 ? (
                    <Space size={[4, 4]} wrap>
                      {row.risk_hints.map((hint) => (
                        <Tag color="warning" key={`${row.symbol}-${hint.code}`}>
                          {hint.label}
                        </Tag>
                      ))}
                    </Space>
                  ) : (
                    <Text type="secondary">未触发</Text>
                  ),
              },
              {
                title: "研究动作",
                dataIndex: "research_action",
                width: 220,
                render: (_value, row) => (
                  <Space direction="vertical" size={2}>
                    <Tag color={researchActionColor(row.research_action.status)}>
                      {row.research_action.label}
                    </Tag>
                    {row.research_action.reasons.map((reason) => (
                      <Text type="secondary" key={`${row.symbol}-reason-${reason}`}>
                        {reason}
                      </Text>
                    ))}
                    {row.research_action.blockers.map((blocker) => (
                      <Text type="warning" key={`${row.symbol}-blocker-${blocker}`}>
                        {blocker}
                      </Text>
                    ))}
                  </Space>
                ),
              },
              {
                title: "历史回看",
                dataIndex: "history",
                render: (_value, row) => renderCandidateHistory(row),
              },
              {
                title: "研究备注",
                dataIndex: "research_notes",
                render: (_value, row) => (
                  <Space direction="vertical" size={2}>
                    {row.research_notes.map((note) => (
                      <Text type="secondary" key={`${row.symbol}-${note}`}>
                        {note}
                      </Text>
                    ))}
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      ) : null}
      {selectedCandidate ? (
        <Card title="研究候选解释">
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={8}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="候选标的">
                  {selectedCandidate.symbol_name || selectedCandidate.symbol}
                </Descriptions.Item>
                <Descriptions.Item label="代码">{selectedCandidate.symbol}</Descriptions.Item>
                <Descriptions.Item label="信号日">{selectedCandidate.date}</Descriptions.Item>
                <Descriptions.Item label="模型版本">{selectedCandidate.model_version}</Descriptions.Item>
                <Descriptions.Item label="预测分数">
                  {formatNumber(selectedCandidate.score)}
                </Descriptions.Item>
                <Descriptions.Item label="相对置信度">
                  <Tag color={watchlistConfidenceColor(selectedCandidate.confidence_level)}>
                    {watchlistConfidenceLabel(selectedCandidate.confidence_level)}
                  </Tag>
                  <Text type="secondary">{formatPercent(selectedCandidate.confidence)}</Text>
                </Descriptions.Item>
                <Descriptions.Item label="研究动作">
                  <Tag color={researchActionColor(selectedCandidate.research_action.status)}>
                    {selectedCandidate.research_action.label}
                  </Tag>
                </Descriptions.Item>
              </Descriptions>
            </Col>
            <Col xs={24} xl={8}>
              <Space direction="vertical" size={8} className="full-width">
                <Text strong>为什么进入该分层</Text>
                {selectedCandidate.research_action.reasons.length > 0 ? (
                  selectedCandidate.research_action.reasons.map((reason) => (
                    <Text type="secondary" key={`${selectedCandidate.symbol}-explain-${reason}`}>
                      {reason}
                    </Text>
                  ))
                ) : (
                  <Text type="secondary">暂无结构化理由</Text>
                )}
                <Text strong>阻塞项</Text>
                {selectedCandidate.research_action.blockers.length > 0 ? (
                  selectedCandidate.research_action.blockers.map((blocker) => (
                    <Text type="danger" key={`${selectedCandidate.symbol}-explain-${blocker}`}>
                      {blocker}
                    </Text>
                  ))
                ) : (
                  <Text type="secondary">暂无阻塞项，仍需人工复核。</Text>
                )}
              </Space>
            </Col>
            <Col xs={24} xl={8}>
              <Space direction="vertical" size={8} className="full-width">
                <Text strong>复核清单</Text>
                {buildCandidateReviewChecklist(selectedCandidate).map((item) => (
                  <Text type="secondary" key={`${selectedCandidate.symbol}-${item}`}>
                    {item}
                  </Text>
                ))}
              </Space>
            </Col>
          </Row>
          <Divider />
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={8}>
              <Card size="small" title="因子依据">
                {selectedCandidate.factors.length > 0 ? (
                  <Space size={[4, 4]} wrap>
                    {selectedCandidate.factors.map((factor) => (
                      <Tag
                        color={factor.direction === "up" ? "green" : "red"}
                        key={`${selectedCandidate.symbol}-detail-${factor.name}`}
                      >
                        {factor.name} {formatPercent(factor.value)}
                      </Tag>
                    ))}
                  </Space>
                ) : (
                  <Empty description="暂无因子" />
                )}
              </Card>
            </Col>
            <Col xs={24} xl={8}>
              <Card size="small" title="风险提示">
                {selectedCandidate.risk_hints.length > 0 ? (
                  <Space size={[4, 4]} wrap>
                    {selectedCandidate.risk_hints.map((hint) => (
                      <Tag color="warning" key={`${selectedCandidate.symbol}-detail-${hint.code}`}>
                        {hint.label}
                      </Tag>
                    ))}
                  </Space>
                ) : (
                  <Text type="secondary">未触发启发式风险</Text>
                )}
              </Card>
            </Col>
            <Col xs={24} xl={8}>
              <Card size="small" title="历史回看">
                {renderCandidateHistory(selectedCandidate)}
              </Card>
            </Col>
          </Row>
        </Card>
      ) : null}
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
              columns={buildPredictionColumns()}
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
        description="当前 baseline 使用动量、短期收益和成交量变化构造可复现预测分数；后续真实模型接入后仍需展示模型版本、数据日期、停牌涨跌停处理和人工复核结论。"
      />
    </>
  );
}

export function BacktestsPage({
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
        <Col xs={24} md={12} xl={6}>
          <Card><Statistic title="无法成交" value={backtest?.rejected_trade_count ?? 0} /></Card>
        </Col>
      </Row>
      <Card title="策略实验对比">
        <Paragraph type="secondary">
          对比不同回测配置的历史结果，只用于研究复核。单次或多次历史回测都不代表未来收益。
        </Paragraph>
        {backtests.length > 0 ? (
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={12}>
              <ReactECharts option={buildBacktestComparisonOption(backtests)} style={{ height: 340 }} />
            </Col>
            <Col xs={24} xl={12}>
              <Table<BacktestSummary>
                rowKey="backtest_id"
                size="small"
                pagination={false}
                dataSource={backtests}
                columns={[
                  { title: "回测 ID", dataIndex: "backtest_id" },
                  { title: "Top N", dataIndex: "top_n", width: 80, align: "right" },
                  { title: "累计", dataIndex: "cumulative_return", align: "right", render: formatPercent },
                  { title: "超额", dataIndex: "excess_return", align: "right", render: formatPercent },
                  { title: "回撤", dataIndex: "max_drawdown", align: "right", render: formatPercent },
                  { title: "胜率", dataIndex: "win_rate", align: "right", render: formatPercent },
                  { title: "换手", dataIndex: "turnover_rate", align: "right", render: formatPercent },
                ]}
              />
            </Col>
          </Row>
        ) : (
          <Empty description="暂无可对比回测" />
        )}
      </Card>
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
              title: "组合回撤",
              dataIndex: "portfolio_drawdown",
              align: "right",
              render: formatPercent,
            },
            {
              title: "基准回撤",
              dataIndex: "benchmark_drawdown",
              align: "right",
              render: formatPercent,
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
            {
              title: "相对基准",
              dataIndex: "relative_return",
              align: "right",
              render: formatPercent,
            },
          ]}
        />
      </Card>
      <Card title="无法成交明细">
        {(backtest?.rejected_trades ?? []).length > 0 ? (
          <Table<RejectedTrade>
            rowKey={(row) => `${row.signal_date}-${row.trade_date}-${row.symbol}-${row.rank}`}
            size="middle"
            dataSource={backtest?.rejected_trades ?? []}
            pagination={{ pageSize: 8, hideOnSinglePage: true }}
            columns={[
              { title: "信号日", dataIndex: "signal_date", width: 120 },
              { title: "成交日", dataIndex: "trade_date", width: 120 },
              { title: "代码", dataIndex: "symbol", width: 120 },
              { title: "排名", dataIndex: "rank", width: 80, align: "right" },
              { title: "原因", dataIndex: "reason", render: rejectedTradeReasonLabel },
            ]}
          />
        ) : (
          <Empty description="暂无无法成交记录" />
        )}
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="净值曲线">
            {backtest?.equity_curve?.length ? (
              <ReactECharts className="large-chart" option={buildEquityOption(backtest.equity_curve)} />
            ) : (
              <Empty description="暂无回测曲线" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="回撤曲线">
            {backtest?.equity_curve?.length ? (
              <ReactECharts className="large-chart" option={buildDrawdownOption(backtest.equity_curve)} />
            ) : (
              <Empty description="暂无回撤曲线" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="相对基准曲线">
            {backtest?.equity_curve?.length ? (
              <ReactECharts className="large-chart" option={buildRelativeReturnOption(backtest.equity_curve)} />
            ) : (
              <Empty description="暂无相对基准曲线" />
            )}
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
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
        <Col xs={24} xl={14}>
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

export function StocksPage({
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

export function FundsPage({
  funds,
  candidates,
  source,
  selectedFundCode,
  fundDetail,
  fundNav,
  profile,
  onProfileChange,
  onFundSelect,
  disclaimer,
}: {
  funds: FundSummary[];
  candidates: FundCandidate[];
  source?: FundSourceSummary;
  selectedFundCode: string;
  fundDetail?: FundSummary;
  fundNav?: FundNav;
  profile: "conservative" | "balanced" | "aggressive";
  onProfileChange: (profile: "conservative" | "balanced" | "aggressive") => void;
  onFundSelect: (fundCode: string) => void;
  disclaimer?: string;
}) {
  const fundOptions = funds.map((fund) => ({
    label: `${fund.fund_code} ${fund.fund_name}`,
    value: fund.fund_code,
  }));
  const [comparisonFundCodes, setComparisonFundCodes] = useState<string[]>([]);
  const defaultComparisonCodes = useMemo(
    () => funds.slice(0, Math.min(3, funds.length)).map((fund) => fund.fund_code),
    [funds],
  );
  const effectiveComparisonCodes =
    comparisonFundCodes.length > 0 ? comparisonFundCodes : defaultComparisonCodes;
  const comparisonRows = funds.filter((fund) => effectiveComparisonCodes.includes(fund.fund_code));
  const selectedCandidate = candidates.find((candidate) => candidate.fund_code === selectedFundCode);
  const navRows = fundNav?.nav ?? [];
  const navChartOption = buildFundNavOption(navRows);
  const comparisonChartOption = buildFundComparisonOption(comparisonRows);
  return (
    <>
      <PageTitle
        title="基金"
        description="比较基金的历史收益、回撤、费用和规模，生成研究候选清单。"
      />
      <Alert
        className="page-alert"
        type="info"
        showIcon
        message="研究边界"
        description={`${disclaimer ?? "仅用于研究，不构成投资建议"}。基金页当前只给出候选基金清单、收益/回撤/费用/规模对比和风险提示，不给出申购、赎回、定投金额或仓位建议。`}
      />
      <Alert
        className="page-alert"
        type={source?.source_kind === "real_data" ? "success" : "warning"}
        showIcon
        message={`基金数据来源：${source?.source_label ?? "待确认"}`}
        description={
          source?.source_kind === "real_data"
            ? `当前展示真实基金试跑产物，最新净值日期 ${source.latest_nav_date ?? "-"}。${source.freshness.message}`
            : `${source?.warning ?? "当前使用本地样例基金数据验证指标链路。"} 真实基金数据源、费用口径、基金合同限制和个人风险偏好完成复核前，只能作为研究框架和人工筛选输入。`
        }
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="基金数据来源" value={source?.source_kind === "real_data" ? "真实试跑" : "样例"} />
            <Text type="secondary">{source?.source_label ?? "-"}</Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="最新净值日期" value={source?.latest_nav_date ?? "-"} />
            <Tag color={freshnessColor(source?.freshness.status)}>{source?.freshness.label ?? "待确认"}</Tag>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="基金数量" value={source?.fund_count ?? funds.length} />
            <Text type="secondary">
              {source?.freshness.lag_days === null || source?.freshness.lag_days === undefined
                ? "缺少新鲜度"
                : `距今天 ${source.freshness.lag_days} 天`}
            </Text>
          </Card>
        </Col>
      </Row>
      <Card className="filter-card" title="候选视图">
        <Space wrap>
          <Select
            value={profile}
            onChange={onProfileChange}
            options={[
              { label: "稳健", value: "conservative" },
              { label: "均衡", value: "balanced" },
              { label: "进取", value: "aggressive" },
            ]}
          />
          <Tag color="blue">候选、关注、参考，不代表买入或持有动作</Tag>
          <Tag color={source?.source_kind === "real_data" ? "green" : "orange"}>
            {source?.source_label ?? "数据来源待确认"}
          </Tag>
        </Space>
      </Card>
      <Card title="基金对比">
        <Space direction="vertical" size={12} className="full-width">
          <Space wrap>
            <Select
              mode="multiple"
              value={effectiveComparisonCodes}
              onChange={(values) => setComparisonFundCodes(values.slice(0, 5))}
              options={fundOptions}
              optionFilterProp="label"
              maxTagCount="responsive"
              className="fund-compare-select"
            />
            <Tag color="blue">最多对比 5 只，仍只用于研究筛选</Tag>
          </Space>
          {comparisonRows.length > 0 ? (
            <Row gutter={[16, 16]}>
              <Col xs={24} xl={14}>
                <ReactECharts option={comparisonChartOption} style={{ height: 320 }} />
              </Col>
              <Col xs={24} xl={10}>
                <Table<FundSummary>
                  rowKey={(row) => row.fund_code}
                  size="small"
                  pagination={false}
                  dataSource={comparisonRows}
                  columns={[
                    { title: "基金", dataIndex: "fund_name" },
                    { title: "近1年", dataIndex: "return_1y", align: "right", render: formatPercent },
                    { title: "最大回撤", dataIndex: "max_drawdown", align: "right", render: formatPercent },
                    { title: "波动率", dataIndex: "volatility", align: "right", render: formatPercent },
                    { title: "总费率", dataIndex: "total_fee", align: "right", render: formatPercent },
                  ]}
                />
              </Col>
            </Row>
          ) : (
            <Empty description="请选择基金进行对比" />
          )}
        </Space>
      </Card>
      <Card title="候选基金清单">
        <Table<FundCandidate>
          rowKey={(row) => `${row.profile}-${row.fund_code}`}
          size="middle"
          dataSource={candidates}
          pagination={false}
          onRow={(record) => ({
            onClick: () => onFundSelect(record.fund_code),
          })}
          rowClassName={(record) =>
            record.fund_code === selectedFundCode ? "selected-table-row" : ""
          }
          columns={[
            { title: "排名", dataIndex: "rank", width: 80 },
            { title: "基金代码", dataIndex: "fund_code", width: 110 },
            { title: "基金名称", dataIndex: "fund_name", width: 180 },
            { title: "类型", dataIndex: "fund_type", width: 110 },
            {
              title: "研究分数",
              dataIndex: "score",
              align: "right",
              width: 110,
              render: (value: number) => formatNumber(value),
            },
            {
              title: "等级",
              dataIndex: "score_level",
              width: 90,
              render: (value: string) => (
                <Tag color={value === "high" ? "green" : value === "medium" ? "blue" : "default"}>
                  {value === "high" ? "高" : value === "medium" ? "中" : "低"}
                </Tag>
              ),
            },
            {
              title: "指标归因",
              dataIndex: "factor_reasons",
              render: (items: string[]) => (
                <Space size={[4, 4]} wrap>
                  {items.map((item) => (
                    <Tag key={item}>{item}</Tag>
                  ))}
                </Space>
              ),
            },
            {
              title: "风险提示",
              dataIndex: "risk_notes",
              render: (items: string[]) =>
                items.length > 0 ? (
                  <Space size={[4, 4]} wrap>
                    {items.map((item) => (
                      <Tag color="warning" key={item}>
                        {item}
                      </Tag>
                    ))}
                  </Space>
                ) : (
                  <Text type="secondary">未触发</Text>
                ),
            },
            {
              title: "买前验证",
              dataIndex: "verification_status",
              width: 260,
              render: (_, row) => (
                <Space direction="vertical" size={4}>
                  <Tag color={fundVerificationColor(row.verification_status ?? "review")}>
                    {row.verification_label ?? "需补充验证"}
                  </Tag>
                  {(row.verification_checks ?? []).slice(0, 2).map((item) => (
                    <Text type="secondary" key={item}>
                      {item}
                    </Text>
                  ))}
                  {(row.verification_blockers ?? []).slice(0, 2).map((item) => (
                    <Text type="danger" key={item}>
                      {item}
                    </Text>
                  ))}
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={9}>
          <Card title="基金详情">
            <Space direction="vertical" size={12} className="full-width">
              <Select
                showSearch
                value={selectedFundCode}
                onChange={onFundSelect}
                options={fundOptions}
                optionFilterProp="label"
                className="full-width"
              />
              <Descriptions column={1} size="small">
                <Descriptions.Item label="基金名称">{fundDetail?.fund_name ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="类型">{fundDetail?.fund_type ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="管理人">{fundDetail?.manager ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="成立日期">{fundDetail?.inception_date ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="规模(亿)">
                  {formatNumber(fundDetail?.aum_billion)}
                </Descriptions.Item>
                <Descriptions.Item label="近1年">{formatPercent(fundDetail?.return_1y)}</Descriptions.Item>
                <Descriptions.Item label="近6月">{formatPercent(fundDetail?.return_6m)}</Descriptions.Item>
                <Descriptions.Item label="最大回撤">
                  {formatPercent(fundDetail?.max_drawdown)}
                </Descriptions.Item>
                <Descriptions.Item label="波动率">
                  {formatPercent(fundDetail?.volatility)}
                </Descriptions.Item>
                <Descriptions.Item label="总费率">{formatPercent(fundDetail?.total_fee)}</Descriptions.Item>
              </Descriptions>
            </Space>
          </Card>
        </Col>
        <Col xs={24} xl={15}>
          <Card title="净值走势">
            {navRows.length > 0 ? (
              <ReactECharts option={navChartOption} style={{ height: 320 }} />
            ) : (
              <Empty description="暂无净值数据" />
            )}
          </Card>
        </Col>
      </Row>
      <Card title="买前验证明细">
        {selectedCandidate ? (
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={8}>
              <Tag color={fundVerificationColor(selectedCandidate.verification_status)}>
                {selectedCandidate.verification_label}
              </Tag>
            </Col>
            <Col xs={24} xl={8}>
              <Space direction="vertical" size={4}>
                <Text strong>检查项</Text>
                {selectedCandidate.verification_checks.map((item) => (
                  <Text type="secondary" key={item}>{item}</Text>
                ))}
              </Space>
            </Col>
            <Col xs={24} xl={8}>
              <Space direction="vertical" size={4}>
                <Text strong>阻塞项</Text>
                {selectedCandidate.verification_blockers.map((item) => (
                  <Text type="danger" key={item}>{item}</Text>
                ))}
              </Space>
            </Col>
          </Row>
        ) : (
          <Empty description="请选择候选基金查看验证明细" />
        )}
      </Card>
      <Card title="基金池指标">
        <Table<FundSummary>
          rowKey={(row) => row.fund_code}
          size="middle"
          dataSource={funds}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
          columns={[
            { title: "基金代码", dataIndex: "fund_code", width: 110 },
            { title: "基金名称", dataIndex: "fund_name", width: 180 },
            { title: "类型", dataIndex: "fund_type", width: 110 },
            { title: "管理人", dataIndex: "manager", width: 120 },
            { title: "规模(亿)", dataIndex: "aum_billion", align: "right", render: formatNumber },
            { title: "近1年", dataIndex: "return_1y", align: "right", render: formatPercent },
            { title: "近6月", dataIndex: "return_6m", align: "right", render: formatPercent },
            { title: "最大回撤", dataIndex: "max_drawdown", align: "right", render: formatPercent },
            { title: "波动率", dataIndex: "volatility", align: "right", render: formatPercent },
            { title: "总费率", dataIndex: "total_fee", align: "right", render: formatPercent },
          ]}
        />
      </Card>
    </>
  );
}

export function ReportsPage({
  reports,
  report,
  selectedReportId,
  onSelectReport,
  status,
  dataStatus,
  researchCandidates,
  fundCandidates,
  fundSource,
  qualityIssues,
  dailyBrief,
  isRunning,
  onRunTask,
}: {
  reports: ReportSummary[];
  report?: ReportDetail;
  selectedReportId: string;
  onSelectReport: (reportId: string) => void;
  status?: ResearchStatus;
  dataStatus?: DataStatus;
  researchCandidates: ResearchCandidate[];
  fundCandidates: FundCandidate[];
  fundSource?: FundSourceSummary;
  qualityIssues: DataQualityIssue[];
  dailyBrief?: DailyBrief;
  isRunning?: boolean;
  onRunTask?: (task: TaskTrigger) => void;
}) {
  const riskItems = [
    ...(report?.structured?.risk_notes ?? []),
    ...(report?.structured?.risk_notes?.length
      ? []
      : [
          `当前模型版本：${status?.model.model_version ?? "-"}`,
          `数据覆盖：${status?.data_quality.start_date ?? "-"} 至 ${status?.data_quality.end_date ?? "-"}`,
          `数据质量问题：${status?.data_quality.issue_count ?? 0} 个`,
          "历史回测不代表未来表现，预测结果不能作为交易依据。",
        ]),
  ];
  const reportBacktest = report?.structured?.backtest;
  const actionSummary = report?.structured?.research_actions?.summary;
  const actionCandidates = report?.structured?.research_actions?.candidates ?? [];
  const focusCandidates = researchCandidates.filter(
    (candidate) => candidate.research_action.status === "focus",
  );
  const reviewCandidates = researchCandidates.filter(
    (candidate) => candidate.research_action.status === "review",
  );
  const deferCandidates = researchCandidates.filter(
    (candidate) => candidate.research_action.status === "defer",
  );
  const briefActionSummary = dailyBrief?.stocks.action_summary ?? {
    focus: focusCandidates.length,
    review: reviewCandidates.length,
    defer: deferCandidates.length,
  };
  const briefStockCandidates = dailyBrief?.stocks.candidates ?? researchCandidates.slice(0, 5);
  const briefFundCandidates = dailyBrief?.funds.candidates ?? fundCandidates.slice(0, 5);
  const briefFundSource = dailyBrief?.funds.source ?? fundSource;
  const briefFreshness = dailyBrief?.data.freshness ?? dataStatus?.freshness;
  const briefAcceptance = dailyBrief?.acceptance ?? {
    status: status?.acceptance.status ?? "unknown",
    passed: status?.acceptance.passed ?? null,
    failed_count: status?.acceptance.failed_count ?? 0,
  };
  const briefReviewItems =
    dailyBrief?.review_items ??
    buildDailyBriefReviewItems({
      dataStatus,
      status,
      researchCandidates,
      fundSource,
      qualityIssues,
    });
  const briefNextActions = dailyBrief?.next_actions ?? [];
  const briefTrials = dailyBrief?.trials;

  return (
    <>
      <PageTitle title="报告" description="展示离线研究报告和结构化风险提示。" />
      <Card
        title="每日研究简报"
        extra={
          <Tag color={dailyBrief?.status === "ready" ? "green" : "orange"}>
            {dailyBrief?.status ?? "local"}
          </Tag>
        }
      >
        <Paragraph type="secondary">
          简报只汇总现有研究产物、门禁和候选分层，不构成投资建议，也不输出买入、卖出、仓位或目标价。
        </Paragraph>
        {dailyBrief?.access_issues.length ? (
          <Alert
            className="page-alert"
            type="warning"
            showIcon
            message="简报部分产物缺失"
            description={dailyBrief.access_issues
              .map((issue) => `${issue.name}: ${issue.message}`)
              .join("；")}
          />
        ) : null}
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12} xl={6}>
            <Card size="small">
              <Statistic title="数据新鲜度" value={briefFreshness?.label ?? "待确认"} />
              <Text type="secondary">{briefFreshness?.message ?? "-"}</Text>
            </Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card size="small">
              <Statistic
                title="研究动作"
                value={`${briefActionSummary.focus}/${briefActionSummary.review}/${briefActionSummary.defer}`}
              />
              <Text type="secondary">可关注 / 需复核 / 暂缓观察</Text>
            </Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card size="small">
              <Statistic title="基金候选" value={dailyBrief?.funds.candidate_count ?? fundCandidates.length} />
              <Text type="secondary">{briefFundSource?.source_label ?? "来源待确认"}</Text>
            </Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card size="small">
              <Statistic title="验收门禁" value={briefAcceptance.status} />
              <Text type="secondary">失败项 {briefAcceptance.failed_count}</Text>
            </Card>
          </Col>
        </Row>
        {briefTrials ? (
          <>
            <Divider />
            <Title level={5}>试跑状态</Title>
            <Space wrap>
              {([
                ["股票", briefTrials.akshare],
                ["基金", briefTrials.fund],
              ] as const).map(([label, trial]) => (
                <Fragment key={label}>
                  <Tag color={preflightStatusColor(trial?.status)}>
                    {label}：{trial?.status ?? "missing"}
                  </Tag>
                  <Text type="secondary">
                    {label}真实数据{trial?.real_data_verified ? "已验证" : "未验证"}
                  </Text>
                </Fragment>
              ))}
            </Space>
          </>
        ) : null}
        <Divider />
        {briefNextActions.length > 0 ? (
          <>
            <Title level={5}>下一步动作</Title>
            <Row gutter={[12, 12]}>
              {briefNextActions.map((action) => {
                const task = action.task;
                return (
                  <Col xs={24} md={12} xl={8} key={action.id}>
                    <Card size="small">
                      <Space direction="vertical" size={8} className="full-width">
                        <Space wrap>
                          <Text strong>{action.label}</Text>
                          <Tag color={task ? "blue" : "default"}>
                            {task ? "可触发任务" : "人工复核"}
                          </Tag>
                        </Space>
                        <Text type="secondary">{action.description}</Text>
                        {task ? (
                          <Button
                            size="small"
                            type="primary"
                            loading={isRunning}
                            disabled={!onRunTask}
                            onClick={() => onRunTask?.(task)}
                          >
                            执行
                          </Button>
                        ) : null}
                      </Space>
                    </Card>
                  </Col>
                );
              })}
            </Row>
            <Divider />
          </>
        ) : null}
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={8}>
            <Title level={5}>股票研究候选</Title>
            {briefStockCandidates.length > 0 ? (
              <Space direction="vertical" size={6} className="full-width">
                {briefStockCandidates.map((candidate) => (
                  <Text key={`${candidate.rank}-${candidate.symbol}`}>
                    {candidate.rank}. {candidate.symbol_name || candidate.symbol}：
                    <Tag color={researchActionColor(candidate.research_action.status)}>
                      {candidate.research_action.label}
                    </Tag>
                  </Text>
                ))}
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无股票候选" />
            )}
          </Col>
          <Col xs={24} xl={8}>
            <Title level={5}>基金研究候选</Title>
            {briefFundCandidates.length > 0 ? (
              <Space direction="vertical" size={6} className="full-width">
                {briefFundCandidates.map((candidate) => (
                  <Text key={`${candidate.rank}-${candidate.fund_code}`}>
                    {candidate.rank}. {candidate.fund_name}：
                    <Tag color={fundVerificationColor(candidate.verification_status)}>
                      {candidate.verification_label}
                    </Tag>
                  </Text>
                ))}
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无基金候选" />
            )}
          </Col>
          <Col xs={24} xl={8}>
            <Title level={5}>今日复核重点</Title>
            <Space direction="vertical" size={6} className="full-width">
              {briefReviewItems.map((item) => (
                <Text type="secondary" key={item}>{item}</Text>
              ))}
            </Space>
          </Col>
        </Row>
      </Card>
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
              <Text>结构化 JSON：{report?.payload_path ?? "-"}</Text>
              <Text>预测条数：{report?.structured?.predictions?.length ?? "-"}</Text>
              <Text>累计收益：{formatPercent(reportBacktest?.cumulative_return)}</Text>
              <Text>超额收益：{formatPercent(reportBacktest?.excess_return)}</Text>
              <Text>最大回撤：{formatPercent(reportBacktest?.max_drawdown)}</Text>
              <Text>AI 报告状态：{report?.ai_report?.status ?? "-"}</Text>
              <Text>AI Provider：{report?.ai_report?.provider ?? "-"}</Text>
              <Text>AI 模型：{report?.ai_report?.model ?? "-"}</Text>
              <Text>AI 状态说明：{report?.ai_report?.reason ?? "-"}</Text>
              <Text>
                研究动作：可关注 {actionSummary?.focus ?? 0}，需复核 {actionSummary?.review ?? 0}，暂缓观察{" "}
                {actionSummary?.defer ?? 0}
              </Text>
              {actionCandidates.slice(0, 5).map((candidate) => (
                <Text key={`${candidate.rank}-${candidate.symbol}`}>
                  {candidate.rank}. {candidate.symbol_name ?? candidate.symbol}（{candidate.symbol}）：
                  {candidate.research_action.label}
                </Text>
              ))}
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

export function SettingsPage({
  settings,
  artifactStatus,
  akshareUniverse,
}: {
  settings?: LocalSettings;
  artifactStatus?: ArtifactStatus;
  akshareUniverse?: AkshareUniverseStatus;
}) {
  const artifacts = artifactStatus?.artifacts ?? settings?.artifacts ?? [];
  const akshareUniverseDescription = akshareUniverse
    ? akshareUniverse.passed
      ? `模式 ${akshareUniverse.universe_mode ?? "-"}，解析 ${akshareUniverse.symbol_count ?? 0} 个标的，最低门槛 ${akshareUniverse.minimum_expected_count ?? 0}。样例：${akshareUniverse.symbols_sample?.join(", ") || "-"}`
      : `${akshareUniverse.error ?? "akshare_universe_failed"}：${akshareUniverse.message ?? "股票池解析未通过"}`
    : "暂无股票池解析结果";
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
              <Descriptions.Item label="数据源">
                <Tag color={settings?.runtime.data_source === "akshare" ? "blue" : "default"}>
                  {settings?.runtime.data_source ?? "-"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="模型类型">{settings?.runtime.model_type ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="LLM">
                <Tag color={settings?.runtime.llm_provider === "disabled" ? "default" : "green"}>
                  {settings?.runtime.llm_provider ?? "-"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="声明">
                {settings?.service.disclaimer ?? "仅用于研究，不构成投资建议"}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card title="配置与产物">
            <Descriptions column={2} size="small" className="settings-runtime">
              <Descriptions.Item label="AKShare 股票池模式">
                {settings?.akshare.universe_mode ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="AKShare 股票池">
                {settings?.akshare.symbols.join(", ") ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="AKShare 区间">
                {settings ? `${settings.akshare.start_date} 至 ${settings.akshare.end_date}` : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="AKShare 基准">
                {settings?.akshare.benchmark_symbol ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="AKShare 试跑上限">
                {settings?.akshare.max_symbols ?? "未限制"}
              </Descriptions.Item>
              <Descriptions.Item label="DeepSeek 模型">
                {settings?.llm.deepseek_model ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="DeepSeek Base URL">
                {settings?.llm.deepseek_base_url ?? "-"}
              </Descriptions.Item>
            </Descriptions>
            <Alert
              className="settings-runtime"
              type={
                settings?.preflight.status === "failed"
                  ? "error"
                  : settings?.preflight.status === "warning"
                    ? "warning"
                    : "success"
              }
              showIcon
              message="运行前预检"
              description={
                settings
                  ? `状态 ${settings.preflight.status}，${settings.preflight.failed_count} 个失败，${settings.preflight.warning_count} 个警告。`
                  : "暂无预检结果"
              }
            />
            <Alert
              className="settings-runtime"
              type={akshareUniverse?.passed ? "success" : akshareUniverse ? "warning" : "info"}
              showIcon
              message="股票池解析门禁"
              description={akshareUniverseDescription}
            />
            <Table
              rowKey="key"
              size="small"
              className="settings-runtime"
              dataSource={settings?.preflight.checks ?? []}
              pagination={false}
              columns={buildCheckColumns({
                statusLabel: "raw",
                nameWidth: 160,
                statusWidth: 110,
              })}
            />
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
              columns={buildArtifactColumns({ missingColor: "orange" })}
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

function watchlistConfidenceLabel(level: ResearchCandidate["confidence_level"]): string {
  if (level === "high") {
    return "高";
  }
  if (level === "medium") {
    return "中";
  }
  return "低";
}

function watchlistConfidenceColor(level: ResearchCandidate["confidence_level"]): string {
  if (level === "high") {
    return "green";
  }
  if (level === "medium") {
    return "blue";
  }
  return "default";
}

function researchActionColor(status: ResearchCandidate["research_action"]["status"]): string {
  if (status === "focus") {
    return "green";
  }
  if (status === "review") {
    return "orange";
  }
  return "default";
}

function buildCandidateReviewChecklist(candidate: ResearchCandidate): string[] {
  const checklist = [
    "核对数据新鲜度、停牌和涨跌停约束",
    "复核候选信号是否来自样本外日期",
    "查看同标的历史成熟样本表现",
  ];
  if (candidate.risk_hints.length > 0) {
    checklist.push("先处理启发式风险提示，再进入人工研究池");
  }
  if (candidate.history.sample_count <= 0) {
    checklist.push("历史成熟样本不足，不能形成强结论");
  }
  if (candidate.research_action.blockers.length > 0) {
    checklist.push("逐项消除阻塞项后再复核");
  }
  return checklist;
}

function buildDailyBriefReviewItems({
  dataStatus,
  status,
  researchCandidates,
  fundSource,
  qualityIssues,
}: {
  dataStatus?: DataStatus;
  status?: ResearchStatus;
  researchCandidates: ResearchCandidate[];
  fundSource?: FundSourceSummary;
  qualityIssues: DataQualityIssue[];
}): string[] {
  const items: string[] = [];
  if (dataStatus?.freshness?.status === "stale") {
    items.push(`先更新行情数据：${dataStatus.freshness.message}`);
  }
  if (status?.acceptance.passed === false) {
    items.push(`验收门禁未通过：失败 ${status.acceptance.failed_count} 项`);
  }
  if (qualityIssues.length > 0) {
    items.push(`数据质量问题 ${qualityIssues.length} 个，先复核异常数据`);
  }
  const blockedCandidates = researchCandidates.filter(
    (candidate) => candidate.research_action.blockers.length > 0,
  );
  if (blockedCandidates.length > 0) {
    items.push(`股票候选存在 ${blockedCandidates.length} 个阻塞项，先处理需复核/暂缓观察原因`);
  }
  if (fundSource?.source_kind === "sample") {
    items.push("基金页当前使用样例数据，真实研究前先运行基金真实试跑");
  }
  if (items.length === 0) {
    items.push("当前无明显阻塞项，仍需人工复核研究假设和交易约束");
  }
  return items;
}

function fundVerificationColor(status: FundCandidate["verification_status"]): string {
  if (status === "ready") {
    return "green";
  }
  if (status === "review") {
    return "orange";
  }
  return "red";
}

function freshnessColor(status?: DataFreshness["status"]): string {
  if (status === "fresh") {
    return "green";
  }
  if (status === "aging") {
    return "orange";
  }
  if (status === "stale") {
    return "red";
  }
  return "default";
}

function healthStatusColor(status?: string): string {
  if (["passed", "complete", "healthy", "fresh", "dry_run"].includes(status ?? "")) {
    return "green";
  }
  if (["warning", "aging", "incomplete"].includes(status ?? "")) {
    return "orange";
  }
  if (["failed", "stale", "missing", "invalid", "inconsistent"].includes(status ?? "")) {
    return "red";
  }
  return "default";
}

function buildFundNavOption(rows: FundNavPoint[]) {
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 24, top: 24, bottom: 48 },
    xAxis: {
      type: "category",
      data: rows.map((row) => row.date),
      axisLabel: { hideOverlap: true },
    },
    yAxis: {
      type: "value",
      scale: true,
    },
    series: [
      {
        name: "单位净值",
        type: "line",
        showSymbol: false,
        smooth: true,
        data: rows.map((row) => row.nav),
      },
    ],
  };
}

function buildFundComparisonOption(rows: FundSummary[]) {
  const names = rows.map((row) => row.fund_name);
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { left: 48, right: 24, top: 48, bottom: 56 },
    xAxis: {
      type: "category",
      data: names,
      axisLabel: { interval: 0, rotate: names.length > 3 ? 25 : 0 },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
    },
    series: [
      {
        name: "近1年",
        type: "bar",
        data: rows.map((row) => row.return_1y),
      },
      {
        name: "最大回撤",
        type: "bar",
        data: rows.map((row) => row.max_drawdown),
      },
      {
        name: "波动率",
        type: "bar",
        data: rows.map((row) => row.volatility),
      },
      {
        name: "总费率",
        type: "bar",
        data: rows.map((row) => row.total_fee),
      },
    ],
  };
}

function buildBacktestComparisonOption(rows: BacktestSummary[]) {
  const labels = rows.map((row) => row.backtest_id);
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { left: 48, right: 24, top: 48, bottom: 64 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { interval: 0, rotate: labels.length > 2 ? 25 : 0 },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
    },
    series: [
      {
        name: "累计收益",
        type: "bar",
        data: rows.map((row) => row.cumulative_return),
      },
      {
        name: "超额收益",
        type: "bar",
        data: rows.map((row) => row.excess_return),
      },
      {
        name: "最大回撤",
        type: "bar",
        data: rows.map((row) => row.max_drawdown),
      },
      {
        name: "胜率",
        type: "bar",
        data: rows.map((row) => row.win_rate),
      },
    ],
  };
}

function renderCandidateHistory(row: ResearchCandidate) {
  const history = row.history;
  if (!history || history.sample_count <= 0) {
    return <Text type="secondary">暂无成熟样本</Text>;
  }
  return (
    <Space direction="vertical" size={2}>
      <Text>历史样本 {history.sample_count}</Text>
      <Text type="secondary">跑赢率 {formatPercent(history.outperform_rate ?? undefined)}</Text>
      <Text type="secondary">均值 {formatPercent(history.average_future_5d_return ?? undefined)}</Text>
      <Text type="secondary">最新信号 {history.latest_signal_date ?? "-"}</Text>
    </Space>
  );
}

function dataSourceQualityColor(level?: string): string {
  if (level === "good") {
    return "green";
  }
  if (level === "usable") {
    return "blue";
  }
  if (level === "poor") {
    return "red";
  }
  return "default";
}
