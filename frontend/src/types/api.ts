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

export interface AkshareTrialStep {
  name: string;
  command?: string[];
  status: "planned" | "passed" | "failed";
  returncode?: number;
  stdout?: string;
  stderr?: string;
}

export interface AkshareTrialRun {
  status: "passed" | "failed" | "dry_run" | "missing";
  passed?: boolean;
  trial_kind?: "real_data" | "dry_run";
  real_data_verified?: boolean;
  started_at?: string;
  ended_at?: string;
  duration_seconds?: number;
  artifact_path?: string;
  path?: string;
  message?: string;
  env?: Record<string, string>;
  last_passed?: {
    status: string;
    passed: boolean;
    trial_kind?: "real_data" | "dry_run";
    real_data_verified: boolean;
    started_at?: string;
    ended_at?: string;
    duration_seconds?: number;
  } | null;
  steps?: AkshareTrialStep[];
  disclaimer?: string;
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

export interface DataSourceStatus {
  status: "passed" | "warning" | "failed" | "missing";
  passed: boolean;
  path: string | null;
  data_source?: string;
  market?: string;
  universe_mode?: string;
  universe_name?: string;
  benchmark?: string;
  benchmark_name?: string;
  selected_symbol_count: number;
  resolved_symbol_count?: number;
  succeeded_symbol_count: number;
  failed_symbol_count: number;
  success_rate?: number;
  quality_score?: number;
  quality_level?: "good" | "usable" | "poor";
  source_attempts?: Array<{
    symbol: string;
    source: string;
    status: string;
    attempts: string | number;
    error?: string;
  }>;
  max_symbols?: number | null;
  failed_symbols: Array<{
    symbol: string;
    reason: string;
  }>;
  warning_count: number;
  warnings: string[];
  failed_count: number;
  failures: string[];
  updated_at?: string | null;
  disclaimer: string;
}

export interface ArtifactStatus {
  status: "complete" | "missing";
  missing: string[];
  optional_missing?: string[];
  disclaimer?: string;
  artifacts: Array<{
    name: string;
    path: string;
    exists: boolean;
    required?: boolean;
    size_bytes: number | null;
    updated_at: string | null;
  }>;
}

export type ProjectProgressStageStatus = "complete" | "partial" | "pending";

export interface ProjectProgressEvidence {
  key: string;
  name: string;
  status: "passed" | "missing" | "failed";
  message: string;
}

export interface ProjectProgressStage {
  id: string;
  name: string;
  goal: string;
  status: ProjectProgressStageStatus;
  completed_count: number;
  required_count: number;
  evidence: ProjectProgressEvidence[];
}

export interface ProjectProgress {
  status: "complete" | "in_progress";
  completed_stage_count: number;
  partial_stage_count: number;
  stage_count: number;
  completion_ratio: number;
  current_stage: ProjectProgressStage;
  next_actions: string[];
  akshare_trial?: Pick<AkshareTrialRun, "status" | "trial_kind" | "real_data_verified" | "path">;
  stages: ProjectProgressStage[];
  disclaimer: string;
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
  data_source: DataSourceStatus | null;
  model: {
    model_version: string;
    model_type: string;
    requested_model_type: string;
    training_backend: string;
    dependency_status: string;
    model_artifact_path: string | null;
    feature_importance: ModelFeatureImportance[];
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
  training_samples: {
    status: "ready" | "incomplete" | "missing";
    row_count: number;
    symbol_count: number;
    start_date: string | null;
    end_date: string | null;
    split_counts: Record<string, number>;
    positive_count: number;
    negative_count: number;
    positive_rate: number | null;
    missing_feature_counts: Record<string, number>;
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
    training_samples: string;
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

export interface ResearchCandidateFactor {
  code: string;
  name: string;
  value: number;
  direction: "up" | "down";
}

export interface ResearchCandidateRiskHint {
  code: string;
  label: string;
}

export interface ResearchCandidateHistory {
  sample_count: number;
  outperform_count: number;
  outperform_rate: number | null;
  average_future_5d_return: number | null;
  best_future_5d_return: number | null;
  worst_future_5d_return: number | null;
  latest_signal_date: string | null;
  note: string;
}

export interface ResearchCandidateAction {
  status: "focus" | "review" | "defer";
  label: string;
  reasons: string[];
  blockers: string[];
}

export interface ResearchCandidate {
  rank: number;
  symbol: string;
  symbol_name: string;
  date: string;
  model_version: string;
  score: number;
  confidence: number;
  confidence_level: "high" | "medium" | "low";
  factors: ResearchCandidateFactor[];
  risk_hints: ResearchCandidateRiskHint[];
  history: ResearchCandidateHistory;
  research_action: ResearchCandidateAction;
  research_notes: string[];
}

export interface ResearchCandidates {
  count: number;
  candidates: ResearchCandidate[];
  readiness?: {
    status: "passed" | "failed" | "unknown";
    passed: boolean | null;
    failed_checks: AcceptanceCheck[];
    note: string;
  };
  filters?: {
    top_n: number;
  };
  disclaimer: string;
}

export interface BacktestPoint {
  date: string;
  signal_date: string;
  portfolio_return: number;
  benchmark_return: number;
  portfolio_value: number;
  benchmark_value: number;
  excess_value: number;
  relative_return: number;
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
  data_source_status: "passed" | "warning" | "failed" | "missing";
  data_source_passed: boolean;
  data_source_warning_count: number;
  data_source_warnings: string[];
  data_source_failed_count: number;
  data_source_failures: string[];
  data_source: string;
  market: string;
  universe: string;
  universe_mode: string;
  universe_name: string;
  symbols: string[];
  selected_symbol_count: number;
  resolved_symbol_count: number;
  max_symbols: number | null;
  succeeded_symbols: string[];
  succeeded_symbol_count: number;
  failed_symbols: Array<{
    symbol: string;
    reason: string;
  }>;
  failed_symbol_count: number;
  success_rate?: number;
  quality_score?: number;
  quality_level?: "good" | "usable" | "poor";
  source_attempts?: Array<{
    symbol: string;
    source: string;
    status: string;
    attempts: string | number;
    error?: string;
  }>;
  target_universe: string;
  target_universe_size: number;
  benchmark: string;
  benchmark_name: string;
  benchmark_fallback: string;
  benchmark_same_source: boolean;
  benchmark_note: string;
  adjustment: string;
  update_mode: string;
  configured_start_date: string | null;
  configured_end_date: string | null;
  source_updated_at: string | null;
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
  volatility_5d: number | null;
  rsi_6: number | null;
  macd_dif: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
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
  requested_model_type: string;
  training_backend: string;
  dependency_status: string;
  model_artifact_path: string | null;
  training_params: Record<string, number | string | boolean | null>;
  feature_importance: ModelFeatureImportance[];
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

export interface ModelFeatureImportance {
  feature_name: string;
  rank: number;
  importance: number;
  raw_importance: number;
  split_count?: number;
  importance_type: string;
}

export interface ModelSummary {
  model_version: string;
  model_type: string;
  feature_count: number;
  requested_model_type: string;
  training_backend: string;
  dependency_status: string;
  model_artifact_path?: string | null;
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

export interface TrainingSamplePreview {
  symbol: string;
  date: string;
  split: string;
  future_5d_return: number;
  benchmark_5d_return: number;
  outperform_benchmark_5d: number;
}

export interface TrainingSamplesSummary {
  row_count: number;
  symbol_count: number;
  start_date: string | null;
  end_date: string | null;
  feature_names: string[];
  split_counts: Record<string, number>;
  positive_count: number;
  negative_count: number;
  positive_rate: number | null;
  missing_feature_counts: Record<string, number>;
  latest_samples: TrainingSamplePreview[];
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
  volatility_5d: number | null;
  rsi_6: number | null;
  macd_dif: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
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

export interface FundSummary {
  fund_code: string;
  fund_name: string;
  fund_type: string;
  manager: string;
  inception_date: string;
  aum_billion: number;
  management_fee: number;
  custody_fee: number;
  total_fee: number;
  return_1m: number;
  return_3m: number;
  return_6m: number;
  return_1y: number;
  max_drawdown: number;
  volatility: number;
  downside_volatility: number;
  age_years: number;
  disclaimer?: string;
}

export interface FundList {
  count: number;
  funds: FundSummary[];
  disclaimer: string;
}

export interface FundNavPoint {
  date: string;
  nav: number;
}

export interface FundNav {
  fund_code: string;
  count: number;
  nav: FundNavPoint[];
  disclaimer: string;
}

export interface FundCandidate {
  rank: number;
  fund_code: string;
  fund_name: string;
  fund_type: string;
  profile: "conservative" | "balanced" | "aggressive";
  score: number;
  score_level: "high" | "medium" | "low";
  factor_reasons: string[];
  risk_notes: string[];
  verification_status: "ready" | "review" | "block";
  verification_label: string;
  verification_checks: string[];
  verification_blockers: string[];
}

export interface FundCandidates {
  profile: "conservative" | "balanced" | "aggressive";
  count: number;
  candidates: FundCandidate[];
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
  runtime: {
    data_source: string;
    model_type: string;
    llm_provider: string;
  };
  akshare: {
    universe_mode: string;
    symbols: string[];
    start_date: string;
    end_date: string;
    benchmark_symbol: string;
    max_symbols: number | null;
  };
  llm: {
    provider: string;
    deepseek_model: string;
    deepseek_base_url: string;
  };
  api_keys: {
    deepseek_configured: boolean;
    openai_configured: boolean;
  };
  preflight: {
    status: "passed" | "warning" | "failed";
    passed: boolean;
    check_count: number;
    failed_count: number;
    warning_count: number;
    checks: Array<{
      key: string;
      name: string;
      status: "passed" | "warning" | "failed";
      message: string;
    }>;
  };
  artifacts: SettingsArtifact[];
}

export interface AkshareUniverseStatus {
  status: "passed" | "failed";
  passed: boolean;
  data_source?: string;
  universe_mode?: string;
  symbol_count?: number;
  minimum_expected_count?: number;
  symbols_sample?: string[];
  error?: string;
  message?: string;
  disclaimer: string;
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
  payload_path: string | null;
  structured: {
    predictions?: unknown[];
    research_actions?: {
      summary?: Record<"focus" | "review" | "defer", number>;
      candidates?: Array<{
        rank: number;
        symbol: string;
        symbol_name?: string;
        confidence_level: "high" | "medium" | "low";
        research_action: ResearchCandidateAction;
      }>;
      disclaimer: string;
    };
    risk_notes?: string[];
    backtest?: {
      cumulative_return?: number;
      excess_return?: number;
      max_drawdown?: number;
    };
  } | null;
  ai_report: {
    status: "success" | "failed" | "skipped";
    provider: string;
    model: string | null;
    reason: string | null;
    content: string;
    disclaimer: string;
  } | null;
  body: string;
}
