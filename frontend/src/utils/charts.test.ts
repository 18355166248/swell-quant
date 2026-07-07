import { describe, expect, it } from "vitest";

import {
  buildEquityOption,
  buildFeatureImportanceOption,
  buildScoreOption,
  buildStockFactorOption,
  buildStockPriceOption,
} from "./charts";
import type {
  BacktestPoint,
  ModelFeatureImportance,
  Prediction,
  StockFeature,
  StockPrices,
} from "../types/api";

function makeImportance(rank: number): ModelFeatureImportance {
  return {
    feature_name: `f${rank}`,
    rank,
    importance: 1 / rank,
    raw_importance: rank,
    importance_type: "gain",
  };
}

describe("chart option builders", () => {
  it("maps equity curve points into portfolio, benchmark, and excess series", () => {
    const points: BacktestPoint[] = [
      {
        date: "2024-01-03",
        signal_date: "2024-01-02",
        portfolio_return: 0.01,
        benchmark_return: 0.005,
        portfolio_value: 1.01,
        benchmark_value: 1.005,
        excess_value: 0.005,
        relative_return: 0.004975,
        portfolio_drawdown: 0,
        benchmark_drawdown: 0,
      },
    ];

    const option = buildEquityOption(points);

    expect(option.xAxis.data).toEqual(["2024-01-03"]);
    expect(option.series.map((series) => series.name)).toEqual(["组合净值", "基准净值", "超额净值"]);
    expect(option.series.map((series) => series.data)).toEqual([[1.01], [1.005], [0.005]]);
  });

  it("maps prediction rows into symbol score bars", () => {
    const predictions: Prediction[] = [
      {
        rank: 1,
        symbol: "000300.SH",
        date: "2024-01-08",
        model_version: "baseline-rule-v1",
        score: 0.42,
        return_1d: 0.01,
        momentum_5d: 0.05,
        volume_change_1d: 0.02,
      },
    ];

    const option = buildScoreOption(predictions);

    expect(option.xAxis.data).toEqual(["000300.SH"]);
    expect(option.series[0].name).toBe("预测分数");
    expect(option.series[0].data).toEqual([0.42]);
  });

  it("handles missing stock prices as an empty chart dataset", () => {
    const option = buildStockPriceOption(undefined);

    expect(option.xAxis.data).toEqual([]);
    expect(option.series.map((series) => series.data)).toEqual([[], []]);
  });

  it("normalizes RSI into chart scale while preserving nullable factor points", () => {
    const features: StockFeature[] = [
      {
        date: "2024-01-08",
        close: 10.5,
        return_1d: 0.01,
        momentum_5d: 0.04,
        ma_5: 10.3,
        volatility_5d: 0.02,
        rsi_6: 75,
        macd_dif: 0.1,
        macd_signal: 0.08,
        macd_hist: 0.02,
        volume_change_1d: null,
      },
    ];

    const option = buildStockFactorOption(features);

    expect(option.xAxis.data).toEqual(["2024-01-08"]);
    expect(option.series.find((series) => series.name === "RSI6")?.data).toEqual([0.75]);
    expect(option.series.find((series) => series.name === "成交量变化")?.data).toEqual([null]);
  });

  it("renders feature importance as a horizontal bar chart", () => {
    const option = buildFeatureImportanceOption([makeImportance(1), makeImportance(2)]);

    expect(option.yAxis.type).toBe("category");
    expect(option.xAxis.type).toBe("value");
    expect(option.series[0].type).toBe("bar");
    expect(option.series[0].data).toHaveLength(2);
  });

  it("truncates feature importance rows to topN keeping the most important", () => {
    const rows = [5, 3, 1, 4, 2].map(makeImportance);

    const option = buildFeatureImportanceOption(rows, 3);

    expect(option.series[0].data).toHaveLength(3);
    // 横向条形图从下往上绘制，末位对应 rank 最小（最重要）的特征。
    expect(option.yAxis.data).toEqual(["f3", "f2", "f1"]);
    expect(option.yAxis.data[option.yAxis.data.length - 1]).toBe("f1");
  });

  it("returns a valid option with empty series for no feature importance", () => {
    const option = buildFeatureImportanceOption([]);

    expect(option.yAxis.data).toEqual([]);
    expect(option.series[0].data).toEqual([]);
  });
});
