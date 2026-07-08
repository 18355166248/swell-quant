import type { Prediction } from "../types/api";

export interface WatchlistFactor {
  name: string;
  value: number;
  direction: "up" | "down";
}

export interface WatchlistRiskHint {
  code: "limit_move" | "volume_spike";
  label: string;
}

export interface WatchlistItem {
  rank: number;
  symbol: string;
  score: number;
  confidence: number;
  confidenceLevel: "high" | "medium" | "low";
  factors: WatchlistFactor[];
  riskHints: WatchlistRiskHint[];
}

const FACTOR_LABELS: Array<{ key: keyof Prediction; name: string }> = [
  { key: "momentum_5d", name: "5日动量" },
  { key: "return_1d", name: "1日收益" },
  { key: "volume_change_1d", name: "成交量变化" },
];

export function buildWatchlist(rows: Prediction[], topN = 10): WatchlistItem[] {
  if (rows.length === 0 || topN <= 0) {
    return [];
  }

  const scores = rows.map((row) => row.score);
  const minScore = Math.min(...scores);
  const maxScore = Math.max(...scores);
  const denominator = maxScore - minScore;

  return [...rows]
    .sort((left, right) => left.rank - right.rank)
    .slice(0, topN)
    .map((row) => {
      // 置信度只是同一批预测分数的相对位置，不代表胜率或收益概率。
      const confidence = denominator === 0 ? 0.5 : (row.score - minScore) / denominator;
      return {
        rank: row.rank,
        symbol: row.symbol,
        score: row.score,
        confidence,
        confidenceLevel: confidenceLevel(confidence),
        factors: buildFactorTags(row),
        riskHints: buildRiskHints(row),
      };
    });
}

function confidenceLevel(confidence: number): WatchlistItem["confidenceLevel"] {
  if (confidence >= 0.8) {
    return "high";
  }
  if (confidence >= 0.5) {
    return "medium";
  }
  return "low";
}

function buildFactorTags(row: Prediction): WatchlistFactor[] {
  return FACTOR_LABELS.flatMap(({ key, name }) => {
    const value = row[key];
    if (typeof value !== "number" || Number.isNaN(value)) {
      return [];
    }
    return [{ name, value, direction: value >= 0 ? "up" : "down" } satisfies WatchlistFactor];
  })
    .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))
    .slice(0, 3);
}

function buildRiskHints(row: Prediction): WatchlistRiskHint[] {
  const hints: WatchlistRiskHint[] = [];
  if (typeof row.return_1d === "number" && Math.abs(row.return_1d) >= 0.095) {
    hints.push({ code: "limit_move", label: "接近涨跌停幅度" });
  }
  if (
    typeof row.volume_change_1d === "number" &&
    Math.abs(row.volume_change_1d) >= 2
  ) {
    hints.push({ code: "volume_spike", label: "成交量异动" });
  }
  return hints;
}
