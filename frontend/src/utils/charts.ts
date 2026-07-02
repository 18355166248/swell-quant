import type {
  BacktestPoint,
  Prediction,
  StockFeature,
  StockPrices,
} from "../types/api";
import { formatPercent } from "./display";

export function buildEquityOption(points: BacktestPoint[]) {
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["组合净值", "基准净值", "超额净值"] },
    grid: { top: 44, left: 48, right: 24, bottom: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => point.date),
    },
    yAxis: {
      type: "value",
      min: "dataMin",
      axisLabel: {
        formatter: (value: number) => value.toFixed(2),
      },
    },
    series: [
      {
        name: "组合净值",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((point) => point.portfolio_value),
      },
      {
        name: "基准净值",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((point) => point.benchmark_value),
      },
      {
        name: "超额净值",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((point) => point.excess_value),
      },
    ],
  };
}

export function buildDrawdownOption(points: BacktestPoint[]) {
  return {
    tooltip: {
      trigger: "axis",
      valueFormatter: (value: number) => formatPercent(value),
    },
    legend: { top: 0, data: ["组合回撤", "基准回撤"] },
    grid: { top: 44, left: 56, right: 24, bottom: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => point.date),
    },
    yAxis: {
      type: "value",
      max: 0,
      axisLabel: {
        formatter: (value: number) => formatPercent(value),
      },
    },
    series: [
      {
        name: "组合回撤",
        type: "line",
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.12 },
        data: points.map((point) => point.portfolio_drawdown),
      },
      {
        name: "基准回撤",
        type: "line",
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.08 },
        data: points.map((point) => point.benchmark_drawdown),
      },
    ],
  };
}

export function buildRelativeReturnOption(points: BacktestPoint[]) {
  return {
    tooltip: {
      trigger: "axis",
      valueFormatter: (value: number) => formatPercent(value),
    },
    grid: { top: 28, left: 56, right: 24, bottom: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => point.date),
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => formatPercent(value),
      },
    },
    series: [
      {
        name: "相对基准",
        type: "line",
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.1 },
        data: points.map((point) => point.relative_return),
      },
    ],
  };
}

export function buildScoreOption(predictions: Prediction[]) {
  return {
    tooltip: { trigger: "axis" },
    grid: { top: 28, left: 44, right: 20, bottom: 34 },
    xAxis: {
      type: "category",
      data: predictions.map((row) => row.symbol),
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => value.toFixed(2),
      },
    },
    series: [
      {
        name: "预测分数",
        type: "bar",
        data: predictions.map((row) => row.score),
        itemStyle: { color: "#1f6feb" },
      },
    ],
  };
}

export function buildStockPriceOption(data?: StockPrices) {
  const prices = data?.prices ?? [];
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["收盘价", "基准收盘"] },
    grid: { top: 44, left: 48, right: 24, bottom: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: prices.map((row) => row.date),
    },
    yAxis: {
      type: "value",
      min: "dataMin",
      axisLabel: {
        formatter: (value: number) => value.toFixed(0),
      },
    },
    series: [
      {
        name: "收盘价",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: prices.map((row) => row.close),
      },
      {
        name: "基准收盘",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: prices.map((row) => row.benchmark_close),
      },
    ],
  };
}

export function buildStockFactorOption(features: StockFeature[]) {
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["5 日动量", "1 日收益", "RSI6", "MACD 柱", "成交量变化"] },
    grid: { top: 44, left: 48, right: 24, bottom: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: features.map((row) => row.date),
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => value.toFixed(2),
      },
    },
    series: [
      {
        name: "5 日动量",
        type: "line",
        showSymbol: false,
        data: features.map((row) => row.momentum_5d),
      },
      {
        name: "1 日收益",
        type: "line",
        showSymbol: false,
        data: features.map((row) => row.return_1d),
      },
      {
        name: "RSI6",
        type: "line",
        showSymbol: false,
        yAxisIndex: 0,
        data: features.map((row) => (row.rsi_6 === null ? null : row.rsi_6 / 100)),
      },
      {
        name: "MACD 柱",
        type: "line",
        showSymbol: false,
        data: features.map((row) => row.macd_hist),
      },
      {
        name: "成交量变化",
        type: "line",
        showSymbol: false,
        data: features.map((row) => row.volume_change_1d),
      },
    ],
  };
}
