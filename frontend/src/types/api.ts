export type PipelineStepStatus = "success" | "failed" | "skipped";

export interface PipelineStep {
  name: string;
  status: PipelineStepStatus;
  message: string;
  started_at?: string;
  ended_at?: string;
  duration_seconds: number;
}

export interface PipelineRun {
  status: "success" | "failed" | "busy";
  manifest_path?: string;
  status_path?: string | null;
  started_at?: string;
  ended_at?: string;
  finished_at?: string;
  duration_seconds?: number;
  steps?: PipelineStep[];
  error?: string;
  message?: string;
}

export interface TaskSummary {
  id: string;
  type: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  step_count: number;
  failed_step: string | null;
  output_path: string;
}

export interface TaskList {
  count: number;
  tasks: TaskSummary[];
}

export interface TaskDetail extends TaskSummary {
  steps: PipelineStep[];
}

export interface ResearchStatus {
  pipeline: {
    status: string;
    started_at: string;
    ended_at: string;
    duration_seconds: number;
    step_count: number;
  };
  data_quality: {
    passed: boolean;
    row_count: number;
    symbol_count: number;
    start_date: string;
    end_date: string;
    issue_count: number;
  };
  model: {
    model_version: string;
    model_type: string;
    train_start: string;
    train_end: string;
    prediction_date: string;
    feature_names: string[];
  };
  predictions: {
    count: number;
    top: Prediction[];
  };
  backtest: {
    backtest_id: string;
    top_n: number;
    trade_count: number;
    start_date: string;
    end_date: string;
    cumulative_return: number;
    benchmark_return: number;
    excess_return: number;
    disclaimer: string;
  };
  artifacts: {
    data_quality: string;
    model: string;
    latest_predictions: string;
    historical_predictions: string;
    backtest: string;
    summary: string;
    pipeline_run: string;
  };
  disclaimer: string;
}

export interface Prediction {
  rank: number;
  symbol: string;
  date: string;
  model_version: string;
  score: number;
  return_1d: number | null;
  momentum_5d: number | null;
  volume_change_1d: number | null;
}

export interface LatestPredictions {
  count: number;
  predictions: Prediction[];
  disclaimer: string;
}

export interface BacktestPoint {
  date: string;
  portfolio_value: number;
  benchmark_value: number;
  excess_value: number;
}

export interface LatestBacktest {
  backtest_id: string;
  model_version: string;
  top_n: number;
  trade_count: number;
  start_date: string;
  end_date: string;
  cumulative_return: number;
  benchmark_return: number;
  excess_return: number;
  equity_curve: BacktestPoint[];
  disclaimer: string;
}

export interface DataQualityIssue {
  code: string;
  severity: string;
  message: string;
  symbol: string | null;
  date: string | null;
}

export interface DataQuality {
  passed: boolean;
  row_count: number;
  symbol_count: number;
  start_date: string;
  end_date: string;
  issue_count: number;
  issues: DataQualityIssue[];
}

export interface StockSummary {
  symbol: string;
  price_row_count: number;
  prediction_row_count: number;
  start_date: string | null;
  end_date: string | null;
  disclaimer: string;
}

export interface StockPrice {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  benchmark_close: number;
}

export interface StockPrices {
  symbol: string;
  count: number;
  prices: StockPrice[];
}

export interface StockFeature {
  date: string;
  close: number;
  return_1d: number | null;
  momentum_5d: number | null;
  ma_5: number | null;
  volume_change_1d: number | null;
}

export interface StockFeatures {
  symbol: string;
  count: number;
  features: StockFeature[];
}

export interface StockPrediction {
  date: string;
  model_version: string;
  score: number;
  rank: number;
  return_1d: number | null;
  momentum_5d: number | null;
  volume_change_1d: number | null;
}

export interface StockPredictions {
  symbol: string;
  count: number;
  predictions: StockPrediction[];
  disclaimer: string;
}

export interface SettingsArtifact {
  name: string;
  path: string;
  exists: boolean;
}

export interface LocalSettings {
  service: {
    name: string;
    mode: string;
    disclaimer: string;
  };
  paths: {
    data_dir: string;
    duckdb_path: string;
  };
  api_keys: {
    deepseek_configured: boolean;
    openai_configured: boolean;
  };
  artifacts: SettingsArtifact[];
}
