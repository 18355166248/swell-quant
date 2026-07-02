import { describe, expect, it } from "vitest";

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
});
