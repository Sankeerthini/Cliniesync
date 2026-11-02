// Small multiples of recorded measurements - one panel per measure, own y-scale, NO reference ranges or
// colour-coding (ClinieSync shows documented values; interpretation stays with the clinician).
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface Series { code: string; display: string; unit: string | null; points: { date: string; value: number; visit_type: string; ga_weeks: number | null }[] }
const ORDER = ["hemoglobin", "weight", "bp_systolic", "bp_diastolic", "fundal_height", "fetal_heart_rate", "infant_weight"];
const NAMES: Record<string, string> = { hemoglobin: "Haemoglobin", weight: "Weight", bp_systolic: "Systolic BP", bp_diastolic: "Diastolic BP",
  fundal_height: "Fundal height", fetal_heart_rate: "Fetal heart rate", infant_weight: "Infant weight" };
const UNITS: Record<string, string> = { hemoglobin: "g/dL", weight: "kg", bp_systolic: "mmHg", bp_diastolic: "mmHg", fundal_height: "cm",
  fetal_heart_rate: "/min", infant_weight: "kg" };

function Tip({ active, payload, unit }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return <div className="viz-tip"><div className="viz-tip-x">{p.date}{p.ga_weeks ? ` · GA ${p.ga_weeks} w` : ""}</div>
    <div><strong>{p.value} {unit}</strong> <span className="muted">{p.visit_type}</span></div></div>;
}

export function MeasureMultiples({ series }: { series: Record<string, Series> }) {
  const codes = ORDER.filter(c => series[c]?.points?.length);
  if (!codes.length) return <div className="empty">No recorded measurements</div>;
  return (
    <div className="multiples">
      {codes.map(c => {
        const pts = series[c].points; const last = pts[pts.length - 1];
        const unit = series[c].unit || UNITS[c] || "";
        return (
          <div key={c} className="multiple card">
            <div className="row" style={{ gap: 6 }}><b>{NAMES[c] || series[c].display}</b><span className="tiny muted">{unit}</span><span className="spacer" />
              <span className="small"><b>{last.value}</b> <span className="muted tiny">latest</span></span></div>
            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={pts} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="#eef1f1" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#5f7176" }} tickLine={false} axisLine={{ stroke: "#c9d3d5" }}
                  tickFormatter={(d: string) => new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short" })} minTickGap={20} />
                <YAxis tick={{ fontSize: 10, fill: "#5f7176" }} tickLine={false} axisLine={false} domain={["auto", "auto"]} width={42} />
                <Tooltip content={<Tip unit={unit} />} cursor={{ stroke: "#9fb3b7" }} />
                <Line dataKey="value" stroke="#2a78d6" strokeWidth={2} dot={{ r: 4, fill: "#2a78d6", stroke: "#fff", strokeWidth: 2 }}
                  activeDot={{ r: 6 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>);
      })}
      <p className="tiny muted" style={{ gridColumn: "1 / -1" }}>Values exactly as documented at each visit. No reference ranges or flags are shown - interpretation stays with the treating clinician.</p>
    </div>
  );
}
