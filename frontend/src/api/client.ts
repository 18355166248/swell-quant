import type {
  AcceptanceStatus,
  AkshareTrialRun,
  AkshareUniverseStatus,
  ArtifactStatus,
  BacktestList,
  DailyBrief,
  DataQuality,
  DataStatus,
  DuckDBStorageStatus,
  FeatureSummary,
  FundCandidates,
  FundList,
  FundNav,
  FundSummary,
  FundTrialRun,
  LabelSummary,
  LatestBacktest,
  LatestModel,
  LatestPredictions,
  LocalSettings,
  ModelList,
  PipelineRun,
  ProjectProgress,
  ResearchCandidates,
  ReportDetail,
  ReportList,
  ResearchStatus,
  StockFeatures,
  StockList,
  StockPredictions,
  StockPrices,
  StockSummary,
  TaskDetail,
  TaskList,
  TaskTrigger,
  TrainingSamplesSummary,
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export interface PredictionQuery {
  date?: string | null;
  modelVersion?: string | null;
  topN?: number | null;
}

export type FundProfile = "conservative" | "balanced" | "aggressive";

export type { TaskTrigger };

const TASK_TRIGGER_PATHS: Record<TaskTrigger, string> = {
  pipeline: "/api/pipeline/run",
  data_update: "/api/data/update",
  model_train: "/api/models/train",
  prediction_run: "/api/predictions/run",
  backtest_run: "/api/backtests/run",
  report_generate: "/api/reports/generate",
  fund_trial: "/api/funds/trial/run",
  akshare_trial: "/api/akshare/trial/run",
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const message =
      payload?.message ?? payload?.error ?? `${response.status} ${response.statusText}`;
    throw new Error(message);
  }

  return payload as T;
}

async function requestText(path: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.text();
}

async function requestJsonLenient<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  const payload = await response.json();
  return payload as T;
}

export const api = {
  getStatus: () => requestJson<ResearchStatus>("/api/status"),
  getAcceptance: () => requestJson<AcceptanceStatus>("/api/acceptance"),
  getArtifacts: () => requestJson<ArtifactStatus>("/api/artifacts"),
  getProgress: () => requestJson<ProjectProgress>("/api/progress"),
  getSettings: () => requestJson<LocalSettings>("/api/settings"),
  getPipeline: () => requestJson<PipelineRun>("/api/pipeline"),
  getTasks: () => requestJson<TaskList>("/api/tasks"),
  getTaskDetail: (taskId: string) => requestJson<TaskDetail>(`/api/tasks/${taskId}`),
  getDataStatus: () => requestJson<DataStatus>("/api/data/status"),
  getAkshareUniverse: () => requestJsonLenient<AkshareUniverseStatus>("/api/akshare/universe"),
  getAkshareTrial: () => requestJsonLenient<AkshareTrialRun>("/api/akshare/trial"),
  getFundTrial: () => requestJsonLenient<FundTrialRun>("/api/funds/trial"),
  getDuckDBStorage: () => requestJson<DuckDBStorageStatus>("/api/storage/duckdb"),
  getDataQuality: () => requestJson<DataQuality>("/api/data-quality"),
  getFeatures: () => requestJson<FeatureSummary>("/api/features"),
  getLabels: () => requestJson<LabelSummary>("/api/labels"),
  getModels: () => requestJson<ModelList>("/api/models"),
  getModel: (modelVersion: string) => requestJson<LatestModel>(`/api/models/${modelVersion}`),
  getLatestModel: () => requestJson<LatestModel>("/api/models/latest"),
  getTrainingSamples: () => requestJson<TrainingSamplesSummary>("/api/training-samples"),
  getLatestPredictions: () => requestJson<LatestPredictions>("/api/predictions/latest"),
  getPredictions: (query: PredictionQuery = {}) => {
    const params = new URLSearchParams();
    if (query.date) {
      params.set("date", query.date);
    }
    if (query.modelVersion) {
      params.set("model_version", query.modelVersion);
    }
    if (query.topN !== null && query.topN !== undefined) {
      params.set("top_n", String(query.topN));
    }
    const suffix = params.size > 0 ? `?${params.toString()}` : "";
    return requestJson<LatestPredictions>(`/api/predictions${suffix}`);
  },
  getResearchCandidates: (query: Pick<PredictionQuery, "topN"> = {}) => {
    const params = new URLSearchParams();
    if (query.topN !== null && query.topN !== undefined) {
      params.set("top_n", String(query.topN));
    }
    const suffix = params.size > 0 ? `?${params.toString()}` : "";
    return requestJson<ResearchCandidates>(`/api/research-candidates/latest${suffix}`);
  },
  getLatestBacktest: () => requestJson<LatestBacktest>("/api/backtest/latest"),
  getBacktests: () => requestJson<BacktestList>("/api/backtests"),
  getBacktest: (backtestId: string) => requestJson<LatestBacktest>(`/api/backtests/${backtestId}`),
  getReport: () => requestText("/api/report"),
  getReports: () => requestJson<ReportList>("/api/reports"),
  getReportDetail: (reportId: string) => requestJson<ReportDetail>(`/api/reports/${reportId}`),
  getDailyBrief: () => requestJson<DailyBrief>("/api/daily-brief"),
  getStocks: () => requestJson<StockList>("/api/stocks"),
  getStockSummary: (symbol: string) => requestJson<StockSummary>(`/api/stocks/${symbol}`),
  getStockPrices: (symbol: string) => requestJson<StockPrices>(`/api/stocks/${symbol}/prices`),
  getStockFeatures: (symbol: string) =>
    requestJson<StockFeatures>(`/api/stocks/${symbol}/features`),
  getStockPredictions: (symbol: string) =>
    requestJson<StockPredictions>(`/api/stocks/${symbol}/predictions`),
  getFunds: () => requestJson<FundList>("/api/funds"),
  getFund: (fundCode: string) => requestJson<FundSummary>(`/api/funds/${fundCode}`),
  getFundNav: (fundCode: string) => requestJson<FundNav>(`/api/funds/${fundCode}/nav`),
  getFundCandidates: (profile: FundProfile = "balanced") =>
    requestJson<FundCandidates>(`/api/funds/candidates?profile=${profile}`),
  runTask: async (task: TaskTrigger = "pipeline") => {
    // 这里只触发后端任务端点；当前 MVP 由后端统一串完整 pipeline，避免派生产物口径分叉。
    const response = await fetch(`${API_BASE_URL}${TASK_TRIGGER_PATHS[task]}`, {
      method: "POST",
    });
    const payload = (await response.json()) as PipelineRun;
    if (!response.ok && response.status !== 409) {
      throw new Error(payload.message ?? payload.error ?? `${response.status} ${response.statusText}`);
    }
    return payload;
  },
  runPipeline: () => api.runTask("pipeline"),
};
