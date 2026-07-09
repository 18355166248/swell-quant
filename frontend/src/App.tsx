import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Alert,
  Button,
  Layout,
  Menu,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import {
  BarChartOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FundProjectionScreenOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SettingOutlined,
  StockOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AcceptancePage,
  BacktestsPage,
  DashboardPage,
  DataPage,
  FundsPage,
  ModelsPage,
  PredictionsPage,
  ReportsPage,
  SettingsPage,
  StocksPage,
  TasksPage,
  type PredictionFilters,
} from "./pages/researchPages";
import { api, type FundProfile, type PredictionQuery } from "./api/client";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

export type PageKey =
  | "dashboard"
  | "acceptance"
  | "data"
  | "tasks"
  | "models"
  | "predictions"
  | "backtests"
  | "funds"
  | "stocks"
  | "reports"
  | "settings";

const PAGE_ROUTES: Record<PageKey, string> = {
  dashboard: "/dashboard",
  acceptance: "/acceptance",
  data: "/data",
  tasks: "/tasks",
  models: "/models",
  predictions: "/predictions",
  backtests: "/backtests",
  funds: "/funds",
  stocks: "/stocks",
  reports: "/reports",
  settings: "/settings",
};

const ROUTE_PAGES = Object.fromEntries(
  Object.entries(PAGE_ROUTES).map(([page, path]) => [path, page]),
) as Record<string, PageKey>;

export function pageFromPath(pathname: string): PageKey {
  const normalized = pathname === "/" ? PAGE_ROUTES.dashboard : pathname.replace(/\/+$/, "");
  return ROUTE_PAGES[normalized] ?? "dashboard";
}

export function pathForPage(page: PageKey): string {
  return PAGE_ROUTES[page];
}

export function resetScrollContainer(container: Pick<HTMLElement, "scrollTo" | "scrollTop"> | null) {
  if (!container) {
    return;
  }
  if (typeof container.scrollTo === "function") {
    container.scrollTo({ top: 0, left: 0, behavior: "auto" });
    return;
  }
  container.scrollTop = 0;
}

function App() {
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const contentRef = useRef<HTMLElement | null>(null);
  const [activePage, setActivePage] = useState<PageKey>(() =>
    typeof window === "undefined" ? "dashboard" : pageFromPath(window.location.pathname),
  );
  const [selectedSymbol, setSelectedSymbol] = useState("000300.SH");
  const [selectedBacktestId, setSelectedBacktestId] = useState("sample-topn-baseline");
  const [selectedReportId, setSelectedReportId] = useState("sample-research-summary");
  const [selectedModelVersion, setSelectedModelVersion] = useState("baseline-rule-v1");
  const [fundProfile, setFundProfile] = useState<FundProfile>("balanced");
  const [predictionFilters, setPredictionFilters] = useState<PredictionFilters>({
    date: "",
    modelVersion: "",
    topN: 10,
  });

  const statusQuery = useQuery({ queryKey: ["status"], queryFn: api.getStatus });
  const acceptanceQuery = useQuery({ queryKey: ["acceptance"], queryFn: api.getAcceptance });
  const artifactsQuery = useQuery({ queryKey: ["artifacts"], queryFn: api.getArtifacts });
  const progressQuery = useQuery({ queryKey: ["progress"], queryFn: api.getProgress });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const pipelineQuery = useQuery({ queryKey: ["pipeline"], queryFn: api.getPipeline });
  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: api.getTasks });
  const taskDetailQuery = useQuery({
    queryKey: ["tasks", "pipeline-latest"],
    queryFn: () => api.getTaskDetail("pipeline-latest"),
  });
  const akshareTrialQuery = useQuery({
    queryKey: ["akshare-trial"],
    queryFn: api.getAkshareTrial,
    enabled: activePage === "tasks",
  });
  const dataStatusQuery = useQuery({ queryKey: ["data-status"], queryFn: api.getDataStatus });
  const akshareUniverseQuery = useQuery({
    queryKey: ["akshare-universe"],
    queryFn: api.getAkshareUniverse,
    enabled: activePage === "settings",
  });
  const duckdbStorageQuery = useQuery({ queryKey: ["duckdb-storage"], queryFn: api.getDuckDBStorage });
  const qualityQuery = useQuery({ queryKey: ["data-quality"], queryFn: api.getDataQuality });
  const featuresQuery = useQuery({ queryKey: ["features"], queryFn: api.getFeatures });
  const labelsQuery = useQuery({ queryKey: ["labels"], queryFn: api.getLabels });
  const latestModelQuery = useQuery({ queryKey: ["model", "latest"], queryFn: api.getLatestModel });
  const modelsQuery = useQuery({ queryKey: ["models"], queryFn: api.getModels });
  const trainingSamplesQuery = useQuery({ queryKey: ["training-samples"], queryFn: api.getTrainingSamples });
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
  const researchCandidatesQuery = useQuery({
    queryKey: ["research-candidates", predictionFilters.topN],
    queryFn: () => api.getResearchCandidates({ topN: predictionFilters.topN }),
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
  const fundsQuery = useQuery({ queryKey: ["funds"], queryFn: api.getFunds });
  const fundCandidatesQuery = useQuery({
    queryKey: ["funds", "candidates", fundProfile],
    queryFn: () => api.getFundCandidates(fundProfile),
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

  useEffect(() => {
    const syncFromLocation = () => setActivePage(pageFromPath(window.location.pathname));
    window.addEventListener("popstate", syncFromLocation);
    return () => window.removeEventListener("popstate", syncFromLocation);
  }, []);

  const navigateToPage = (page: PageKey) => {
    const path = pathForPage(page);
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }
    setActivePage(page);
  };

  useEffect(() => {
    // 右侧内容区是独立滚动容器；切换菜单时必须复位，避免新页面继承上一页滚动位置。
    resetScrollContainer(contentRef.current);
  }, [activePage]);

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
    progressQuery.isLoading ||
    qualityQuery.isLoading ||
    tasksQuery.isLoading ||
    taskDetailQuery.isLoading ||
    (activePage === "tasks" && akshareTrialQuery.isLoading) ||
    dataStatusQuery.isLoading ||
    (activePage === "settings" && akshareUniverseQuery.isLoading) ||
    duckdbStorageQuery.isLoading ||
    featuresQuery.isLoading ||
    labelsQuery.isLoading ||
    trainingSamplesQuery.isLoading ||
    predictionsQuery.isLoading ||
    latestModelQuery.isLoading ||
    modelsQuery.isLoading ||
    modelDetailQuery.isLoading ||
    backtestsQuery.isLoading ||
    backtestDetailQuery.isLoading ||
    backtestQuery.isLoading ||
    predictionsListQuery.isLoading ||
    researchCandidatesQuery.isLoading ||
    reportQuery.isLoading ||
    reportsQuery.isLoading ||
    reportDetailQuery.isLoading ||
    stocksQuery.isLoading ||
    fundsQuery.isLoading ||
    fundCandidatesQuery.isLoading ||
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
    progressQuery.isError ||
    qualityQuery.isError ||
    tasksQuery.isError ||
    taskDetailQuery.isError ||
    (activePage === "tasks" && akshareTrialQuery.isError) ||
    dataStatusQuery.isError ||
    duckdbStorageQuery.isError ||
    featuresQuery.isError ||
    labelsQuery.isError ||
    trainingSamplesQuery.isError ||
    predictionsQuery.isError ||
    latestModelQuery.isError ||
    modelsQuery.isError ||
    modelDetailQuery.isError ||
    backtestsQuery.isError ||
    backtestDetailQuery.isError ||
    backtestQuery.isError ||
    predictionsListQuery.isError ||
    researchCandidatesQuery.isError ||
    reportQuery.isError ||
    reportsQuery.isError ||
    reportDetailQuery.isError ||
    stocksQuery.isError ||
    fundsQuery.isError ||
    fundCandidatesQuery.isError ||
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
        progress={progressQuery.data}
        report={report}
      />
    ),
    acceptance: (
      <AcceptancePage
        acceptance={acceptanceQuery.data}
        artifactStatus={status?.artifact_status}
        trainingSamples={status?.training_samples}
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
        akshareTrial={akshareTrialQuery.data}
        isRunning={runPipelineMutation.isPending}
        onRunTask={(task) => runPipelineMutation.mutate(task)}
      />
    ),
    models: (
      <ModelsPage
        models={modelsQuery.data?.models ?? []}
        model={modelDetailQuery.data ?? latestModelQuery.data}
        trainingSamples={trainingSamplesQuery.data}
        selectedModelVersion={selectedModelVersion}
        onSelectModel={setSelectedModelVersion}
      />
    ),
    predictions: (
      <PredictionsPage
        predictions={predictionRows}
        candidates={researchCandidatesQuery.data?.candidates ?? []}
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
    funds: (
      <FundsPage
        funds={fundsQuery.data?.funds ?? []}
        candidates={fundCandidatesQuery.data?.candidates ?? []}
        profile={fundProfile}
        onProfileChange={setFundProfile}
        disclaimer={fundCandidatesQuery.data?.disclaimer ?? fundsQuery.data?.disclaimer}
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
    settings: (
      <SettingsPage
        settings={settingsQuery.data}
        artifactStatus={artifactsQuery.data}
        akshareUniverse={akshareUniverseQuery.data}
      />
    ),
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
          onClick={(item) => navigateToPage(item.key as PageKey)}
          items={[
            { key: "dashboard", icon: <BarChartOutlined />, label: "工作台" },
            { key: "acceptance", icon: <CheckCircleOutlined />, label: "验收" },
            { key: "data", icon: <DatabaseOutlined />, label: "数据" },
            { key: "tasks", icon: <SyncOutlined />, label: "任务" },
            { key: "models", icon: <ExperimentOutlined />, label: "模型" },
            { key: "predictions", icon: <LineChartOutlined />, label: "预测" },
            { key: "backtests", icon: <DatabaseOutlined />, label: "回测" },
            { key: "funds", icon: <FundProjectionScreenOutlined />, label: "基金" },
            { key: "stocks", icon: <StockOutlined />, label: "单股" },
            { key: "reports", icon: <FileTextOutlined />, label: "报告" },
            { key: "settings", icon: <SettingOutlined />, label: "设置" },
          ]}
        />
      </Sider>
      <Layout className="main-panel">
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
        <Content className="content" ref={contentRef}>
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
