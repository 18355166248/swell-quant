import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";

/** 指标卡：小标签 + 等宽大数字，可按正负着色。 */
export function MetricCard({
  label,
  value,
  tone = "neutral",
  sub,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "pos" | "neg" | "accent";
  sub?: string;
}) {
  return (
    <Card className="p-4">
      <div className="eyebrow mb-2">{label}</div>
      <div
        className={cn(
          "tnum text-2xl font-medium leading-none",
          tone === "pos" && "text-pos",
          tone === "neg" && "text-neg",
          tone === "accent" && "text-accent",
        )}
      >
        {value}
      </div>
      {sub && <div className="tnum mt-1.5 text-xs text-muted-foreground">{sub}</div>}
    </Card>
  );
}
