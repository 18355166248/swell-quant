import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

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
} from "./researchPages";
import type {
  AkshareUniverseStatus,
  BacktestSummary,
  DataStatus,
  LatestBacktest,
  LocalSettings,
  Prediction,
  ProjectProgress,
  ResearchCandidates,
  ResearchStatus,
} from "../types/api";

describe("research pages module", () => {
  it("exports every top-level research dashboard page", () => {
    expect(DashboardPage).toBeTypeOf("function");
    expect(AcceptancePage).toBeTypeOf("function");
    expect(TasksPage).toBeTypeOf("function");
    expect(DataPage).toBeTypeOf("function");
    expect(ModelsPage).toBeTypeOf("function");
    expect(PredictionsPage).toBeTypeOf("function");
    expect(BacktestsPage).toBeTypeOf("function");
    expect(FundsPage).toBeTypeOf("function");
    expect(StocksPage).toBeTypeOf("function");
    expect(ReportsPage).toBeTypeOf("function");
    expect(SettingsPage).toBeTypeOf("function");
  });

  it("renders research disclaimer and stable prediction table headers", () => {
    const predictions: Prediction[] = [
      {
        rank: 1,
        symbol: "000300.SH",
        date: "2024-01-08",
        model_version: "baseline-rule-v1",
        score: 0.42,
        return_1d: 0.01,
        momentum_5d: 0.03,
        volume_change_1d: 0.02,
      },
      {
        rank: 2,
        symbol: "000905.SH",
        date: "2024-01-08",
        model_version: "baseline-rule-v1",
        score: 0.12,
        return_1d: 0.096,
        momentum_5d: -0.01,
        volume_change_1d: 2.4,
      },
    ];
    const candidates: ResearchCandidates["candidates"] = [
      {
        rank: 1,
        symbol: "000300.SH",
        symbol_name: "沪深300样例",
        date: "2024-01-08",
        model_version: "baseline-rule-v1",
        score: 0.42,
        confidence: 1,
        confidence_level: "high",
        factors: [
          { code: "momentum_5d", name: "5日动量", value: 0.03, direction: "up" },
        ],
        risk_hints: [],
        history: {
          sample_count: 2,
          outperform_count: 1,
          outperform_rate: 0.5,
          average_future_5d_return: 0.015,
          best_future_5d_return: 0.05,
          worst_future_5d_return: -0.02,
          latest_signal_date: "2024-01-20",
          note: "历史回看仅统计已成熟标签，不代表未来表现",
        },
        research_action: {
          status: "focus",
          label: "可关注",
          reasons: ["模型分数处于当日高相对位置", "已有成熟历史样本可供回看"],
          blockers: [],
        },
        research_notes: [
          "模型分数在当日候选池中处于高相对位置",
          "主要正向因子：5日动量",
          "未触发启发式风险提示，仍需人工复核数据质量和交易约束",
        ],
      },
      {
        rank: 2,
        symbol: "000905.SH",
        symbol_name: "中证500样例",
        date: "2024-01-08",
        model_version: "baseline-rule-v1",
        score: 0.12,
        confidence: 0,
        confidence_level: "low",
        factors: [
          { code: "volume_change_1d", name: "成交量变化", value: 2.4, direction: "up" },
        ],
        risk_hints: [
          { code: "limit_move", label: "接近涨跌停幅度" },
          { code: "volume_spike", label: "成交量异动" },
        ],
        history: {
          sample_count: 0,
          outperform_count: 0,
          outperform_rate: null,
          average_future_5d_return: null,
          best_future_5d_return: null,
          worst_future_5d_return: null,
          latest_signal_date: null,
          note: "历史回看仅统计已成熟标签，不代表未来表现",
        },
        research_action: {
          status: "defer",
          label: "暂缓观察",
          reasons: ["模型分数处于当日低相对位置"],
          blockers: ["触发风险提示：成交量异动"],
        },
        research_notes: [
          "模型分数在当日候选池中处于低相对位置",
          "已触发风险提示，需先复核交易约束和数据质量",
        ],
      },
    ];

    const html = renderToStaticMarkup(
      <PredictionsPage
        predictions={predictions}
        candidates={candidates}
        filters={{ date: "", modelVersion: "", topN: 10 }}
        dateOptions={["2024-01-08"]}
        modelOptions={["baseline-rule-v1"]}
        onFiltersChange={() => undefined}
      />,
    );

    expect(html).toContain("预测分数仅用于研究，不构成投资建议");
    expect(html).toContain("当前输出不是投资建议");
    expect(html).toContain("不输出买入、卖出、持仓比例、目标价或保证收益");
    expect(html).toContain("真实数据稳定、样本外验证、回测复核和人工确认交易约束");
    expect(html).toContain("排名");
    expect(html).toContain("代码");
    expect(html).toContain("预测分数");
    expect(html).toContain("成交量变化");
    expect(html).toContain("研究参考清单");
    expect(html).toContain("研究候选解释");
    expect(html).toContain("为什么进入该分层");
    expect(html).toContain("复核清单");
    expect(html).toContain("核对数据新鲜度、停牌和涨跌停约束");
    expect(html).toContain("复核候选信号是否来自样本外日期");
    expect(html).toContain("因子依据");
    expect(html).toContain("风险提示");
    expect(html).toContain("候选标的");
    expect(html).toContain("沪深300样例");
    expect(html).toContain("中证500样例");
    expect(html).toContain("相对置信度");
    expect(html).toContain("研究动作");
    expect(html).toContain("可关注");
    expect(html).toContain("暂缓观察");
    expect(html).toContain("模型分数处于当日高相对位置");
    expect(html).toContain("清单由后端研究候选 API 生成，仅用于研究，不构成投资建议");
    expect(html).toContain("研究备注");
    expect(html).toContain("主要正向因子：5日动量");
    expect(html).toContain("历史回看");
    expect(html).toContain("历史样本 2");
    expect(html).toContain("跑赢率 50.00%");
    expect(html).toContain("均值 1.50%");
    expect(html).toContain("暂无成熟样本");
    expect(html).toContain("启发式风险");
    expect(html).toContain("接近涨跌停幅度");
    expect(html).toContain("成交量异动");
  });

  it("renders strategy experiment comparison on the backtests page", () => {
    const summary: BacktestSummary = {
      backtest_id: "sample-topn-baseline",
      model_version: "baseline-rule-v1",
      top_n: 2,
      fee_rate: 0.0003,
      slippage_rate: 0.0005,
      execution_price: "next_day_open",
      holding_period: "5d",
      rebalance_rule: "daily_top_n",
      trade_count: 4,
      rejected_trade_count: 1,
      start_date: "2024-01-02",
      end_date: "2024-01-31",
      cumulative_return: 0.08,
      annualized_return: 0.18,
      benchmark_return: 0.03,
      excess_return: 0.05,
      max_drawdown: -0.04,
      sharpe_ratio: 1.2,
      win_rate: 0.6,
      turnover_rate: 0.4,
      disclaimer: "仅用于研究，不构成投资建议",
    };
    const detail: LatestBacktest = {
      ...summary,
      equity_curve: [
        {
          date: "2024-01-03",
          signal_date: "2024-01-02",
          portfolio_return: 0.01,
          benchmark_return: 0.005,
          portfolio_value: 1.01,
          benchmark_value: 1.005,
          excess_value: 0.005,
          relative_return: 0.0049,
          portfolio_drawdown: 0,
          benchmark_drawdown: 0,
        },
      ],
      rejected_trades: [
        {
          symbol: "000001.SZ",
          rank: 1,
          signal_date: "2024-01-02",
          trade_date: "2024-01-03",
          reason: "limit_up_buy_blocked",
        },
      ],
    };

    const html = renderToStaticMarkup(
      <BacktestsPage
        backtests={[summary]}
        backtest={detail}
        selectedBacktestId="sample-topn-baseline"
        onSelectBacktest={() => undefined}
      />,
    );

    expect(html).toContain("策略实验对比");
    expect(html).toContain("不同回测配置的历史结果");
    expect(html).toContain("不代表未来收益");
    expect(html).toContain("累计");
    expect(html).toContain("超额");
    expect(html).toContain("换手");
    expect(html).toContain("无法成交明细");
    expect(html).toContain("涨停买入受限");
  });

  it("renders project stage progress on the dashboard", () => {
    const progress: ProjectProgress = {
      status: "in_progress",
      completed_stage_count: 6,
      partial_stage_count: 1,
      stage_count: 8,
      completion_ratio: 0.75,
      current_stage: {
        id: "stage_6",
        name: "阶段 6：AI 报告与 Agent 集成",
        goal: "结构化研究报告和可选 AI 报告",
        status: "partial",
        completed_count: 2,
        required_count: 4,
        evidence: [],
      },
      next_actions: ["补齐 AI 报告产物"],
      stages: [
        {
          id: "stage_0",
          name: "阶段 0：项目初始化",
          goal: "仓库、目录、配置和基础文档",
          status: "complete",
          completed_count: 1,
          required_count: 1,
          evidence: [],
        },
        {
          id: "stage_6",
          name: "阶段 6：AI 报告与 Agent 集成",
          goal: "结构化研究报告和可选 AI 报告",
          status: "partial",
          completed_count: 2,
          required_count: 4,
          evidence: [],
        },
      ],
      disclaimer: "仅用于研究，不构成投资建议",
    };

    const html = renderToStaticMarkup(
      <DashboardPage
        models={[]}
        predictions={[]}
        progress={progress}
      />,
    );

    expect(html).toContain("阶段完成度");
    expect(html).toContain("6/8");
    expect(html).toContain("阶段 6：AI 报告与 Agent 集成");
    expect(html).toContain("阶段进度");
    expect(html).toContain("补齐 AI 报告产物");
  });

  it("renders empty states for missing acceptance artifacts", () => {
    const html = renderToStaticMarkup(
      <AcceptancePage
        isRunning={false}
        onRunPipeline={() => undefined}
      />,
    );

    expect(html).toContain("暂无验收结果");
    expect(html).toContain("暂无产物状态");
    expect(html).toContain("仅用于研究，不构成投资建议");
  });

  it("renders AKShare collection failures on the data page", () => {
    const dataStatus: DataStatus = {
      data_source_status: "warning",
      data_source_passed: true,
      data_source_warning_count: 2,
      data_source_warnings: [
        "1 symbols failed during collection",
        "AKSHARE_MAX_SYMBOLS trial cap is active: 2",
      ],
      data_source_failed_count: 0,
      data_source_failures: [],
      data_source: "akshare",
      market: "A_SHARE_DAILY",
      universe: "akshare_csi800",
      universe_mode: "csi800",
      universe_name: "AKShare 沪深 300 + 中证 500 股票池",
      symbols: ["000001.SZ"],
      selected_symbol_count: 2,
      resolved_symbol_count: 800,
      max_symbols: 2,
      succeeded_symbols: ["000001.SZ"],
      succeeded_symbol_count: 1,
      failed_symbols: [{ symbol: "600000.SH", reason: "temporary upstream error" }],
      failed_symbol_count: 1,
      success_rate: 0.5,
      quality_score: 50,
      quality_level: "poor",
      source_attempts: [],
      target_universe: "沪深 300 + 中证 500",
      target_universe_size: 800,
      benchmark: "sh000906",
      benchmark_name: "中证 800",
      benchmark_fallback: "CSI300",
      benchmark_same_source: true,
      benchmark_note: "同源说明",
      adjustment: "forward_adjusted_daily",
      update_mode: "manual_trigger",
      configured_start_date: "20240102",
      configured_end_date: "20240131",
      source_updated_at: "2024-01-31T00:00:00Z",
      row_count: 10,
      symbol_count: 1,
      start_date: "2024-01-02",
      end_date: "2024-01-31",
      freshness: {
        status: "stale",
        label: "数据过期",
        as_of_date: "2024-01-31",
        today: "2026-07-09",
        lag_days: 890,
        message: "最新数据到 2024-01-31，距今天 890 天。",
      },
      quality_passed: true,
      issue_count: 0,
      disclaimer: "仅用于研究，不构成投资建议",
    };

    const html = renderToStaticMarkup(
      <DataPage
        dataStatus={dataStatus}
        artifacts={{
          status: "missing",
          missing: ["duckdb"],
          optional_missing: ["fund_trial"],
          disclaimer: "仅用于研究，不构成投资建议",
          artifacts: [],
        }}
        akshareTrial={{
          status: "dry_run",
          passed: true,
          trial_kind: "dry_run",
          real_data_verified: false,
        }}
        fundTrial={{
          status: "missing",
          passed: false,
          real_data_verified: false,
        }}
      />,
    );

    expect(html).toContain("数据源健康中心");
    expect(html).toContain("A 股行情数据");
    expect(html).toContain("股票真实试跑");
    expect(html).toContain("基金真实试跑");
    expect(html).toContain("关键产物");
    expect(html).toContain("make fund-trial");
    expect(html).toContain("采集摘要");
    expect(html).toContain("采集状态：warning");
    expect(html).toContain("采集成功率");
    expect(html).toContain("质量等级");
    expect(html).toContain("poor");
    expect(html).toContain("采集提示");
    expect(html).toContain("AKSHARE_MAX_SYMBOLS trial cap is active: 2");
    expect(html).toContain("失败标的");
    expect(html).toContain("600000.SH");
    expect(html).toContain("temporary upstream error");
  });

  it("renders latest stock and fund trial summaries on the tasks page", () => {
    const html = renderToStaticMarkup(
      <TasksPage
        tasks={[]}
        isRunning={false}
        onRunTask={() => undefined}
        akshareTrial={{
          status: "dry_run",
          passed: true,
          trial_kind: "dry_run",
          real_data_verified: false,
          started_at: "2026-07-03T00:00:00+00:00",
          ended_at: "2026-07-03T00:00:01+00:00",
          last_passed: {
            status: "passed",
            passed: true,
            trial_kind: "real_data",
            real_data_verified: true,
            ended_at: "2026-07-02T00:00:01+00:00",
          },
          duration_seconds: 1,
          artifact_path: "data/reports/akshare_trial_run.json",
          env: {
            AKSHARE_UNIVERSE_MODE: "csi800",
            AKSHARE_MAX_SYMBOLS: "20",
            AKSHARE_START_DATE: "20240102",
            AKSHARE_END_DATE: "20240131",
          },
          steps: [{ name: "config", status: "planned", command: ["python"] }],
          disclaimer: "仅用于研究，不构成投资建议",
        }}
        fundTrial={{
          status: "failed",
          passed: false,
          trial_kind: "real_data",
          real_data_verified: false,
          started_at: "2026-07-08T00:00:00+00:00",
          ended_at: "2026-07-08T00:00:01+00:00",
          duration_seconds: 1,
          artifact_path: "data/reports/fund_trial_run.json",
          env: {
            FUND_SYMBOLS: "510300,159915",
            FUND_START_DATE: "20250101",
            FUND_END_DATE: "20260708",
          },
          steps: [
            {
              name: "fund_data",
              status: "failed",
              error: "network unavailable",
              succeeded_count: 0,
              failed_count: 2,
            },
          ],
          disclaimer: "仅用于研究，不构成投资建议",
        }}
      />,
    );

    expect(html).toContain("最近股票真实试跑");
    expect(html).toContain("最近基金真实试跑");
    expect(html).toContain("股票试跑预演");
    expect(html).toContain("股票真实试跑");
    expect(html).toContain("基金试跑预演");
    expect(html).toContain("基金真实试跑");
    expect(html).toContain("make akshare-trial");
    expect(html).toContain("make akshare-trial-dry-run");
    expect(html).toContain("make fund-trial");
    expect(html).toContain("make fund-trial-dry-run");
    expect(html).toContain("dry_run");
    expect(html).toContain("真实数据验证");
    expect(html).toContain("未验证，仅预演");
    expect(html).toContain("最近真实通过");
    expect(html).toContain("2026-07-02T00:00:01+00:00");
    expect(html).toContain("csi800");
    expect(html).toContain("data/reports/akshare_trial_run.json");
    expect(html).toContain("config");
    expect(html).toContain("510300,159915");
    expect(html).toContain("data/reports/fund_trial_run.json");
    expect(html).toContain("network unavailable");
  });

  it("renders fund candidates and fund metrics", () => {
    const html = renderToStaticMarkup(
      <FundsPage
        profile="balanced"
        onProfileChange={() => undefined}
        selectedFundCode="510300"
        onFundSelect={() => undefined}
        disclaimer="仅用于研究，不构成投资建议"
        source={{
          source_kind: "sample",
          source_label: "本地样例基金数据",
          metrics_path: "data/processed/sample_fund_metrics.csv",
          candidates_path: "data/processed/sample_fund_candidates_balanced.csv",
          nav_path: "data/raw/sample_fund_nav.csv",
          warning: "真实基金候选产物不完整，当前回退为样例数据。",
          fund_count: 1,
          latest_nav_date: "2024-12-31",
          freshness: {
            status: "stale",
            label: "数据过期",
            as_of_date: "2024-12-31",
            today: "2026-07-09",
            lag_days: 555,
            message: "最新数据到 2024-12-31，距今天 555 天。",
          },
        }}
        fundDetail={{
          fund_code: "510300",
          fund_name: "沪深300ETF样例",
          fund_type: "宽基指数",
          manager: "指数团队",
          inception_date: "2012-05-04",
          aum_billion: 620,
          management_fee: 0.005,
          custody_fee: 0.001,
          total_fee: 0.006,
          return_1m: 0.01,
          return_3m: 0.03,
          return_6m: 0.06,
          return_1y: 0.12,
          max_drawdown: -0.08,
          volatility: 0.16,
          downside_volatility: 0.1,
          age_years: 12,
        }}
        fundNav={{
          fund_code: "510300",
          count: 2,
          nav: [
            { date: "2024-12-30", nav: 1.01 },
            { date: "2024-12-31", nav: 1.02 },
          ],
          disclaimer: "仅用于研究，不构成投资建议",
        }}
        candidates={[
          {
            rank: 1,
            fund_code: "510300",
            fund_name: "沪深300ETF样例",
            fund_type: "宽基指数",
            profile: "balanced",
            score: 0.82,
            score_level: "high",
            factor_reasons: ["近1年收益 12.00%", "最大回撤 -8.00%"],
            risk_notes: ["净值波动偏高"],
            verification_status: "block",
            verification_label: "暂不适合决策",
            verification_checks: ["历史净值覆盖 12.0 年", "最大回撤 -8.00%"],
            verification_blockers: ["当前为样例基金数据，不能作为真实申购依据"],
          },
        ]}
        funds={[
          {
            fund_code: "510300",
            fund_name: "沪深300ETF样例",
            fund_type: "宽基指数",
            manager: "指数团队",
            inception_date: "2012-05-04",
            aum_billion: 620,
            management_fee: 0.005,
            custody_fee: 0.001,
            total_fee: 0.006,
            return_1m: 0.01,
            return_3m: 0.03,
            return_6m: 0.06,
            return_1y: 0.12,
            max_drawdown: -0.08,
            volatility: 0.16,
            downside_volatility: 0.1,
            age_years: 12,
          },
        ]}
      />,
    );

    expect(html).toContain("基金");
    expect(html).toContain("基金对比");
    expect(html).toContain("最多对比 5 只");
    expect(html).toContain("候选基金清单");
    expect(html).toContain("基金详情");
    expect(html).toContain("净值走势");
    expect(html).toContain("买前验证明细");
    expect(html).toContain("沪深300ETF样例");
    expect(html).toContain("净值波动偏高");
    expect(html).toContain("仅用于研究，不构成投资建议");
    expect(html).toContain("不给出申购、赎回、定投金额或仓位建议");
    expect(html).toContain("基金数据来源：本地样例基金数据");
    expect(html).toContain("真实基金候选产物不完整，当前回退为样例数据。");
    expect(html).toContain("最新净值日期");
    expect(html).toContain("数据过期");
    expect(html).toContain("距今天 555 天");
    expect(html).toContain("买前验证");
    expect(html).toContain("暂不适合决策");
    expect(html).toContain("当前为样例基金数据，不能作为真实申购依据");
  });

  it("renders daily research brief on the reports page", () => {
    const status: ResearchStatus = {
      acceptance: {
        status: "failed",
        passed: false,
        check_count: 2,
        failed_count: 1,
        checks: [],
        disclaimer: "仅用于研究，不构成投资建议",
      },
      artifact_status: { status: "complete", missing: [], artifacts: [] },
      pipeline: {
        status: "success",
        started_at: "2026-07-09T00:00:00Z",
        ended_at: "2026-07-09T00:00:01Z",
        duration_seconds: 1,
        step_count: 1,
      },
      data_quality: {
        passed: true,
        row_count: 10,
        symbol_count: 1,
        start_date: "2024-01-02",
        end_date: "2024-01-31",
        issue_count: 1,
      },
      data_source: null,
      model: {
        model_version: "baseline-rule-v1",
        model_type: "baseline",
        requested_model_type: "baseline",
        training_backend: "rule",
        dependency_status: "available",
        model_artifact_path: null,
        feature_importance: [],
        train_start: "2024-01-02",
        train_end: "2024-01-31",
        prediction_date: "2024-01-31",
        feature_names: [],
        label_gap_days: 5,
        evaluation_status: "ready",
        evaluation_train_start: "2024-01-02",
        evaluation_train_end: "2024-01-20",
        validation_start: "2024-01-21",
        validation_end: "2024-01-25",
        test_start: "2024-01-26",
        test_end: "2024-01-31",
        metrics: {},
      },
      training_samples: {
        status: "ready",
        row_count: 10,
        symbol_count: 1,
        split_counts: { train: 6, validation: 2, test: 2 },
        positive_count: 5,
        negative_count: 5,
        positive_rate: 0.5,
        start_date: "2024-01-02",
        end_date: "2024-01-31",
        missing_feature_counts: {},
      },
      predictions: { count: 1, top: [] },
      backtest: {
        backtest_id: "sample-topn-baseline",
        top_n: 2,
        trade_count: 2,
        fee_rate: 0.0003,
        slippage_rate: 0.0005,
        cumulative_return: 0.01,
        annualized_return: 0.08,
        benchmark_return: 0.005,
        excess_return: 0.005,
        max_drawdown: -0.01,
        sharpe_ratio: 1,
        win_rate: 0.5,
        turnover_rate: 0.2,
        start_date: "2024-01-02",
        end_date: "2024-01-31",
        disclaimer: "仅用于研究，不构成投资建议",
      },
      artifacts: {
        data_quality: "data/processed/data_quality.json",
        model: "data/models/latest_model.json",
        training_samples: "data/processed/training_samples.csv",
        latest_predictions: "data/processed/latest_predictions.csv",
        historical_predictions: "data/processed/historical_predictions.csv",
        duckdb: "data/duckdb/swell_quant.duckdb",
        backtest: "data/reports/sample_backtest.json",
        summary: "data/reports/sample_research_summary.md",
        pipeline_run: "data/reports/pipeline_run.json",
      },
      disclaimer: "仅用于研究，不构成投资建议",
    };
    const dataStatus: DataStatus = {
      data_source_status: "passed",
      data_source_passed: true,
      data_source_warning_count: 0,
      data_source_warnings: [],
      data_source_failed_count: 0,
      data_source_failures: [],
      data_source: "sample",
      market: "A_SHARE_DAILY",
      universe: "sample",
      universe_mode: "sample",
      universe_name: "样例",
      symbols: ["000300.SH"],
      selected_symbol_count: 1,
      resolved_symbol_count: 1,
      max_symbols: null,
      succeeded_symbols: ["000300.SH"],
      succeeded_symbol_count: 1,
      failed_symbols: [],
      failed_symbol_count: 0,
      target_universe: "沪深 300 + 中证 500",
      target_universe_size: 800,
      benchmark: "sh000906",
      benchmark_name: "中证 800",
      benchmark_fallback: "CSI300",
      benchmark_same_source: true,
      benchmark_note: "同源说明",
      adjustment: "forward_adjusted_daily",
      update_mode: "manual_trigger",
      configured_start_date: "20240102",
      configured_end_date: "20240131",
      source_updated_at: "2024-01-31T00:00:00Z",
      row_count: 10,
      symbol_count: 1,
      start_date: "2024-01-02",
      end_date: "2024-01-31",
      freshness: {
        status: "stale",
        label: "数据过期",
        as_of_date: "2024-01-31",
        today: "2026-07-09",
        lag_days: 890,
        message: "最新数据到 2024-01-31，距今天 890 天。",
      },
      quality_passed: true,
      issue_count: 1,
      disclaimer: "仅用于研究，不构成投资建议",
    };
    const html = renderToStaticMarkup(
      <ReportsPage
        reports={[]}
        selectedReportId="sample"
        onSelectReport={() => undefined}
        status={status}
        dataStatus={dataStatus}
        researchCandidates={[
          {
            rank: 1,
            symbol: "000300.SH",
            symbol_name: "沪深300样例",
            date: "2024-01-31",
            model_version: "baseline-rule-v1",
            score: 0.8,
            confidence: 1,
            confidence_level: "high",
            factors: [],
            risk_hints: [],
            history: {
              sample_count: 1,
              outperform_count: 1,
              outperform_rate: 1,
              average_future_5d_return: 0.01,
              best_future_5d_return: 0.01,
              worst_future_5d_return: 0.01,
              latest_signal_date: "2024-01-20",
              note: "历史回看",
            },
            research_action: {
              status: "focus",
              label: "可关注",
              reasons: ["模型分数处于当日高相对位置"],
              blockers: [],
            },
            research_notes: [],
          },
        ]}
        fundCandidates={[
          {
            rank: 1,
            fund_code: "510300",
            fund_name: "沪深300ETF样例",
            fund_type: "宽基指数",
            profile: "balanced",
            score: 0.8,
            score_level: "high",
            factor_reasons: [],
            risk_notes: [],
            verification_status: "block",
            verification_label: "暂不适合决策",
            verification_checks: [],
            verification_blockers: ["样例数据"],
          },
        ]}
        fundSource={{
          source_kind: "sample",
          source_label: "本地样例基金数据",
          metrics_path: "data/processed/sample_fund_metrics.csv",
          candidates_path: "data/processed/sample_fund_candidates_balanced.csv",
          nav_path: "data/raw/sample_fund_nav.csv",
          warning: "样例",
          fund_count: 1,
          latest_nav_date: "2024-12-31",
          freshness: {
            status: "stale",
            label: "数据过期",
            as_of_date: "2024-12-31",
            today: "2026-07-09",
            lag_days: 555,
            message: "最新数据到 2024-12-31，距今天 555 天。",
          },
        }}
        qualityIssues={[
          { code: "missing", severity: "warning", message: "缺失价格", symbol: "000300.SH", date: "2024-01-03" },
        ]}
        dailyBrief={{
          status: "partial",
          data: {
            freshness: dataStatus.freshness,
            data_source_status: "passed",
            quality_issue_count: 1,
          },
          acceptance: {
            status: "failed",
            passed: false,
            failed_count: 1,
          },
          stocks: {
            action_summary: { focus: 1, review: 0, defer: 0 },
            candidates: [
              {
                rank: 1,
                symbol: "000300.SH",
                symbol_name: "沪深300样例",
                date: "2024-01-31",
                model_version: "baseline-rule-v1",
                score: 0.8,
                confidence: 1,
                confidence_level: "high",
                factors: [],
                risk_hints: [],
                history: {
                  sample_count: 1,
                  outperform_count: 1,
                  outperform_rate: 1,
                  average_future_5d_return: 0.01,
                  best_future_5d_return: 0.01,
                  worst_future_5d_return: 0.01,
                  latest_signal_date: "2024-01-20",
                  note: "历史回看",
                },
                research_action: {
                  status: "focus",
                  label: "可关注",
                  reasons: ["模型分数处于当日高相对位置"],
                  blockers: [],
                },
                research_notes: [],
              },
            ],
          },
          funds: {
            source: {
              source_kind: "sample",
              source_label: "本地样例基金数据",
              metrics_path: "data/processed/sample_fund_metrics.csv",
              candidates_path: "data/processed/sample_fund_candidates_balanced.csv",
              nav_path: "data/raw/sample_fund_nav.csv",
              warning: "样例",
              fund_count: 1,
              latest_nav_date: "2024-12-31",
              freshness: {
                status: "stale",
                label: "数据过期",
                as_of_date: "2024-12-31",
                today: "2026-07-09",
                lag_days: 555,
                message: "最新数据到 2024-12-31，距今天 555 天。",
              },
            },
            candidate_count: 1,
            candidates: [
              {
                rank: 1,
                fund_code: "510300",
                fund_name: "沪深300ETF样例",
                fund_type: "宽基指数",
                profile: "balanced",
                score: 0.8,
                score_level: "high",
                factor_reasons: [],
                risk_notes: [],
                verification_status: "block",
                verification_label: "暂不适合决策",
                verification_checks: [],
                verification_blockers: ["样例数据"],
              },
            ],
          },
          artifacts: {
            status: "missing",
            missing: ["duckdb"],
            optional_missing: [],
          },
          review_items: ["API 简报复核项", "基金页当前使用样例数据"],
          next_actions: [
            {
              id: "refresh_data",
              label: "刷新数据并重跑研究链路",
              description: "行情数据过期，先刷新数据产物。",
              task: "data_update",
            },
            {
              id: "fund_trial",
              label: "运行基金真实数据试跑",
              description: "基金候选仍是样例数据，真实研究前先执行 make fund-trial。",
              task: "fund_trial",
            },
          ],
          access_issues: [{ name: "fund_candidates", message: "missing fund candidates" }],
          disclaimer: "仅用于研究，不构成投资建议",
        }}
      />,
    );

    expect(html).toContain("每日研究简报");
    expect(html).toContain("不输出买入、卖出、仓位或目标价");
    expect(html).toContain("股票研究候选");
    expect(html).toContain("基金研究候选");
    expect(html).toContain("今日复核重点");
    expect(html).toContain("沪深300样例");
    expect(html).toContain("沪深300ETF样例");
    expect(html).toContain("partial");
    expect(html).toContain("简报部分产物缺失");
    expect(html).toContain("API 简报复核项");
    expect(html).toContain("下一步动作");
    expect(html).toContain("刷新数据并重跑研究链路");
    expect(html).toContain("执行");
    expect(html).toContain("基金页当前使用样例数据");
  });

  it("shows API key configuration status without rendering secret values", () => {
    const settings = {
      service: {
        name: "swell-quant",
        mode: "local",
        disclaimer: "仅用于研究，不构成投资建议",
      },
      paths: {
        data_dir: "F:/FrontEnd/swell-quant/data",
        duckdb_path: "F:/FrontEnd/swell-quant/data/processed/swell_quant.duckdb",
      },
      runtime: {
        data_source: "sample",
        model_type: "baseline",
        llm_provider: "deepseek",
      },
      akshare: {
        universe_mode: "manual",
        symbols: ["000300.SH"],
        start_date: "2024-01-01",
        end_date: "2024-01-31",
        benchmark_symbol: "000300.SH",
        max_symbols: 20,
      },
      llm: {
        provider: "deepseek",
        deepseek_model: "deepseek-chat",
        deepseek_base_url: "https://api.deepseek.com",
      },
      api_keys: {
        deepseek_configured: true,
        openai_configured: false,
      },
      preflight: {
        status: "passed",
        passed: true,
        check_count: 1,
        failed_count: 0,
        warning_count: 0,
        checks: [
          {
            key: "api_key",
            name: "API key 配置",
            status: "passed",
            message: "已配置",
          },
        ],
      },
      artifacts: [],
      secret_probe: "sk-secret-should-not-render",
    } satisfies LocalSettings & { secret_probe: string };
    const akshareUniverse: AkshareUniverseStatus = {
      status: "passed",
      passed: true,
      data_source: "sample",
      universe_mode: "manual",
      symbol_count: 1,
      minimum_expected_count: 1,
      symbols_sample: ["000300.SH"],
      disclaimer: "仅用于研究，不构成投资建议",
    };

    const html = renderToStaticMarkup(
      <SettingsPage settings={settings} akshareUniverse={akshareUniverse} />,
    );

    expect(html).toContain("DeepSeek Key");
    expect(html).toContain("已配置");
    expect(html).toContain("股票池解析门禁");
    expect(html).toContain("000300.SH");
    expect(html).toContain("AKShare 试跑上限");
    expect(html).toContain("20");
    expect(html).not.toContain("sk-secret-should-not-render");
  });
});
