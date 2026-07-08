import { describe, expect, it } from "vitest";

import type { Prediction } from "../types/api";
import { buildWatchlist } from "./watchlist";

const basePrediction: Prediction = {
  rank: 1,
  symbol: "000001.SZ",
  date: "2024-01-08",
  model_version: "baseline-rule-v1",
  score: 0.5,
  return_1d: 0.01,
  momentum_5d: 0.02,
  volume_change_1d: 0.03,
};

describe("buildWatchlist", () => {
  it("normalizes confidence by score range and maps levels", () => {
    const items = buildWatchlist([
      { ...basePrediction, rank: 1, symbol: "A", score: 0.9 },
      { ...basePrediction, rank: 2, symbol: "B", score: 0.6 },
      { ...basePrediction, rank: 3, symbol: "C", score: 0.1 },
    ]);

    expect(items.map((item) => item.confidence)).toEqual([1, 0.625, 0]);
    expect(items.map((item) => item.confidenceLevel)).toEqual(["high", "medium", "low"]);
  });

  it("uses medium confidence when every score is equal", () => {
    const items = buildWatchlist([
      { ...basePrediction, rank: 1, symbol: "A", score: 0.2 },
      { ...basePrediction, rank: 2, symbol: "B", score: 0.2 },
    ]);

    expect(items.map((item) => item.confidence)).toEqual([0.5, 0.5]);
    expect(items.map((item) => item.confidenceLevel)).toEqual(["medium", "medium"]);
  });

  it("sorts factor tags by absolute value and keeps direction", () => {
    const [item] = buildWatchlist([
      {
        ...basePrediction,
        return_1d: -0.04,
        momentum_5d: 0.12,
        volume_change_1d: 0.6,
      },
    ]);

    expect(item.factors).toEqual([
      { name: "成交量变化", value: 0.6, direction: "up" },
      { name: "5日动量", value: 0.12, direction: "up" },
      { name: "1日收益", value: -0.04, direction: "down" },
    ]);
  });

  it("adds heuristic risk hints only when source fields cross thresholds", () => {
    const [item] = buildWatchlist([
      {
        ...basePrediction,
        return_1d: 0.096,
        volume_change_1d: 2.1,
      },
    ]);

    expect(item.riskHints).toEqual([
      { code: "limit_move", label: "接近涨跌停幅度" },
      { code: "volume_spike", label: "成交量异动" },
    ]);
  });

  it("respects topN and returns empty output for empty rows", () => {
    expect(buildWatchlist([], 10)).toEqual([]);
    expect(
      buildWatchlist([
        { ...basePrediction, rank: 2, symbol: "B" },
        { ...basePrediction, rank: 1, symbol: "A" },
      ], 1),
    ).toHaveLength(1);
  });
});
