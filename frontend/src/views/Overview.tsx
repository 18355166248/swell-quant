import { Database, Layers, LineChart, ScrollText } from "lucide-react";
import type { Meta } from "@/lib/api";
import { Card } from "@/components/ui/card";

type Status = "loading" | "ok" | "down";

export function Overview({ meta, status }: { meta: Meta | null; status: Status }) {
  const u = meta?.universes?.[0];
  return (
    <div className="space-y-8">
      <section className="animate-fade-up pt-6">
        <div className="eyebrow mb-4">A 股多因子研究台 · 只读</div>
        <h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
          一台<span className="text-accent">诚实</span>的量化研究仪器
        </h1>
        <p className="mt-5 max-w-xl text-sm leading-relaxed text-muted-foreground">
          数据 → 因子 → 评估 → 回测，全程无未来函数。它不用漂亮数字骗你，
          而是把每一层偏差如实摊开——所以你敢信它。
        </p>
      </section>

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
              sub={status === "loading" ? "加载中" : `${meta!.bars.symbols} 只 · ${meta!.bars.start ?? "?"} → ${meta!.bars.end ?? "?"}`}
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
    </div>
  );
}

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

function BackendDown() {
  return (
    <Card className="animate-fade-up p-8">
      <div className="eyebrow mb-3 text-neg">后端桥未连接</div>
      <p className="mb-4 text-sm text-muted-foreground">启动只读后端桥后刷新本页：</p>
      <pre className="tnum overflow-x-auto rounded-md border border-border bg-background/60 p-4 text-xs text-foreground">
        python -m swell_quant.api --db data/duckdb/marketdata.duckdb
      </pre>
    </Card>
  );
}

function fmt(n: number): string {
  return n.toLocaleString("en-US");
}
