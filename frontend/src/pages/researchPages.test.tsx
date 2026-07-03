import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import {
  AcceptancePage,
  BacktestsPage,
  DashboardPage,
  DataPage,
  ModelsPage,
  PredictionsPage,
  ReportsPage,
  SettingsPage,
  StocksPage,
  TasksPage,
} from "./researchPages";
import type {
  AkshareUniverseStatus,
  DataStatus,
  LocalSettings,
  Prediction,
  ProjectProgress,
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
    ];

    const html = renderToStaticMarkup(
      <PredictionsPage
        predictions={predictions}
        filters={{ date: "", modelVersion: "", topN: 10 }}
        dateOptions={["2024-01-08"]}
        modelOptions={["baseline-rule-v1"]}
        onFiltersChange={() => undefined}
      />,
    );

    expect(html).toContain("预测分数仅用于研究，不构成投资建议");
    expect(html).toContain("排名");
    expect(html).toContain("代码");
    expect(html).toContain("预测分数");
    expect(html).toContain("成交量变化");
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
      quality_passed: true,
      issue_count: 0,
      disclaimer: "仅用于研究，不构成投资建议",
    };

    const html = renderToStaticMarkup(<DataPage dataStatus={dataStatus} />);

    expect(html).toContain("采集摘要");
    expect(html).toContain("采集状态：warning");
    expect(html).toContain("采集提示");
    expect(html).toContain("AKSHARE_MAX_SYMBOLS trial cap is active: 2");
    expect(html).toContain("失败标的");
    expect(html).toContain("600000.SH");
    expect(html).toContain("temporary upstream error");
  });

  it("renders latest AKShare trial summary on the tasks page", () => {
    const html = renderToStaticMarkup(
      <TasksPage
        tasks={[]}
        isRunning={false}
        onRunTask={() => undefined}
        akshareTrial={{
          status: "dry_run",
          passed: true,
          started_at: "2026-07-03T00:00:00+00:00",
          ended_at: "2026-07-03T00:00:01+00:00",
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
      />,
    );

    expect(html).toContain("最近真实试跑");
    expect(html).toContain("make akshare-trial");
    expect(html).toContain("make akshare-trial-dry-run");
    expect(html).toContain("dry_run");
    expect(html).toContain("csi800");
    expect(html).toContain("data/reports/akshare_trial_run.json");
    expect(html).toContain("config");
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
