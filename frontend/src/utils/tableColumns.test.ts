import { describe, expect, it } from "vitest";

import {
  buildArtifactColumns,
  buildCheckColumns,
  buildModelSummaryColumns,
  buildPredictionColumns,
  buildTaskSummaryColumns,
} from "./tableColumns";
import type { Prediction } from "../types/api";

describe("table column builders", () => {
  const prediction: Prediction = {
    rank: 1,
    symbol: "000300.SH",
    date: "2024-01-08",
    model_version: "baseline-rule-v1",
    score: 0.2,
    return_1d: null,
    momentum_5d: null,
    volume_change_1d: null,
  };

  it("builds prediction columns with stable titles and data bindings", () => {
    const columns = buildPredictionColumns() as Array<Record<string, any>>;

    expect(columns.map((column) => column.title)).toEqual([
      "排名",
      "代码",
      "日期",
      "预测分数",
      "1 日收益",
      "5 日动量",
      "成交量变化",
    ]);
    expect(columns.map((column) => column.dataIndex)).toEqual([
      "rank",
      "symbol",
      "date",
      "score",
      "return_1d",
      "momentum_5d",
      "volume_change_1d",
    ]);
  });

  it("sorts prediction ranking and score columns numerically", () => {
    const [rankColumn, , , scoreColumn] = buildPredictionColumns() as Array<Record<string, any>>;
    const low: Prediction = prediction;
    const high: Prediction = { ...low, rank: 3, symbol: "000905.SH", score: 0.8 };

    expect(rankColumn.sorter?.(high, low)).toBe(2);
    expect(scoreColumn.sorter?.(high, low)).toBeCloseTo(0.6);
  });

  it("formats score and nullable factor cells consistently", () => {
    const columns = buildPredictionColumns() as Array<Record<string, any>>;
    const scoreColumn = columns[3];
    const returnColumn = columns[4];

    expect(scoreColumn.render?.(0.123456, prediction, 0)).toBe("0.1235");
    expect(returnColumn.render?.(null, prediction, 0)).toBe("-");
    expect(returnColumn.render?.(0.123456, prediction, 0)).toBe("0.1235");
  });

  it("builds reusable check columns with optional key visibility", () => {
    const compactColumns = buildCheckColumns() as Array<Record<string, any>>;
    const detailedColumns = buildCheckColumns({ showKey: true }) as Array<Record<string, any>>;

    expect(compactColumns.map((column) => column.title)).toEqual(["检查项", "状态", "说明"]);
    expect(detailedColumns.map((column) => column.title)).toEqual([
      "检查项",
      "Key",
      "状态",
      "说明",
    ]);
    expect(
      (buildCheckColumns({ nameWidth: 160, statusWidth: 110 }) as Array<Record<string, any>>)
        .slice(0, 2)
        .map((column) => column.width),
    ).toEqual([160, 110]);
    expect(compactColumns[1].render("passed").props).toMatchObject({
      color: "green",
      children: "通过",
    });
    expect(compactColumns[1].render("failed").props).toMatchObject({
      color: "red",
      children: "失败",
    });
  });

  it("builds reusable artifact columns while preserving missing status color policy", () => {
    const columns = buildArtifactColumns({ missingColor: "orange" }) as Array<Record<string, any>>;

    expect(columns.map((column) => column.title)).toEqual([
      "产物",
      "路径",
      "大小",
      "更新时间",
      "状态",
    ]);
    expect(columns[2].render(2048)).toBe("2.0 KB");
    expect(columns[4].render(false).props).toMatchObject({
      color: "orange",
      children: "缺失",
    });
  });

  it("builds reusable model summary columns with compact and detailed variants", () => {
    const compactColumns = buildModelSummaryColumns({ variant: "compact" }) as Array<Record<string, any>>;
    const detailedColumns = buildModelSummaryColumns() as Array<Record<string, any>>;

    expect(compactColumns.map((column) => column.title)).toEqual([
      "版本",
      "类型",
      "特征",
      "预测日",
    ]);
    expect(detailedColumns.map((column) => column.title)).toEqual([
      "版本",
      "类型",
      "后端",
      "特征",
      "预测日",
      "评估",
    ]);
    expect(detailedColumns[5].render("ready").props).toMatchObject({
      color: "green",
      children: "ready",
    });
  });

  it("builds reusable task summary columns with status colors", () => {
    const columns = buildTaskSummaryColumns() as Array<Record<string, any>>;

    expect(columns.map((column) => column.title)).toEqual(["任务", "状态"]);
    expect(columns[1].render("failed").props).toMatchObject({
      color: "red",
      children: "failed",
    });
  });
});
