// Renders backend chart specs with Recharts, following the data-viz mark specs:
// bars <= 24px with 4px rounded data-ends, 2px surface gaps, 2px lines, >= 8px markers with surface ring,
// hairline solid grid, legend for >= 2 series, value-first tooltips, and a table view for every chart.
import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Info, Table2 } from "lucide-react";
import type { ChartSpec } from "../api/client";
import { DataTable } from "../ui/components";

export const CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"];
export const ORDINAL = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"];
const ORDINAL_IDS = new Set(["anc_funnel", "backlog", "immunization", "pnc"]);
const SURFACE = "#ffffff";
const GRID = "#e8ecec";
const AXIS_INK = "#5f7176";

export function fmtValue(v: unknown, f?: string) {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  const n = Number(v);
  if (f === "pct") return `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
  if (f === "int") return Math.round(n).toLocaleString();
  return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
}
const compact = (v: number, f?: string) => f === "pct" ? `${v}%` : Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}K` : `${v}`;

function colorsFor(spec: ChartSpec) {
  if (ORDINAL_IDS.has(spec.id)) {
    const n = spec.series.length;
    if (n === 1) return [ORDINAL[2]];
    return spec.series.map((_, i) => ORDINAL[Math.min(ORDINAL.length - 1, i + (4 - n))]);
  }
  return spec.series.map((_, i) => CATEGORICAL[i % CATEGORICAL.length]);
}

function ValueTooltip({ active, payload, label, f, kind }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="viz-tip">
      <div className="viz-tip-x">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="viz-tip-row">
          <span className="viz-key" style={{ background: p.color, height: kind === "line" ? 2 : 8, borderRadius: kind === "line" ? 2 : 2 }} />
          <strong>{fmtValue(p.value, f)}</strong><span className="muted">{p.name}</span>
        </div>
      ))}
    </div>
  );
}

function Legend({ spec, colors, kind }: { spec: ChartSpec; colors: string[]; kind: "bar" | "line" }) {
  if (spec.series.length < 2) return null;
  return (
    <div className="viz-legend">
      {spec.series.map((s, i) => (
        <span key={s.key}><span className="viz-key" style={{ background: colors[i], height: kind === "line" ? 2 : 10,
          width: kind === "line" ? 16 : 10 }} />{s.label}</span>
      ))}
    </div>
  );
}

export function Chart({ spec, height = 260 }: { spec: ChartSpec; height?: number }) {
  const colors = colorsFor(spec);
  const f = spec.value_format;
  const data = spec.data as any[];
  if (!data?.length) return <div className="empty">No data for this period</div>;
  const axisProps = { tick: { fill: AXIS_INK, fontSize: 12 }, tickLine: false, axisLine: { stroke: "#c9d3d5" } } as const;

  if (spec.type === "line") {
    const last = data.length - 1;
    return (<>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 16, right: 44, left: 0, bottom: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey={spec.x} {...axisProps} minTickGap={18} />
          <YAxis {...axisProps} axisLine={false} width={44} tickFormatter={(v) => compact(v, f)}
            domain={f === "pct" ? [0, (dataMax: number) => Math.min(100, Math.ceil((dataMax + 5) / 10) * 10)] : ["auto", "auto"]} />
          <Tooltip content={<ValueTooltip f={f} kind="line" />} cursor={{ stroke: "#9fb3b7", strokeWidth: 1 }} />
          {spec.series.map((s, i) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={colors[i]} strokeWidth={2}
              dot={{ r: 4, fill: colors[i], stroke: SURFACE, strokeWidth: 2 }} activeDot={{ r: 6, stroke: SURFACE, strokeWidth: 2 }}
              isAnimationActive={false} connectNulls>
              <LabelList dataKey={s.key} content={(p: any) => p.index === last ? (
                <text x={p.x + 8} y={p.y + 4} fontSize={12} fontWeight={600} fill="#2c434b">{fmtValue(p.value, f)}</text>) : null} />
            </Line>
          ))}
        </LineChart>
      </ResponsiveContainer>
      <Legend spec={spec} colors={colors} kind="line" />
    </>);
  }

  const horizontal = spec.type === "hbar" || spec.type === "stacked_hbar" || spec.type === "funnel";
  const stacked = spec.type === "stacked_bar" || spec.type === "stacked_hbar";
  const single = spec.series.length === 1;
  const h = horizontal ? Math.max(height, data.length * 34 + 40) : height;
  const labelW = horizontal ? Math.min(220, Math.max(64, Math.max(...data.map(d => String(d[spec.x]).length)) * 7 + 16)) : 0;
  return (<>
    <ResponsiveContainer width="100%" height={h}>
      <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"} barCategoryGap="28%"
        margin={{ top: 16, right: horizontal ? 52 : 8, left: 0, bottom: 4 }}>
        <CartesianGrid stroke={GRID} vertical={horizontal} horizontal={!horizontal} />
        {horizontal ? (<>
          <XAxis type="number" {...axisProps} axisLine={false} allowDecimals={f !== "int"} tickFormatter={(v) => compact(v, f)}
            domain={f === "pct" ? [0, 100] : [0, "auto"]} />
          <YAxis type="category" dataKey={spec.x} {...axisProps} width={labelW} interval={0} />
        </>) : (<>
          <XAxis dataKey={spec.x} {...axisProps} interval={data.length > 14 ? "preserveStartEnd" : 0} minTickGap={6} />
          <YAxis {...axisProps} axisLine={false} width={44} allowDecimals={f !== "int"} tickFormatter={(v) => compact(v, f)}
            domain={f === "pct" ? [0, 100] : [0, "auto"]} />
        </>)}
        <Tooltip content={<ValueTooltip f={f} kind="bar" />} cursor={{ fill: "rgba(15,124,128,.06)" }} />
        {spec.series.map((s, i) => {
          const isTop = !stacked || i === spec.series.length - 1;
          const radius: [number, number, number, number] = isTop ? (horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]) : [0, 0, 0, 0];
          return (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={colors[i]} stackId={stacked ? "s" : undefined}
              maxBarSize={24} radius={radius} stroke={stacked ? SURFACE : undefined} strokeWidth={stacked ? 2 : 0}
              isAnimationActive={false}>
              {single && data.length <= 14 && (
                <LabelList dataKey={s.key} position={horizontal ? "right" : "top"} formatter={(v: number) => fmtValue(v, f)}
                  style={{ fill: "#2c434b", fontSize: 12, fontWeight: 600 }} />)}
            </Bar>
          );
        })}
      </BarChart>
    </ResponsiveContainer>
    <Legend spec={spec} colors={colors} kind="bar" />
  </>);
}

export function ChartCard({ spec, definition, caveat, height }: { spec: ChartSpec; definition?: string | null; caveat?: string; height?: number }) {
  const [table, setTable] = useState(false);
  const cols = [{ key: spec.x, label: spec.x.replace(/_/g, " ") }, ...spec.series.map(s => ({ key: s.key, label: s.label }))];
  return (
    <div className="card chart-card fade-in">
      <div className="card-head">
        <div><h3>{spec.title}</h3>{spec.subtitle && <div className="sub">{spec.subtitle}</div>}</div>
        <span className="spacer" />
        {definition && <span className="def-tip" tabIndex={0} aria-label={definition}><Info size={16} /><span className="def-pop">{definition}</span></span>}
        <button className="btn ghost sm" onClick={() => setTable(t => !t)} aria-pressed={table}><Table2 size={15} />{table ? "Chart" : "Table"}</button>
      </div>
      {table ? <DataTable columns={cols} rows={spec.data} /> : <Chart spec={spec} height={height} />}
      {caveat && <p className="tiny muted" style={{ marginTop: 8 }}>{caveat}</p>}
    </div>
  );
}
