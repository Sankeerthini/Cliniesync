// KPIs & pilot plan: one primary operational KPI with baseline vs pilot, secondary KPIs, AI quality & safety,
// a time-motion stopwatch for the "time-to-information" KPI, and the 60-90 day pilot plan.
import { useEffect, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowDownRight, ArrowUpRight, Pause, Play, ShieldCheck, Target, Timer } from "lucide-react";
import { api } from "../../api/client";
import { Card3D, ErrorNote, Loading, Seg, useAsync } from "../../ui/components";

interface W { value: number | null; n: number; window: string[] }
interface KPI {
  reference_date: string; go_live: string;
  primary: { name: string; definition: string; baseline: W; pilot: W; delta_pp: number | null; target: string; series: { month: string; value: number; n: number }[]; data_note: string };
  secondary: any[]; ai_quality: Record<string, number | null>; safety: { blocked_total: number; blocked_by_category: Record<string, number>; wrong_block_reports: number; block_rate_pct: number | null };
  reminders: Record<string, number>;
}

// The problem each KPI addresses, with the published evidence (moved here from the home page).
const PROBLEMS = [
  { tag: "Fragmented clinical information", problem: "Information is present, but not readily usable",
    evidence: "Conventional EHR search produces false positives/negatives and needs substantial cognitive effort.", ref: "Hill et al., Appl Clin Inform 2021",
    solution: "Ask instead of search", how: "Natural-language queries retrieve the relevant records, visits, investigations and documented follow-ups." },
  { tag: "Operational overload", problem: "Clinicians spend bandwidth navigating the record",
    evidence: "Physician documentation time rose from 16% to 28% of observed work time after EHR implementation.", ref: "Baumann et al., Health Policy 2018",
    solution: "Summarize instead of reconstruct", how: "Fragmented records become a traceable timeline and a cited summary." },
  { tag: "Care coordination gaps", problem: "Maternal care is longitudinal and multi-provider",
    evidence: "Coordinated care is an important organisational element of continuity in perinatal care.", ref: "Baart et al., Midwifery 2025",
    solution: "Coordinate instead of chase", how: "One shared operational layer for doctors, coordinators and administrators." },
  { tag: "Care coordination gaps", problem: "A missed follow-up is a missed opportunity for care",
    evidence: "Text notifications: 23% more likely to attend, 25% less likely to no-show; SMS can raise ANC attendance.", ref: "Robotham et al., BMJ Open 2016; Wagnew et al., Reprod Health 2018",
    solution: "Prompt instead of depend on memory", how: "Documented pending follow-ups become multilingual prompts - sent only after human approval." },
];

const PLAN = [
  { w: "Weeks 0-2", t: "Set-up & baseline", d: "Sign data-sharing/IRB approvals, connect to the clinic's existing exports (HMIS CSV, Excel register, lab PDFs), freeze the KPI definitions, extract 90-day baseline for recall completion and no-show; time-motion baseline of manual chart review (20 tasks)." },
  { w: "Weeks 2-4", t: "Go-live at 1 PHC", d: "1 doctor + 1 care coordinator; daily follow-up queue; reminders in Kannada/Hindi/Bengali via SMS/WhatsApp after human approval; weekly safety review of blocked/flagged requests." },
  { w: "Weeks 4-10", t: "Iterate & extend", d: "Weekly KPI review; fix wrong blocks & template wording with ANMs; add second facility; native-speaker review of every template; audit-trail spot checks." },
  { w: "Weeks 10-13", t: "Evaluate", d: "Compare pilot vs baseline (recall completion, no-show, handoff lag, time-to-information); user interviews (SUS); decision on scale-up, with the safety and privacy review required for clinical use." },
];

export function KpiPage() {
  const k = useAsync(() => api.get<KPI>("/api/kpi"), []);
  if (k.error) return <div className="page"><ErrorNote error={k.error} /></div>;
  if (!k.data) return <div className="page"><Loading /></div>;
  const p = k.data.primary;
  const [ns, lag, tti] = k.data.secondary;
  return (
    <div className="page kpi">
      <div className="page-head"><div><div className="eyebrow">Measurable impact · pilot evidence in 60-90 days</div><h2>KPIs &amp; pilot plan</h2>
        <p>One primary operational KPI, measured the same way before and after go-live. Demo go-live: {k.data.go_live} (baseline = the 90 days before).</p></div></div>

      <Card3D className="kpi-hero" tilt={3}>
        <div className="kpi-hero-grid">
          <div>
            <span className="badge brand"><Target size={13} />Primary KPI</span>
            <h2 style={{ marginTop: 8 }}>{p.name}</h2>
            <p className="small muted" style={{ marginTop: 6 }}>{p.definition}</p>
            <div className="kpi-compare">
              <div><span>Baseline</span><b>{p.baseline.value ?? "-"}%</b><small>n = {p.baseline.n} · {p.baseline.window.join(" → ")}</small></div>
              <div><span>Pilot window</span><b>{p.pilot.value ?? "-"}%</b><small>n = {p.pilot.n} · {p.pilot.window.join(" → ")}</small></div>
              <div><span>Change</span><b className={p.delta_pp !== null && p.delta_pp >= 0 ? "up" : "down"}>
                {p.delta_pp !== null && (p.delta_pp >= 0 ? <ArrowUpRight size={22} /> : <ArrowDownRight size={22} />)}{p.delta_pp ?? "-"} pp</b><small>Target: {p.target}</small></div>
            </div>
            <div className="callout warn" style={{ marginTop: 12 }}>{p.data_note}</div>
          </div>
          <div className="card" style={{ padding: 12 }}>
            <h3>Monthly on-time completion</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={p.series} margin={{ top: 18, right: 24, left: -10, bottom: 0 }}>
                <CartesianGrid stroke="#e8ecec" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#5f7176" }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#5f7176" }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
                <Tooltip formatter={(v: number, _n, item: any) => [`${v}% (n=${item.payload.n})`, "On time"]} />
                <ReferenceLine x={k.data.go_live.slice(0, 7)} stroke="#5b3fd6" label={{ value: "go-live", position: "top", fill: "#5b3fd6", fontSize: 11 }} />
                <Line dataKey="value" stroke="#2a78d6" strokeWidth={2} dot={{ r: 4, fill: "#2a78d6", stroke: "#fff", strokeWidth: 2 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </Card3D>

      <div className="grid g3" style={{ marginTop: 18 }}>
        <div className="card"><h3>{ns.name}</h3><p className="tiny muted">{ns.definition}</p>
          <div className="kpi-mini"><div><span>Baseline</span><b>{ns.baseline.value ?? "-"}%</b></div><div><span>Pilot</span><b>{ns.pilot.value ?? "-"}%</b></div></div>
          <p className="tiny muted">Lower is better · n = {ns.baseline.n} / {ns.pilot.n} booked ANC visits</p></div>
        <div className="card"><h3>{lag.name}</h3><p className="tiny muted">{lag.definition}</p>
          <div className="kpi-mini"><div><span>Median</span><b>{lag.value ?? "-"}{lag.value !== null && " d"}</b></div><div><span>Contacts logged</span><b>{lag.n}</b></div></div></div>
        <div className="card"><h3>{tti.name}</h3><p className="tiny muted">{tti.definition}</p>
          <div className="kpi-mini"><div><span>Manual (median)</span><b>{tti.manual ?? "-"}{tti.manual !== null && " s"}</b></div>
            <div><span>ClinieSync (median)</span><b>{tti.cliniesync ?? "-"}{tti.cliniesync !== null && " s"}</b></div></div>
          <p className="tiny muted">System latency (median): {tti.system_latency_ms ?? "-"} ms</p></div>
      </div>

      <div className="grid g2" style={{ marginTop: 18 }}>
        <Stopwatch onSaved={k.reload} />
        <div className="card">
          <h3><ShieldCheck size={16} /> AI quality &amp; safety (live from audit data)</h3>
          <div className="kpi-mini four">
            <div><span>Answers</span><b>{k.data.ai_quality.answers}</b></div>
            <div><span>Verified</span><b>{k.data.ai_quality.verified_pct ?? "-"}%</b></div>
            <div><span>Edited</span><b>{k.data.ai_quality.edited_pct ?? "-"}%</b></div>
            <div><span>Rejected</span><b>{k.data.ai_quality.rejected_pct ?? "-"}%</b></div>
            <div><span>Requests blocked</span><b>{k.data.safety.blocked_total}</b></div>
            <div><span>Block rate</span><b>{k.data.safety.block_rate_pct ?? "-"}%</b></div>
            <div><span>“Wrong block” reports</span><b>{k.data.safety.wrong_block_reports}</b></div>
            <div><span>Reminders sent</span><b>{k.data.reminders.sent || 0}</b></div>
          </div>
        </div>
      </div>

      <section style={{ marginTop: 26 }}>
        <h3 className="section-title">60-90 day pilot plan</h3>
        <div className="plan">{PLAN.map((s, i) => (
          <Card3D key={s.w} className="plan-step" tilt={4}><span className="plan-n lift">{i + 1}</span><span className="eyebrow">{s.w}</span><h3>{s.t}</h3><p className="small">{s.d}</p></Card3D>))}</div>
        <p className="small muted" style={{ marginTop: 10 }}>Success criteria: +10 pp on-time follow-up completion vs baseline, no increase in safety incidents (zero clinical-advice outputs in audit), ≥ 80 % of answers verified without edits, ≥ 50 % reduction in time-to-information.</p>
      </section>

      <section style={{ marginTop: 30 }}>
        <h3 className="section-title">Why it matters <span className="tiny muted">· hover or focus a card</span></h3>
        <div className="grid g4">
          {PROBLEMS.map(p => (
            <div className="flip" tabIndex={0} key={p.solution}>
              <div className="flip-inner">
                <div className="flip-face front">
                  <span className="badge warn">{p.tag}</span>
                  <h3>{p.problem}</h3>
                  <p className="small">{p.evidence}</p>
                  <p className="tiny muted">{p.ref}</p>
                </div>
                <div className="flip-face back">
                  <span className="badge brand">ClinieSync</span>
                  <h3>{p.solution}</h3>
                  <p className="small">{p.how}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Stopwatch({ onSaved }: { onSaved: () => void }) {
  const [method, setMethod] = useState<"manual" | "cliniesync">("manual");
  const [task, setTask] = useState("Show the patient's last 3 visits");
  const [secs, setSecs] = useState(0); const [running, setRunning] = useState(false); const [saved, setSaved] = useState<string | null>(null);
  const t0 = useRef(0);
  useEffect(() => { if (!running) return; const id = setInterval(() => setSecs((Date.now() - t0.current) / 1000), 100); return () => clearInterval(id); }, [running]);
  const save = async () => {
    if (!secs) return;
    await api.post("/api/kpi/timing", { task, method, seconds: Math.round(secs * 10) / 10 });
    setSaved(`Saved ${secs.toFixed(1)} s (${method})`); setSecs(0); onSaved();
  };
  return (
    <div className="card">
      <h3><Timer size={16} /> Time-motion logger</h3>
      <p className="tiny muted" style={{ margin: "4px 0 10px" }}>Time the same standard question answered by manual chart review and by ClinieSync (including verification).</p>
      <div className="col">
        <select className="input" value={task} onChange={e => setTask(e.target.value)} aria-label="Task">
          {["Show the patient's last 3 visits", "Summarize the pregnancy journey", "Find patients with pending follow-ups", "Monthly MCH visit count", "Pending investigation results"].map(t => <option key={t}>{t}</option>)}</select>
        <Seg value={method} onChange={setMethod} options={[{ value: "manual", label: "Manual chart review" }, { value: "cliniesync", label: "With ClinieSync" }]} />
        <div className="stopwatch"><b className="num">{secs.toFixed(1)} s</b>
          <button className="btn" onClick={() => { if (running) setRunning(false); else { t0.current = Date.now() - secs * 1000; setRunning(true); setSaved(null); } }}>
            {running ? <><Pause size={15} />Stop</> : <><Play size={15} />Start</>}</button>
          <button className="btn primary" disabled={running || !secs} onClick={save}>Save timing</button></div>
        {saved && <div className="callout ok">{saved}</div>}
      </div>
    </div>
  );
}
