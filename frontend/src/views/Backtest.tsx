import { useEffect, useState } from "react";
import { Play, Loader2, TriangleAlert } from "lucide-react";
import { api, type BacktestResult, type FactorCatalogItem } from "@/lib/api";
import { pct, num } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Field } from "@/components/ui/input";
import { MetricCard } from "@/components/MetricCard";
import { EquityChart } from "@/components/EquityChart";

interface FactorState {
  enabled: boolean;
  value: string; // lookback 数字或 item 字符串
  weight: string;
}

const DEFAULT_ON: Record<string, { weight: string }> = {
  momentum: { weight: "1" },
  quality: { weight: "1" },
  volatility: { weight: "-1" },
};

export function Backtest() {
  const [catalog, setCatalog] = useState<FactorCatalogItem[]>([]);
  const [factors, setFactors] = useState<Record<string, FactorState>>({});
  const [params, setParams] = useState({
    universe_index: "000300",
    start: "2018-01-01",
    end: "2026-05-01",
    step: "20",
    horizon: "20",
    top_n: "20",
    cost_bps: "10",
    benchmark: "equal_weight",
  });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.factors().then(({ catalog }) => {
      setCatalog(catalog);
      const init: Record<string, FactorState> = {};
      for (const f of catalog) {
        init[f.name] = {
          enabled: f.name in DEFAULT_ON,
          value: String(f.default),
          weight: DEFAULT_ON[f.name]?.weight ?? "1",
        };
      }
      setFactors(init);
    });
  }, []);

  const setF = (name: string, patch: Partial<FactorState>) =>
    setFactors((s) => ({ ...s, [name]: { ...s[name], ...patch } }));

  async function run() {
    const chosen = catalog.filter((f) => factors[f.name]?.enabled);
    if (chosen.length === 0) {
      setError("至少选择一个因子");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const body = {
        factors: chosen.map((f) => {
          const st = factors[f.name];
          const base = { name: f.name, weight: Number(st.weight) };
          return f.param === "lookback"
            ? { ...base, lookback: Number(st.value) }
            : { ...base, item: st.value };
        }),
        start: params.start,
        end: params.end,
        step: Number(params.step),
        horizon: Number(params.horizon),
        top_n: Number(params.top_n),
        cost_bps: Number(params.cost_bps),
        benchmark: params.benchmark,
        benchmark_index: "sh000300",
        universe_index: params.universe_index || null,
      };
      setResult(await api.backtest(body));
    } catch (e) {
      setError(String(e));
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  const m = result?.metrics;
  const benchLabel = params.benchmark === "equal_weight" ? "等权全池" : "沪深300";

  return (
    <div className="animate-fade-up space-y-6">
      <div>
        <div className="eyebrow mb-1">策略回测</div>
        <h2 className="text-2xl font-semibold tracking-tight">多因子组合 · 净值与超额</h2>
      </div>

      {/* 控制面板 */}
      <Card className="p-5">
        <div className="eyebrow mb-3">因子与权重</div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {catalog.map((f) => {
            const st = factors[f.name];
            if (!st) return null;
            return (
              <div
                key={f.name}
                className="flex items-center gap-2 rounded-sm border border-border px-3 py-2"
              >
                <input
                  type="checkbox"
                  checked={st.enabled}
                  onChange={(e) => setF(f.name, { enabled: e.target.checked })}
                  className="accent-[hsl(var(--accent))]"
                />
                <span className="flex-1 text-sm">{f.label}</span>
                <input
                  value={st.value}
                  onChange={(e) => setF(f.name, { value: e.target.value })}
                  className="tnum h-7 w-16 rounded-sm border border-input bg-background/60 px-1.5 text-xs"
                  title={f.param === "lookback" ? "回看窗口" : "指标"}
                />
                <input
                  value={st.weight}
                  onChange={(e) => setF(f.name, { weight: e.target.value })}
                  className="tnum h-7 w-12 rounded-sm border border-input bg-background/60 px-1.5 text-xs"
                  title="权重"
                />
              </div>
            );
          })}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          <Field label="股票池">
            <Input value={params.universe_index} onChange={(e) => setParams({ ...params, universe_index: e.target.value })} />
          </Field>
          <Field label="开始">
            <Input type="date" value={params.start} onChange={(e) => setParams({ ...params, start: e.target.value })} />
          </Field>
          <Field label="结束">
            <Input type="date" value={params.end} onChange={(e) => setParams({ ...params, end: e.target.value })} />
          </Field>
          <Field label="调仓间隔">
            <Input value={params.step} onChange={(e) => setParams({ ...params, step: e.target.value })} />
          </Field>
          <Field label="持有期">
            <Input value={params.horizon} onChange={(e) => setParams({ ...params, horizon: e.target.value })} />
          </Field>
          <Field label="Top-N">
            <Input value={params.top_n} onChange={(e) => setParams({ ...params, top_n: e.target.value })} />
          </Field>
          <Field label="成本(bps)">
            <Input value={params.cost_bps} onChange={(e) => setParams({ ...params, cost_bps: e.target.value })} />
          </Field>
          <Field label="基准">
            <select
              value={params.benchmark}
              onChange={(e) => setParams({ ...params, benchmark: e.target.value })}
              className="h-8 rounded-sm border border-input bg-background/60 px-2 text-sm"
            >
              <option value="equal_weight">等权全池</option>
              <option value="index">沪深300</option>
            </select>
          </Field>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <Button onClick={run} disabled={running}>
            {running ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
            {running ? "运行中…" : "运行回测"}
          </Button>
          {error && (
            <span className="flex items-center gap-1.5 text-xs text-neg">
              <TriangleAlert className="size-3.5" /> {error}
            </span>
          )}
        </div>
      </Card>

      {/* 结果 */}
      {m && result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="组合总收益" value={pct(m.total_return)} tone={sgn(m.total_return)} sub={`${result.periods} 期`} />
            <MetricCard label="年化收益" value={pct(m.annualized_return)} tone={sgn(m.annualized_return)} />
            <MetricCard label={`超额IR · vs ${benchLabel}`} value={num(m.information_ratio, 2)} tone={sgn(m.information_ratio)} />
            <MetricCard label="超额胜率" value={pct(m.excess_hit_rate, 0)} />
            <MetricCard label="最大回撤" value={pct(m.max_drawdown)} tone="neg" />
            <MetricCard label="累计成本" value={pct(m.total_cost)} sub={`基准 ${pct(m.benchmark_total_return)}`} />
          </div>
          <Card className="p-5">
            <div className="eyebrow mb-4">净值曲线（扣成本，起点 1.0）</div>
            <EquityChart data={result.equity_curve} />
          </Card>
          <p className="text-xs leading-relaxed text-muted-foreground">
            提示：对市值加权指数“跑赢”可能只是等权 tilt；对<strong className="text-foreground">等权全池</strong>的超额才是纯选股 alpha。
            成本 10bps 对 A 股偏乐观，高换手信号会被成本吃光。
          </p>
        </div>
      )}
    </div>
  );
}

function sgn(x: number | null | undefined): "pos" | "neg" | "neutral" {
  if (x === null || x === undefined) return "neutral";
  return x >= 0 ? "pos" : "neg";
}
