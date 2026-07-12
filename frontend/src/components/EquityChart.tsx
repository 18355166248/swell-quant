import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface EquityPoint {
  date: string;
  equity: number;
}

/** 净值曲线：从 1.0 开始的复利净值（已扣成本）。琥珀线 + 面积渐变，配仪表盘主题。 */
export function EquityChart({ data }: { data: EquityPoint[] }) {
  const accent = "hsl(38 82% 58%)";
  const border = "hsl(222 12% 16%)";
  const muted = "hsl(40 6% 56%)";
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
        <defs>
          <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity={0.28} />
            <stop offset="100%" stopColor={accent} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={border} strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: muted, fontSize: 10, fontFamily: "IBM Plex Mono" }}
          tickLine={false}
          axisLine={{ stroke: border }}
          minTickGap={48}
        />
        <YAxis
          tick={{ fill: muted, fontSize: 10, fontFamily: "IBM Plex Mono" }}
          tickLine={false}
          axisLine={false}
          width={44}
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => v.toFixed(2)}
        />
        <Tooltip
          contentStyle={{
            background: "hsl(222 16% 9%)",
            border: `1px solid ${border}`,
            borderRadius: 6,
            fontFamily: "IBM Plex Mono",
            fontSize: 12,
          }}
          labelStyle={{ color: muted }}
          formatter={(v: number) => [v.toFixed(4), "净值"]}
        />
        <Area
          type="monotone"
          dataKey="equity"
          stroke={accent}
          strokeWidth={1.8}
          fill="url(#eq)"
          dot={false}
          animationDuration={600}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
