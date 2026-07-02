import type {
  BacktestList,
  DataQuality,
  DataStatus,
  FeatureSummary,
  LatestBacktest,
  LatestModel,
  LatestPredictions,
  LocalSettings,
  ModelList,
  PipelineRun,
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
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export interface PredictionQuery {
  date?: string | null;
  modelVersion?: string | null;
  topN?: number | null;
}

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

export const api = {
  getStatus: () => requestJson<ResearchStatus>("/api/status"),
  getSettings: () => requestJson<LocalSettings>("/api/settings"),
  getPipeline: () => requestJson<PipelineRun>("/api/pipeline"),
  getTasks: () => requestJson<TaskList>("/api/tasks"),
  getTaskDetail: (taskId: string) => requestJson<TaskDetail>(`/api/tasks/${taskId}`),
  getDataStatus: () => requestJson<DataStatus>("/api/data/status"),
  getDataQuality: () => requestJson<DataQuality>("/api/data-quality"),
  getFeatures: () => requestJson<FeatureSummary>("/api/features"),
  getModels: () => requestJson<ModelList>("/api/models"),
  getModel: (modelVersion: string) => requestJson<LatestModel>(`/api/models/${modelVersion}`),
  getLatestModel: () => requestJson<LatestModel>("/api/models/latest"),
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
  getLatestBacktest: () => requestJson<LatestBacktest>("/api/backtest/latest"),
  getBacktests: () => requestJson<BacktestList>("/api/backtests"),
  getBacktest: (backtestId: string) => requestJson<LatestBacktest>(`/api/backtests/${backtestId}`),
  getReport: () => requestText("/api/report"),
  getReports: () => requestJson<ReportList>("/api/reports"),
  getReportDetail: (reportId: string) => requestJson<ReportDetail>(`/api/reports/${reportId}`),
  getStocks: () => requestJson<StockList>("/api/stocks"),
  getStockSummary: (symbol: string) => requestJson<StockSummary>(`/api/stocks/${symbol}`),
  getStockPrices: (symbol: string) => requestJson<StockPrices>(`/api/stocks/${symbol}/prices`),
  getStockFeatures: (symbol: string) =>
    requestJson<StockFeatures>(`/api/stocks/${symbol}/features`),
  getStockPredictions: (symbol: string) =>
    requestJson<StockPredictions>(`/api/stocks/${symbol}/predictions`),
  runPipeline: async () => {
    // 这里只触发后端离线链路；前端不直接计算因子、标签、训练或回测，避免两套口径分叉。
    const response = await fetch(`${API_BASE_URL}/api/pipeline/run`, {
      method: "POST",
    });
    const payload = (await response.json()) as PipelineRun;
    if (!response.ok && response.status !== 409) {
      throw new Error(payload.message ?? payload.error ?? `${response.status} ${response.statusText}`);
    }
    return payload;
  },
};
