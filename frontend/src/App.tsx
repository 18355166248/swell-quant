import { useEffect, useState } from "react";
import { Activity, Database, LineChart, Moon, Sun, Layers, ScrollText } from "lucide-react";
import { api, type Meta } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(
    () => (localStorage.getItem("sq-theme") as "dark" | "light") || "dark",
  );
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("sq-theme", theme);
  }, [theme]);
  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}

type Status = "loading" | "ok" | "down";

function StatTile({
  icon,
  label,
  value,
  sub,
  delay,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  delay: number;
}) {
  return (
    <Card
      className="animate-fade-up p-5 transition-colors hover:border-accent/40"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="mb-4 flex items-center gap-2 text-muted-foreground">
        <span className="text-accent">{icon}</span>
        <span className="eyebrow">{label}</span>
      </div>
      <div className="tnum text-3xl font-medium leading-none text-foreground">{value}</div>
      {sub && <div className="tnum mt-2 text-xs text-muted-foreground">{sub}</div>}
    </Card>
  );
}

export default function App() {
  const { theme, toggle } = useTheme();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    api
      .meta()
      .then((m) => {
        setMeta(m);
        setStatus("ok");
      })
      .catch(() => setStatus("down"));
  }, []);

  const u = meta?.universes?.[0];

  return (
    <div className="min-h-screen">
      {/* 顶栏 */}
      <header className="sticky top-0 z-10 border-b border-border bg-background">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="grid size-7 place-items-center rounded-sm bg-accent text-accent-foreground">
              <Activity className="size-4" strokeWidth={2.5} />
            </div>
            <span className="font-mono text-sm font-semibold tracking-[0.14em]">SWELL QUANT</span>
          </div>
          <div className="flex items-center gap-3">
            <StatusPill status={status} />
            <Button variant="ghost" size="icon" onClick={toggle} aria-label="切换主题">
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-24">
        {/* Hero */}
        <section className="animate-fade-up py-14">
          <div className="eyebrow mb-4">A 股多因子研究台 · 只读</div>
          <h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
            一台<span className="text-accent">诚实</span>的量化研究仪器
          </h1>
          <p className="mt-5 max-w-xl text-sm leading-relaxed text-muted-foreground">
            数据 → 因子 → 评估 → 回测，全程无未来函数。它不用漂亮数字骗你，
            而是把每一层偏差如实摊开——所以你敢信它。
          </p>
        </section>

        {/* 系统概况 */}
        <section>
          <div className="eyebrow mb-4 flex items-center gap-2">
            <span className="h-px w-6 bg-accent" />
            系统概况
          </div>

          {status === "down" ? (
            <BackendDown />
          ) : (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatTile
                icon={<Database className="size-4" />}
                label="行情"
                value={status === "loading" ? "—" : fmt(meta!.bars.rows)}
                sub={
                  status === "loading"
                    ? "加载中"
                    : `${meta!.bars.symbols} 只 · ${meta!.bars.start ?? "?"} → ${meta!.bars.end ?? "?"}`
                }
                delay={0}
              />
              <StatTile
                icon={<ScrollText className="size-4" />}
                label="财务 / 估值"
                value={status === "loading" ? "—" : fmt((meta!.fundamentals || 0) + (meta!.valuations || 0))}
                sub={status === "loading" ? "" : `财务 ${fmt(meta!.fundamentals)} · 估值 ${fmt(meta!.valuations)}`}
                delay={70}
              />
              <StatTile
                icon={<Layers className="size-4" />}
                label="成分快照"
                value={status === "loading" ? "—" : String(u?.members ?? 0)}
                sub={status === "loading" ? "" : `${u?.index_code ?? "—"} · ${u?.snapshot_date ?? ""}`}
                delay={140}
              />
              <StatTile
                icon={<LineChart className="size-4" />}
                label="采集批次"
                value={status === "loading" ? "—" : String(meta!.ingestion_batches)}
                sub={status === "loading" ? "" : `指数日线 ${fmt(meta!.index_bars)} 根`}
                delay={210}
              />
            </div>
          )}
        </section>

        {/* 占位：后续 P3 加因子评估 / 回测页 */}
        <section className="mt-6">
          <Card className="animate-fade-up border-dashed p-8 text-center" style={{ animationDelay: "280ms" }}>
            <div className="eyebrow mb-2">下一步</div>
            <p className="text-sm text-muted-foreground">
              因子评估与回测页开发中（P3）。
            </p>
          </Card>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-6">
          <p className="text-xs text-muted-foreground">
            仅用于研究，不构成投资建议。回测收益不等于可实现收益。
          </p>
        </div>
      </footer>
    </div>
  );
}

function StatusPill({ status }: { status: Status }) {
  const map = {
    loading: { c: "bg-muted-foreground", t: "连接中" },
    ok: { c: "bg-pos", t: "后端已连接" },
    down: { c: "bg-neg", t: "后端未连接" },
  }[status];
  return (
    <div className="flex items-center gap-2 rounded-full border border-border px-3 py-1">
      <span className={`size-1.5 rounded-full ${map.c}`} />
      <span className="font-mono text-[0.68rem] tracking-wide text-muted-foreground">{map.t}</span>
    </div>
  );
}

function BackendDown() {
  return (
    <Card className="animate-fade-up p-8">
      <div className="eyebrow mb-3 text-neg">后端桥未连接</div>
      <p className="mb-4 text-sm text-muted-foreground">
        启动只读后端桥后刷新本页：
      </p>
      <pre className="tnum overflow-x-auto rounded-md border border-border bg-background/60 p-4 text-xs text-foreground">
        python -m swell_quant.api --db data/duckdb/marketdata.duckdb
      </pre>
    </Card>
  );
}

function fmt(n: number): string {
  return n.toLocaleString("en-US");
}
