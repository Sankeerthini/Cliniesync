// Longitudinal mother-baby timeline: one lane per care stream, trimester bands, LMP/EDD/Delivery/Today markers.
// Encodes status by SHAPE + colour (never colour alone) and every event is keyboard-focusable with a tooltip.
import { useEffect, useMemo, useRef, useState } from "react";

export interface TLEvent { lane: string; date: string; end_date?: string | null; label: string; status: string; detail: string; ref_type: string; ref_id: string }
export interface TimelineData { lanes: string[]; events: TLEvent[]; bands: { label: string; start: string; end: string }[]; markers: { date: string; label: string }[] }

const DAY = 86400000;
const t = (s: string) => new Date(s + "T00:00:00").getTime();
const LANE_H = 46, TOP = 34, LEFT = 150, BOTTOM = 52;

export const STATUS_STYLE: Record<string, { fill: string; stroke: string; shape: "dot" | "ring" | "diamond" | "square"; label: string }> = {
  completed: { fill: "#2a78d6", stroke: "#2a78d6", shape: "dot", label: "Completed / given" },
  resulted: { fill: "#2a78d6", stroke: "#2a78d6", shape: "dot", label: "Resulted" },
  given: { fill: "#2a78d6", stroke: "#2a78d6", shape: "dot", label: "Given" },
  no_show: { fill: "#fff", stroke: "#eb6834", shape: "ring", label: "No-show (documented)" },
  pending: { fill: "#fff", stroke: "#2a78d6", shape: "ring", label: "Awaiting result" },
  upcoming: { fill: "#fff", stroke: "#7b8d92", shape: "ring", label: "Upcoming" },
  due: { fill: "#fab219", stroke: "#8a5a00", shape: "diamond", label: "Due ≤ 7 days" },
  overdue: { fill: "#ec835a", stroke: "#9a3412", shape: "diamond", label: "Overdue" },
  missed: { fill: "#d03b3b", stroke: "#7f1d1d", shape: "square", label: "Missed (> 28 d)" },
  cancelled: { fill: "#c9d3d5", stroke: "#8a9a9e", shape: "square", label: "Cancelled" },
};

function Mark({ x, y, st, focus }: { x: number; y: number; st: typeof STATUS_STYLE[string]; focus: boolean }) {
  const r = focus ? 8 : 6;
  if (st.shape === "diamond") return <rect x={x - r} y={y - r} width={r * 2} height={r * 2} transform={`rotate(45 ${x} ${y})`} fill={st.fill} stroke="#fff" strokeWidth={2} />;
  if (st.shape === "square") return <rect x={x - r} y={y - r} width={r * 2} height={r * 2} rx={2} fill={st.fill} stroke="#fff" strokeWidth={2} />;
  if (st.shape === "ring") return <circle cx={x} cy={y} r={r} fill="#fff" stroke={st.stroke} strokeWidth={2.5} />;
  return <circle cx={x} cy={y} r={r} fill={st.fill} stroke="#fff" strokeWidth={2} />;
}

export function Swimlane({ data, onSelect }: { data: TimelineData; onSelect?: (e: TLEvent) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(900);
  const [hover, setHover] = useState<{ e: TLEvent; x: number; y: number } | null>(null);
  useEffect(() => {
    const el = wrap.current; if (!el) return;
    const ro = new ResizeObserver(([en]) => setW(Math.max(560, en.contentRect.width)));
    ro.observe(el); return () => ro.disconnect();
  }, []);
  const lanes = data.lanes.filter(l => data.events.some(e => e.lane === l));
  const H = TOP + lanes.length * LANE_H + BOTTOM;
  const [x0, x1] = useMemo(() => {
    const ds = [...data.events.flatMap(e => [t(e.date), e.end_date ? t(e.end_date) : t(e.date)]),
      ...data.bands.flatMap(b => [t(b.start), t(b.end)]), ...data.markers.map(m => t(m.date))];
    return [Math.min(...ds) - 10 * DAY, Math.max(...ds) + 10 * DAY];
  }, [data]);
  const sx = (d: number) => LEFT + ((d - x0) / (x1 - x0)) * (w - LEFT - 16);
  const months: number[] = [];
  const start = new Date(x0); start.setDate(1);
  for (let d = new Date(start); d.getTime() <= x1; d.setMonth(d.getMonth() + 1)) if (d.getTime() >= x0) months.push(d.getTime());
  const step = Math.ceil(months.length / Math.max(4, Math.floor((w - LEFT) / 70)));
  const bandFill = ["#e3f5f4", "#d3efed", "#c2e8e6", "#eef0fb"];

  return (
    <div ref={wrap} className="swimlane" style={{ position: "relative" }}>
      <svg width={w} height={H} role="img" aria-label="Longitudinal patient timeline">
        {data.bands.map((b, i) => (
          <g key={b.label}>
            <rect x={sx(t(b.start))} y={TOP - 6} width={Math.max(0, sx(t(b.end)) - sx(t(b.start)))} height={lanes.length * LANE_H + 6}
              fill={bandFill[i % bandFill.length]} opacity={.75} />
            <text x={sx(t(b.start)) + 6} y={TOP - 12} fontSize={11} fill="#0b5c60" fontWeight={600}>{b.label}</text>
          </g>
        ))}
        {lanes.map((l, i) => (
          <g key={l}>
            <line x1={LEFT} x2={w - 16} y1={TOP + i * LANE_H + LANE_H / 2} y2={TOP + i * LANE_H + LANE_H / 2} stroke="#d7e1e3" />
            <text x={12} y={TOP + i * LANE_H + LANE_H / 2 + 4} fontSize={12.5} fontWeight={600} fill="#2c434b">{l}</text>
          </g>
        ))}
        {months.filter((_, i) => i % step === 0).map(m => (
          <text key={m} x={sx(m)} y={TOP + lanes.length * LANE_H + 16} fontSize={11} fill="#5f7176" textAnchor="middle">
            {new Date(m).toLocaleDateString("en-GB", { month: "short", year: "2-digit" })}</text>
        ))}
        {data.markers.map(m => (
          <g key={m.label}>
            <line x1={sx(t(m.date))} x2={sx(t(m.date))} y1={TOP - 4} y2={TOP + lanes.length * LANE_H} stroke={m.label === "Today" ? "#5b3fd6" : "#0f7c80"} strokeWidth={1.5} />
            <line x1={sx(t(m.date))} x2={sx(t(m.date))} y1={TOP + lanes.length * LANE_H} y2={H - 18} stroke={m.label === "Today" ? "#5b3fd6" : "#0f7c80"} strokeWidth={1.5} opacity={.5} />
            <rect x={sx(t(m.date)) - 26} y={H - 20} width={52} height={16} rx={8} fill={m.label === "Today" ? "#5b3fd6" : "#0f7c80"} />
            <text x={sx(t(m.date))} y={H - 8.5} fontSize={10.5} fill="#fff" textAnchor="middle" fontWeight={600}>{m.label}</text>
          </g>
        ))}
        {data.events.map((e, i) => {
          const li = lanes.indexOf(e.lane); if (li < 0) return null;
          const y = TOP + li * LANE_H + LANE_H / 2, x = sx(t(e.date));
          const st = STATUS_STYLE[e.status] || STATUS_STYLE.completed;
          const focus = hover?.e === e;
          return (
            <g key={i} tabIndex={0} role="button" aria-label={`${e.label}, ${e.date}, ${st.label}`} style={{ cursor: "pointer", outline: "none" }}
              onMouseEnter={() => setHover({ e, x, y })} onMouseLeave={() => setHover(null)}
              onFocus={() => setHover({ e, x, y })} onBlur={() => setHover(null)} onClick={() => onSelect?.(e)}
              onKeyDown={k => k.key === "Enter" && onSelect?.(e)}>
              {e.end_date && <line x1={x} x2={sx(t(e.end_date))} y1={y} y2={y} stroke={st.stroke} strokeWidth={3} strokeLinecap="round" opacity={.35} />}
              <circle cx={x} cy={y} r={13} fill="transparent" />
              <Mark x={x} y={y} st={st} focus={focus} />
            </g>
          );
        })}
      </svg>
      {hover && (
        <div className="viz-tip floating" style={{ left: Math.min(hover.x + 12, w - 260), top: hover.y + 14 }}>
          <div className="viz-tip-x">{hover.e.label}</div>
          <div><strong>{new Date(hover.e.date + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}</strong>
            <span className="muted"> · {(STATUS_STYLE[hover.e.status] || STATUS_STYLE.completed).label}</span></div>
          <div className="small muted" style={{ marginTop: 4 }}>{hover.e.detail}</div>
        </div>
      )}
      <div className="viz-legend" style={{ marginTop: 6 }}>
        {["completed", "no_show", "pending", "upcoming", "due", "overdue", "missed"].map(k => (
          <span key={k}><svg width={18} height={18}><Mark x={9} y={9} st={STATUS_STYLE[k]} focus={false} /></svg>{STATUS_STYLE[k].label}</span>
        ))}
      </div>
    </div>
  );
}
