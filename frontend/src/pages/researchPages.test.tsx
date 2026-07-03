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
import type { AkshareUniverseStatus, LocalSettings, Prediction, ProjectProgress } from "../types/api";

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
    expect(html).not.toContain("sk-secret-should-not-render");
  });
});
