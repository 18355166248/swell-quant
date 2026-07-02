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
  requested_task?: string;
  execution_mode?: string;
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

export interface AcceptanceCheck {
  key: string;
  name: string;
  status: "passed" | "failed";
  message: string;
}

export interface AcceptanceStatus {
  status: "passed" | "failed" | "missing";
  passed: boolean;
  check_count: number;
  failed_count: number;
  checks: AcceptanceCheck[];
  disclaimer?: string;
}

export interface ArtifactStatus {
  status: "complete" | "missing";
  missing: string[];
  disclaimer?: string;
  artifacts: Array<{
    name: string;
    path: string;
    exists: boolean;
    size_bytes: number | null;
    updated_at: string | null;
  }>;
}

export interface ResearchStatus {
  acceptance: AcceptanceStatus;
  artifact_status: ArtifactStatus;
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
    label_gap_days: number;
    evaluation_status: string;
    evaluation_train_start: string | null;
    evaluation_train_end: string | null;
    validation_start: string | null;
    validation_end: string | null;
    test_start: string | null;
    test_end: string | null;
    metrics: Record<string, number | string | null>;
  };
  predictions: {
    count: number;
    top: Prediction[];
  };
  backtest: {
    backtest_id: string;
    top_n: number;
    trade_count: number;
    fee_rate: number;
    slippage_rate: number;
    start_date: string;
    end_date: string;
    cumulative_return: number;
    annualized_return: number;
    benchmark_return: number;
    excess_return: number;
    max_drawdown: number;
    sharpe_ratio: number | null;
    win_rate: number;
    turnover_rate: number;
    disclaimer: string;
  };
  artifacts: {
    data_quality: string;
    model: string;
    latest_predictions: string;
    historical_predictions: string;
    duckdb: string;
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
  available_dates?: string[];
  model_versions?: string[];
  filters?: {
    date: string | null;
    model_version: string | null;
    top_n: number | null;
  };
}

export interface BacktestPoint {
  date: string;
  signal_date: string;
  portfolio_return: number;
  benchmark_return: number;
  portfolio_value: number;
  benchmark_value: number;
  excess_value: number;
  portfolio_drawdown: number;
  benchmark_drawdown: number;
}

export interface RejectedTrade {
  symbol: string;
  rank: number;
  signal_date: string;
  trade_date: string;
  reason: string;
}

export interface LatestBacktest {
  backtest_id: string;
  model_version: string;
  top_n: number;
  fee_rate: number;
  slippage_rate: number;
  execution_price: string;
  holding_period: string;
  rebalance_rule: string;
  trade_count: number;
  rejected_trade_count: number;
  start_date: string;
  end_date: string;
  cumulative_return: number;
  annualized_return: number;
  benchmark_return: number;
  excess_return: number;
  max_drawdown: number;
  sharpe_ratio: number | null;
  win_rate: number;
  turnover_rate: number;
  equity_curve: BacktestPoint[];
  rejected_trades: RejectedTrade[];
  disclaimer: string;
}

export interface BacktestSummary {
  backtest_id: string;
  model_version: string;
  top_n: number;
  fee_rate: number;
  slippage_rate: number;
  execution_price: string;
  holding_period: string;
  rebalance_rule: string;
  trade_count: number;
  rejected_trade_count: number;
  start_date: string;
  end_date: string;
  cumulative_return: number;
  annualized_return: number;
  benchmark_return: number;
  excess_return: number;
  max_drawdown: number;
  sharpe_ratio: number | null;
  win_rate: number;
  turnover_rate: number;
  disclaimer: string;
}

export interface BacktestList {
  count: number;
  backtests: BacktestSummary[];
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

export interface DataStatus {
  market: string;
  universe: string;
  universe_name: string;
  target_universe: string;
  target_universe_size: number;
  benchmark: string;
  benchmark_name: string;
  benchmark_fallback: string;
  benchmark_same_source: boolean;
  benchmark_note: string;
  adjustment: string;
  update_mode: string;
  row_count: number;
  symbol_count: number;
  start_date: string;
  end_date: string;
  quality_passed: boolean;
  issue_count: number;
  disclaimer: string;
}

export type DuckDBStorageHealth =
  | "healthy"
  | "incomplete"
  | "missing"
  | "inconsistent"
  | "schema_mismatch";

export interface DuckDBTableStatus {
  name: string;
  exists: boolean;
  row_count: number | null;
  source_path: string | null;
  source_exists: boolean | null;
  source_row_count: number | null;
  row_count_matches: boolean | null;
  expected_columns: string[];
  actual_columns: string[] | null;
  missing_columns: string[];
  extra_columns: string[];
  schema_matches: boolean | null;
}

export interface DuckDBStorageStatus {
  exists: boolean;
  path: string;
  status: DuckDBStorageHealth;
  file_size_bytes?: number;
  tables: DuckDBTableStatus[];
  missing_tables: string[];
  inconsistent_tables: string[];
  schema_mismatch_tables: string[];
  total_rows: number;
  disclaimer: string;
}

export interface FeatureSample {
  symbol: string;
  date: string;
  close: number;
  return_1d: number | null;
  momentum_5d: number | null;
  ma_5: number | null;
  volume_change_1d: number | null;
}

export interface FeatureSummary {
  row_count: number;
  symbol_count: number;
  start_date: string | null;
  end_date: string | null;
  feature_names: string[];
  non_null_counts: Record<string, number>;
  latest_samples: FeatureSample[];
  disclaimer: string;
}

export interface LabelSample {
  symbol: string;
  date: string;
  future_5d_return: number | null;
  benchmark_5d_return: number | null;
  outperform_benchmark_5d: number | null;
}

export interface LabelSummary {
  row_count: number;
  symbol_count: number;
  start_date: string | null;
  end_date: string | null;
  label_names: string[];
  labeled_row_count: number;
  unlabeled_row_count: number;
  positive_count: number;
  negative_count: number;
  horizon_days: number;
  label_window: string;
  entry_price: string;
  exit_price: string;
  latest_samples: LabelSample[];
  disclaimer: string;
}

export interface LatestModel {
  model_version: string;
  model_type: string;
  feature_names: string[];
  feature_count: number;
  train_start: string;
  train_end: string;
  prediction_date: string;
  row_count: number;
  label_gap_days: number;
  evaluation_status: string;
  evaluation_train_start: string | null;
  evaluation_train_end: string | null;
  validation_start: string | null;
  validation_end: string | null;
  test_start: string | null;
  test_end: string | null;
  metrics: Record<string, number | string | null>;
  path?: string;
  updated_at?: string;
  disclaimer: string;
}

export interface ModelSummary {
  model_version: string;
  model_type: string;
  feature_count: number;
  train_start: string;
  train_end: string;
  prediction_date: string;
  row_count: number;
  evaluation_status: string;
  test_start: string | null;
  test_end: string | null;
  path: string;
  updated_at: string;
  disclaimer: string;
}

export interface ModelList {
  count: number;
  models: ModelSummary[];
  disclaimer: string;
}

export interface StockSummary {
  symbol: string;
  price_row_count: number;
  prediction_row_count: number;
  start_date: string | null;
  end_date: string | null;
  disclaimer: string;
}

export interface StockList {
  count: number;
  stocks: StockSummary[];
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
  size_bytes: number | null;
  updated_at: string | null;
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

export interface ReportSummary {
  report_id: string;
  title: string;
  path: string;
  generated_at: string;
  model_version: string | null;
  backtest_id: string | null;
  summary: string;
  disclaimer: string;
}

export interface ReportList {
  count: number;
  reports: ReportSummary[];
}

export interface ReportDetail extends ReportSummary {
  body: string;
}
