import { describe, expect, it } from "vitest";

import { buildPredictionColumns } from "./tableColumns";
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
});
