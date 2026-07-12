// 后端桥（FastAPI）的类型与取数封装。开发时 Vite 把 /api 代理到 127.0.0.1:8000。

export interface Meta {
  bars: { rows: number; symbols: number; start: string | null; end: string | null };
  fundamentals: number;
  valuations: number;
  index_bars: number;
  universes: { index_code: string; snapshot_date: string; members: number }[];
  ingestion_batches: number;
}

export interface FactorCatalogItem {
  name: string;
  label: string;
  param: "lookback" | "item";
  default: number | string;
}

export interface BacktestMetrics {
  total_return: number | null;
  annualized_return: number | null;
  annualized_sharpe: number | null;
  information_ratio: number | null;
  excess_hit_rate: number | null;
  benchmark_total_return: number | null;
  max_drawdown: number | null;
  total_cost: number;
}

export interface BacktestResult {
  periods: number;
  metrics: BacktestMetrics;
  equity_curve: { date: string; equity: number }[];
}

export interface InstrumentAnalysis {
  code: string;
  start: string;
  end: string;
  n: number;
  current: number;
  inception_return: number | null;
  ath: number;
  ath_date: string;
  atl: number;
  drawdown_from_ath: number | null;
  max_drawdown: number;
  range_percentile: number;
  trend: Record<string, "above" | "below" | null>;
  trailing_returns: { m1: number | null; m3: number | null; m6: number | null; m12: number | null };
  ann_vol_60d: number | null;
  vol_percentile: number | null;
  return_dist_20d: { p5: number; p50: number; p95: number; min: number; max: number } | null;
  valuation: ValuationPercentile | null;
  note: string;
}

export interface ValuationPercentile {
  item: string;
  current: number;
  percentile: number;
  min: number;
  max: number;
  median: number;
  n: number;
  start: string;
  end: string;
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  factors: () => get<{ catalog: FactorCatalogItem[] }>("/api/factors"),
  backtest: async (body: unknown): Promise<BacktestResult> => {
    const res = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  instrument: (code: string) => get<InstrumentAnalysis>(`/api/instrument?code=${encodeURIComponent(code)}`),
  uploadValuation: async (body: {
    code: string;
    item: string;
    source?: string;
    points: { date: string; value: number }[];
  }): Promise<{ written: number }> => {
    const res = await fetch("/api/instrument/valuation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
};
