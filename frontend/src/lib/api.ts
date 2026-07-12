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
};
