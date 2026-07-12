import { useEffect, useState } from "react";
import { Activity, Moon, Sun } from "lucide-react";
import { api, type Meta } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Overview } from "@/views/Overview";
import { Backtest } from "@/views/Backtest";

type Status = "loading" | "ok" | "down";
type View = "overview" | "backtest";

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

const NAV: { id: View; label: string }[] = [
  { id: "overview", label: "概况" },
  { id: "backtest", label: "回测" },
];

export default function App() {
  const { theme, toggle } = useTheme();
  const [view, setView] = useState<View>("overview");
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

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-border bg-background">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <div className="grid size-7 place-items-center rounded-sm bg-accent text-accent-foreground">
                <Activity className="size-4" strokeWidth={2.5} />
              </div>
              <span className="font-mono text-sm font-semibold tracking-[0.14em]">SWELL QUANT</span>
            </div>
            <nav className="flex items-center gap-1">
              {NAV.map((n) => (
                <button
                  key={n.id}
                  onClick={() => setView(n.id)}
                  className={cn(
                    "relative rounded-sm px-3 py-1.5 text-sm transition-colors",
                    view === n.id
                      ? "text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {n.label}
                  {view === n.id && (
                    <span className="absolute inset-x-3 -bottom-[9px] h-px bg-accent" />
                  )}
                </button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <StatusPill status={status} />
            <Button variant="ghost" size="icon" onClick={toggle} aria-label="切换主题">
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-24 pt-8">
        {view === "overview" ? <Overview meta={meta} status={status} /> : <Backtest />}
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
