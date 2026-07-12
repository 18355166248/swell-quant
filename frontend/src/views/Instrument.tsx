import { useEffect, useState } from "react";
import { Search, Loader2, Info, TriangleAlert, Upload, RefreshCw } from "lucide-react";
import { api, type InstrumentAnalysis } from "@/lib/api";
import { pct } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { MetricCard } from "@/components/MetricCard";

const MA_LABEL: Record<string, string> = { "20": "MA20", "60": "MA60", "120": "MA120", "250": "MA250" };
const TR_LABEL: Record<string, string> = { m1: "近1月", m3: "近3月", m6: "近6月", m12: "近12月" };

export function Instrument() {
  const [code, setCode] = useState("513260");
  const [data, setData] = useState<InstrumentAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [valText, setValText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [danjuanIndex, setDanjuanIndex] = useState("HKHSTECH");
  const [refreshing, setRefreshing] = useState(false);

  async function load(c: string) {
    setLoading(true);
    setError(null);
    try {
      setData(await api.instrument(c.trim()));
    } catch (e) {
      setError(`取数失败：${e}`);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  async function uploadValuation() {
    const points = valText
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => {
        const [d, v] = l.split(/[,\s]+/);
        return { date: d, value: Number(v) };
      })
      .filter((p) => /^\d{4}-\d{2}-\d{2}$/.test(p.date) && !Number.isNaN(p.value));
    if (points.length === 0) {
      setError("没有可解析的行（每行格式：2024-01-01,18.5）");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await api.uploadValuation({ code: code.trim(), item: "pe_ttm", points });
      setValText("");
      await load(code);
    } catch (e) {
      setError(`上传失败：${e}`);
    } finally {
      setUploading(false);
    }
  }

  async function refreshValuation() {
    setRefreshing(true);
    setError(null);
    try {
      await api.refreshValuation({ code: code.trim(), danjuan_index: danjuanIndex.trim(), item: "pe_ttm" });
      await load(code);
    } catch (e) {
      setError(`一键更新失败：${e}`);
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load("513260");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sgn = (x: number | null | undefined) => (x == null ? "neutral" : x >= 0 ? "pos" : "neg");

  return (
    <div className="animate-fade-up space-y-6">
      <div>
        <div className="eyebrow mb-1">持仓研究</div>
        <h2 className="text-2xl font-semibold tracking-tight">单标的 · 历史坐标</h2>
      </div>

      {/* 查询 */}
      <div className="flex items-end gap-2">
        <label className="flex flex-col gap-1.5">
          <span className="eyebrow">ETF 代码</span>
          <Input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load(code)}
            className="w-40"
            placeholder="如 513260"
          />
        </label>
        <Button onClick={() => load(code)} disabled={loading}>
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
          查询
        </Button>
        {error && (
          <span className="mb-1.5 flex items-center gap-1.5 text-xs text-neg">
            <TriangleAlert className="size-3.5" /> {error}
          </span>
        )}
      </div>

      {/* 诚实声明 */}
      <div className="flex items-start gap-2 rounded-md border border-accent/30 bg-accent/[0.06] p-3">
        <Info className="mt-0.5 size-4 shrink-0 text-accent" />
        <p className="text-xs leading-relaxed text-muted-foreground">
          以下均为<strong className="text-foreground">历史坐标，不是买卖信号，也不预测未来</strong>。
          同样的低位可以更低，回撤可以更深。它帮你理解处境、校准预期，决定永远是你自己的。
        </p>
      </div>

      {data && (
        <div className="space-y-6">
          <div className="tnum text-xs text-muted-foreground">
            {data.code} · {data.start} → {data.end} · {data.n} 个交易日
          </div>

          {/* 核心坐标 */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="现价" value={data.current.toFixed(3)} />
            <MetricCard label="成立至今" value={pct(data.inception_return)} tone={sgn(data.inception_return)} />
            <MetricCard label="距历史高点" value={pct(data.drawdown_from_ath)} tone="neg" sub={`高点 ${data.ath.toFixed(3)} · ${data.ath_date}`} />
            <MetricCard label="历史最大回撤" value={pct(data.max_drawdown)} tone="neg" />
            <MetricCard label="年化波动(近60日)" value={data.ann_vol_60d == null ? "—" : `${(data.ann_vol_60d * 100).toFixed(0)}%`} sub={data.vol_percentile == null ? "" : `自身历史 ${(data.vol_percentile * 100).toFixed(0)} 分位`} />
            <MetricCard label="价在历史区间" value={`${(data.range_percentile * 100).toFixed(0)}%`} sub="非估值 · 仅价格位置" />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {/* 趋势 */}
            <Card className="p-5">
              <div className="eyebrow mb-4">趋势 · 现价 vs 均线</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.trend).map(([k, v]) => (
                  <span
                    key={k}
                    className={
                      "tnum rounded-sm border px-3 py-1.5 text-xs " +
                      (v === "above"
                        ? "border-accent/40 text-accent"
                        : v === "below"
                          ? "border-border text-muted-foreground"
                          : "border-border text-muted-foreground/50")
                    }
                  >
                    {MA_LABEL[k] ?? k} · {v === "above" ? "上方" : v === "below" ? "下方" : "—"}
                  </span>
                ))}
              </div>
              <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                均线之上/之下只描述过去的价格走势段，不预测反转。
              </p>
            </Card>

            {/* 区间收益 */}
            <Card className="p-5">
              <div className="eyebrow mb-4">区间收益</div>
              <div className="grid grid-cols-4 gap-2">
                {Object.entries(data.trailing_returns).map(([k, v]) => (
                  <div key={k} className="text-center">
                    <div className="eyebrow mb-1.5">{TR_LABEL[k] ?? k}</div>
                    <div className={`tnum text-lg ${v == null ? "text-muted-foreground" : v >= 0 ? "text-pos" : "text-neg"}`}>
                      {pct(v, 1)}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* 收益分布 */}
          {data.return_dist_20d && (
            <Card className="p-5">
              <div className="eyebrow mb-4">20 日收益分布 · 这东西一个月能怎么波动</div>
              <div className="grid grid-cols-3 gap-4 sm:grid-cols-5">
                {[
                  ["最差", data.return_dist_20d.min, "neg"],
                  ["5% 分位", data.return_dist_20d.p5, "neg"],
                  ["中位", data.return_dist_20d.p50, "neutral"],
                  ["95% 分位", data.return_dist_20d.p95, "pos"],
                  ["最好", data.return_dist_20d.max, "pos"],
                ].map(([label, v, tone]) => (
                  <div key={label as string}>
                    <div className="eyebrow mb-1.5">{label as string}</div>
                    <div className={`tnum text-xl ${tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-foreground"}`}>
                      {pct(v as number, 0)}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* 估值分位 · 自带数据 */}
          <Card className={data.valuation ? "p-5" : "border-dashed p-5"}>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div className="eyebrow">估值分位 · "贵还是便宜"</div>
              <div className="flex items-center gap-2">
                <input
                  value={danjuanIndex}
                  onChange={(e) => setDanjuanIndex(e.target.value)}
                  placeholder="蛋卷指数码 如 HKHSTECH"
                  title="蛋卷估值中心的指数代码"
                  className="tnum h-7 w-36 rounded-sm border border-input bg-background/60 px-2 text-xs"
                />
                <Button size="sm" variant="outline" onClick={refreshValuation} disabled={refreshing}>
                  {refreshing ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                  一键更新
                </Button>
              </div>
            </div>
            {data.valuation ? (
              <div>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <div>
                    <div className="eyebrow mb-1.5">当前 {data.valuation.item}</div>
                    <div className="tnum text-2xl font-medium">{data.valuation.current.toFixed(1)}</div>
                  </div>
                  <div>
                    <div className="eyebrow mb-1.5">历史分位</div>
                    <div className="tnum text-2xl font-medium text-accent">
                      {(data.valuation.percentile * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div>
                    <div className="eyebrow mb-1.5">历史区间</div>
                    <div className="tnum text-sm text-muted-foreground">
                      {data.valuation.min.toFixed(1)} ~ {data.valuation.max.toFixed(1)}
                    </div>
                    <div className="tnum text-xs text-muted-foreground">中位 {data.valuation.median.toFixed(1)}</div>
                  </div>
                  <div>
                    <div className="eyebrow mb-1.5">覆盖</div>
                    <div className="tnum text-xs text-muted-foreground">
                      {data.valuation.start} → {data.valuation.end}
                    </div>
                    <div className="tnum text-xs text-muted-foreground">{data.valuation.n} 点</div>
                  </div>
                </div>
                <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                  当前 PE 处于历史 {(data.valuation.percentile * 100).toFixed(0)} 分位——
                  <strong className="text-foreground">越低越"便宜"，但低位可以更低</strong>，这仍是历史坐标、不是买入信号。
                </p>
              </div>
            ) : (
              <div>
                <p className="mb-3 text-sm text-muted-foreground">
                  恒生科技等港股指数 PE 免费源不可得。你可以把从别处（券商/官网/付费源）拿到的
                  PE 历史**粘进来**，系统就能算真正的"贵/便宜"分位。每行一条：
                  <code className="tnum text-foreground"> 日期,PE</code>。
                </p>
                <textarea
                  value={valText}
                  onChange={(e) => setValText(e.target.value)}
                  placeholder={"2022-01-01,28.5\n2022-02-01,24.1\n2022-03-01,22.0"}
                  rows={4}
                  className="tnum w-full rounded-sm border border-input bg-background/60 p-3 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
                <div className="mt-3">
                  <Button onClick={uploadValuation} disabled={uploading} size="sm">
                    {uploading ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
                    上传 PE 数据
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
