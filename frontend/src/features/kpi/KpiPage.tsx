// KPIs & pilot plan: one primary operational KPI (baseline -> pilot -> target, monthly trend), three secondary KPIs,
// AI quality & safety from the audit data, a time-motion stopwatch for "time-to-information", and the 60-90 day pilot plan.
import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  ArrowDownRight, ArrowRight, ArrowUpRight, CheckCircle2, Clock, Gauge, Info, Pause, Play, RotateCcw, ShieldCheck, Sparkles, Target, Timer, UserCheck,
} from "lucide-react";
import { api } from "../../api/client";
import { ErrorNote, Loading, Seg, useAsync, useCountUp } from "../../ui/components";

interface W { value: number | null; n: number; window: string[] }
interface KPI {
  reference_date: string; go_live: string;
  primary: { name: string; definition: string; baseline: W; pilot: W; delta_pp: number | null; target: string; series: { month: string; value: number; n: number }[]; data_note: string };
  secondary: any[];
  ai_quality: { answers: number; reviewed?: number; verified_pct: number | null; edited_pct: number | null; rejected_pct: number | null; median_review_seconds?: number | null; llm_share_pct?: number | null };
  safety: { blocked_total: number; blocked_by_category: Record<string, number>; wrong_block_reports: number; block_rate_pct: number | null };
  reminders: Record<string, number>;
}

// The problem each KPI addresses, with the published evidence.
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
const SUCCESS = ["+10 pp on-time follow-up completion vs baseline", "No increase in safety incidents (zero clinical-advice outputs in audit)",
  "≥ 80% of answers verified without edits", "≥ 50% reduction in time-to-information"];

const BLOCK_LABEL: Record<string, string> = { diagnosis: "Diagnosis", treatment_prescription: "Treatment / dosing", clinical_advice: "Clinical advice",
  risk_scoring: "Risk scoring", prompt_injection: "Prompt injection", bulk_data_export: "Bulk export", out_of_scope: "Out of scope", access: "Access" };

const shortDate = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const span = (w: string[]) => w.length === 2 ? `${shortDate(w[0])} – ${shortDate(w[1])}` : "";
const monthLabel = (m: string) => new Date(m + "-01T00:00:00").toLocaleDateString("en-GB", { month: "short", year: "2-digit" });

function Num({ v, unit }: { v: number | null | undefined; unit?: string }) {
  const shown = useCountUp(v ?? null);
  return <>{shown ?? "-"}{unit && v != null && <small>{unit}</small>}</>;
}

function Delta({ v, good, unit = "pp", label }: { v: number | null; good: "up" | "down"; unit?: string; label?: string }) {
  if (v === null || v === undefined) return null;
  const better = good === "up" ? v >= 0 : v <= 0;
  return <span className={`delta ${better ? "good" : "bad"}`}>{v >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
    {v > 0 ? "+" : ""}{v.toFixed(1)} {unit}{label && <em>{label}</em>}</span>;
}

// baseline -> pilot -> target on a scale zoomed to the range that matters (so a 1-point change is still visible)
function TargetBar({ baseline, pilot, target }: { baseline: number; pilot: number; target: number }) {
  const from = Math.max(0, Math.floor((Math.min(baseline, pilot, target) - 8) / 5) * 5);
  const to = Math.min(100, Math.ceil((Math.max(baseline, pilot, target) + 8) / 5) * 5);
  const at = (v: number) => `${((v - from) / (to - from)) * 100}%`;
  const lo = Math.min(baseline, pilot), hi = Math.max(baseline, pilot);
  return (
    <div className="tbar" aria-label={`Baseline ${baseline}%, pilot ${pilot}%, target ${target}%`}>
      <div className="tbar-track">
        <span className="tbar-goal" style={{ left: at(hi), width: `calc(${at(target)} - ${at(hi)})` }} />
        <span className="tbar-range" style={{ left: at(lo), width: `max(4px, calc(${at(hi)} - ${at(lo)}))` }} />
        <span className="tbar-mark base" style={{ left: at(baseline) }}><i />Baseline</span>
        <span className="tbar-mark pilot" style={{ left: at(pilot) }}><i />Pilot</span>
        <span className="tbar-mark target" style={{ left: at(target) }}><i />Target {target.toFixed(0)}%</span>
      </div>
      <div className="tbar-scale"><span>{from}%</span><span>{Math.round((from + to) / 2)}%</span><span>{to}%</span></div>
    </div>
  );
}

function TrendTip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return <div className="viz-tip"><div className="viz-tip-x">{monthLabel(d.month)}</div>
    <div className="viz-tip-row"><strong>{d.value}%</strong><span className="muted">on time · n = {d.n}</span></div></div>;
}

// two bars on a shared scale (e.g. baseline vs pilot, manual vs ClinieSync)
function Pair({ a, b, unit }: { a: { label: string; v: number | null }; b: { label: string; v: number | null }; unit: string }) {
  const max = Math.max(a.v || 0, b.v || 0, 0.0001);
  return (
    <div className="pair">
      {[a, b].map((x, i) => (
        <div key={x.label} className={`pair-row ${i ? "second" : ""}`}>
          <span className="pair-label">{x.label}</span>
          <span className="pair-track"><span style={{ width: `${((x.v || 0) / max) * 100}%` }} /></span>
          <b className="num">{x.v ?? "-"}{x.v != null && unit}</b>
        </div>))}
    </div>
  );
}

export function KpiPage() {
  const k = useAsync(() => api.get<KPI>("/api/kpi"), []);
  if (k.error) return <div className="page"><ErrorNote error={k.error} /></div>;
  if (!k.data) return <div className="page"><Loading label="Loading KPIs" /></div>;
  const p = k.data.primary, q = k.data.ai_quality, sf = k.data.safety;
  const [ns, lag, tti] = k.data.secondary;
  const target = (p.baseline.value ?? 0) + 10;
  const goLive = k.data.go_live.slice(0, 7);
  const last = p.series[p.series.length - 1]?.month;
  const ratio = tti.manual && tti.cliniesync ? tti.manual / tti.cliniesync : null;
  const reviewedTotal = (q.verified_pct ?? 0) + (q.edited_pct ?? 0) + (q.rejected_pct ?? 0);
  const blocks = Object.entries(sf.blocked_by_category).sort((a, b) => b[1] - a[1]);
  const blockMax = Math.max(1, ...blocks.map(b => b[1]));

  return (
    <div className="page kpi">
      <div className="page-head"><div><div className="eyebrow">Measurable impact · pilot evidence in 60-90 days</div><h2>KPIs &amp; pilot</h2>
        <p>One primary operational KPI, measured the same way before and after go-live. Demo go-live {shortDate(k.data.go_live)} 2026 - the baseline is the 90 days before it.</p></div></div>

      {/* primary KPI */}
      <section className="kpi-hero">
        <div className="kpi-hero-copy">
          <span className="kpi-tag"><Target size={14} />Primary KPI</span>
          <h3>{p.name}</h3>
          <p className="kpi-def">{p.definition}</p>
          <div className="kpi-figures">
            <div><span>Baseline</span><b className="num"><Num v={p.baseline.value} unit="%" /></b><small>{span(p.baseline.window)} · n = {p.baseline.n}</small></div>
            <ArrowRight className="kpi-arrow" size={20} />
            <div className="accent"><span>Pilot window</span><b className="num"><Num v={p.pilot.value} unit="%" /></b><small>{span(p.pilot.window)} · n = {p.pilot.n}</small></div>
          </div>
          <div className="kpi-delta-row"><Delta v={p.delta_pp} good="up" label="vs baseline" /><span className="muted small">Target: {p.target}</span></div>
          {p.baseline.value != null && p.pilot.value != null && <TargetBar baseline={p.baseline.value} pilot={p.pilot.value} target={target} />}
          <p className="kpi-note"><Info size={14} />{p.data_note}</p>
        </div>
        <div className="kpi-hero-chart">
          <div className="kpi-chart-head"><b>Monthly on-time completion</b>
            <span className="kpi-legend"><i className="l-pilot" />Pilot window<i className="l-target" />Target</span></div>
          <div className="kpi-chart-body"><ResponsiveContainer width="100%" height="100%">
            <AreaChart data={p.series} margin={{ top: 16, right: 12, left: -16, bottom: 0 }}>
              <defs><linearGradient id="kpi-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#14a3a0" stopOpacity={.32} /><stop offset="1" stopColor="#14a3a0" stopOpacity={0} /></linearGradient></defs>
              <CartesianGrid stroke="#e8ecec" vertical={false} />
              {last && <ReferenceArea x1={goLive} x2={last} fill="#5b3fd6" fillOpacity={.06} />}
              <XAxis dataKey="month" tickFormatter={monthLabel} tick={{ fontSize: 11, fill: "#5f7176" }} tickLine={false} axisLine={false} minTickGap={18} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#5f7176" }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
              <ReferenceLine y={target} stroke="#eb6834" strokeDasharray="5 5" />
              <ReferenceLine x={goLive} stroke="#5b3fd6" strokeWidth={1.5} label={{ value: "go-live", position: "insideTopRight", fill: "#5b3fd6", fontSize: 11, fontWeight: 600 }} />
              <Tooltip content={<TrendTip />} cursor={{ stroke: "#94a9ad", strokeDasharray: "3 3" }} />
              <Area dataKey="value" type="monotone" stroke="#0f7c80" strokeWidth={2.5} fill="url(#kpi-fill)"
                dot={{ r: 3.5, fill: "#0f7c80", stroke: "#fff", strokeWidth: 2 }} activeDot={{ r: 6, stroke: "#fff", strokeWidth: 2 }} animationDuration={900} />
            </AreaChart>
          </ResponsiveContainer></div>
        </div>
      </section>

      {/* secondary KPIs - one story each */}
      <div className="kpi-row">
        <article className="kpi-card">
          <header><span className="kc-icon tone-coral"><Gauge size={17} /></span><h4>{ns.name}</h4></header>
          <div className="kc-big num"><Num v={ns.pilot.value} unit="%" /><Delta v={ns.pilot.value != null && ns.baseline.value != null ? +(ns.pilot.value - ns.baseline.value).toFixed(1) : null} good="down" /></div>
          <Pair a={{ label: "Baseline", v: ns.baseline.value }} b={{ label: "Pilot", v: ns.pilot.value }} unit="%" />
          <p className="kc-foot">Lower is better · n = {ns.baseline.n} / {ns.pilot.n} booked ANC visits</p>
        </article>
        <article className="kpi-card">
          <header><span className="kc-icon tone-blue"><Clock size={17} /></span><h4>{lag.name}</h4></header>
          <div className="kc-big num"><Num v={lag.value} unit=" d" /><span className="kc-chip">median</span></div>
          <p className="kc-def">{lag.definition}</p>
          <p className="kc-foot">{lag.n} contacts logged so far</p>
        </article>
        <article className="kpi-card">
          <header><span className="kc-icon tone-violet"><Timer size={17} /></span><h4>{tti.name}</h4></header>
          <div className="kc-big num">{ratio ? <>{ratio >= 1 ? ratio.toFixed(1) : (1 / ratio).toFixed(1)}<small>×</small>
            <span className={`kc-chip ${ratio >= 1 ? "good" : "bad"}`}>{ratio >= 1 ? "faster with ClinieSync" : "slower so far"}</span></> : <span className="kc-empty">Log a timing below</span>}</div>
          <Pair a={{ label: "Manual", v: tti.manual }} b={{ label: "ClinieSync", v: tti.cliniesync }} unit=" s" />
          <p className="kc-foot">Median of logged timings · system latency {tti.system_latency_ms ?? "-"} ms</p>
        </article>
      </div>

      <div className="kpi-two">
        {/* AI quality & safety */}
        <article className="kpi-card wide">
          <header><span className="kc-icon tone-brand"><ShieldCheck size={17} /></span><h4>AI quality &amp; safety</h4><span className="kc-live">live from audit data</span></header>
          <div className="review-mix">
            <div className="mix-bar" role="img" aria-label={`Verified ${q.verified_pct}%, edited ${q.edited_pct}%, rejected ${q.rejected_pct}%`}>
              {reviewedTotal > 0 && <>
                <span className="v" style={{ flexGrow: q.verified_pct || 0 }} />
                <span className="e" style={{ flexGrow: q.edited_pct || 0 }} />
                <span className="r" style={{ flexGrow: q.rejected_pct || 0 }} /></>}
            </div>
            <div className="mix-legend">
              <span><i className="v" />Verified <b>{q.verified_pct ?? "-"}%</b></span>
              <span><i className="e" />Edited <b>{q.edited_pct ?? "-"}%</b></span>
              <span><i className="r" />Rejected <b>{q.rejected_pct ?? "-"}%</b></span>
              <span className="muted">of {q.reviewed ?? "-"} reviewed answers</span>
            </div>
          </div>
          <div className="kc-stats">
            <div><span>Answers</span><b className="num"><Num v={q.answers} /></b></div>
            <div><span>Requests blocked</span><b className="num"><Num v={sf.blocked_total} /></b></div>
            <div><span>Block rate</span><b className="num"><Num v={sf.block_rate_pct} unit="%" /></b></div>
            <div><span>“Wrong block” reports</span><b className="num">{sf.wrong_block_reports}</b></div>
            {q.median_review_seconds != null && <div><span>Median review</span><b className="num">{q.median_review_seconds}<small> s</small></b></div>}
            <div><span>Reminders sent</span><b className="num">{(k.data.reminders.sent || 0) + (k.data.reminders.handed_to_device || 0)}</b></div>
          </div>
          {blocks.length > 0 && <div className="block-bars">
            <span className="kc-sub">What the guardrails stopped</span>
            {blocks.map(([c, n]) => <div key={c} className="bb-row"><span>{BLOCK_LABEL[c] || c.replace(/_/g, " ")}</span>
              <span className="bb-track"><span style={{ width: `${(n / blockMax) * 100}%` }} /></span><b className="num">{n}</b></div>)}
          </div>}
        </article>
        <Stopwatch onSaved={k.reload} />
      </div>

      {/* pilot plan */}
      <section className="kpi-section">
        <div className="kpi-section-head"><span className="eyebrow">60-90 day pilot plan</span><h3>From baseline to a scale-up decision</h3></div>
        <ol className="plan-line">
          {PLAN.map((s, i) => (
            <li key={s.w} style={{ "--d": `${i * 90}ms` } as React.CSSProperties}>
              <span className="plan-node">{i + 1}</span>
              <span className="plan-when">{s.w}</span>
              <b>{s.t}</b>
              <p>{s.d}</p>
            </li>))}
        </ol>
        <div className="success">
          <span className="kc-sub"><Sparkles size={14} />Success criteria</span>
          <ul>{SUCCESS.map(s => <li key={s}><CheckCircle2 size={15} />{s}</li>)}</ul>
        </div>
      </section>

      {/* why it matters */}
      <section className="kpi-section">
        <div className="kpi-section-head"><span className="eyebrow">Why it matters</span><h3>Each KPI answers a documented problem</h3></div>
        <div className="why-list">
          {PROBLEMS.map(x => (
            <div key={x.solution} className="why-row">
              <div className="why-problem"><span className="why-tag">{x.tag}</span><b>{x.problem}</b><p>{x.evidence}</p><cite>{x.ref}</cite></div>
              <span className="why-arrow" aria-hidden="true"><ArrowRight size={18} /></span>
              <div className="why-solution"><span className="why-tag brand">ClinieSync</span><b>{x.solution}</b><p>{x.how}</p></div>
            </div>))}
        </div>
      </section>
    </div>
  );
}

const TASKS = ["Show the patient's last 3 visits", "Summarize the pregnancy journey", "Find patients with pending follow-ups", "Monthly MCH visit count", "Pending investigation results"];

function Stopwatch({ onSaved }: { onSaved: () => void }) {
  const [method, setMethod] = useState<"manual" | "cliniesync">("manual");
  const [task, setTask] = useState(TASKS[0]);
  const [secs, setSecs] = useState(0); const [running, setRunning] = useState(false); const [saved, setSaved] = useState<string | null>(null);
  const t0 = useRef(0);
  useEffect(() => { if (!running) return; const id = setInterval(() => setSecs((Date.now() - t0.current) / 1000), 50); return () => clearInterval(id); }, [running]);
  const save = async () => {
    if (!secs) return;
    await api.post("/api/kpi/timing", { task, method, seconds: Math.round(secs * 10) / 10 });
    setSaved(`Saved ${secs.toFixed(1)} s · ${method === "manual" ? "manual chart review" : "with ClinieSync"}`); setSecs(0); onSaved();
  };
  const R = 62, C = 2 * Math.PI * R;
  return (
    <article className="kpi-card stopwatch-card">
      <header><span className="kc-icon tone-violet"><Timer size={17} /></span><h4>Time-motion logger</h4></header>
      <p className="kc-def">Time the same standard question answered by manual chart review and by ClinieSync (including verification).</p>
      <select className="input" value={task} onChange={e => setTask(e.target.value)} aria-label="Task">{TASKS.map(t => <option key={t}>{t}</option>)}</select>
      <Seg value={method} onChange={setMethod} ariaLabel="Method" options={[{ value: "manual", label: <><UserCheck size={14} />Manual review</> }, { value: "cliniesync", label: <><Sparkles size={14} />With ClinieSync</> }]} />
      <div className={`sw ${running ? "running" : ""}`}>
        <svg viewBox="0 0 150 150" aria-hidden="true"><circle cx="75" cy="75" r={R} className="sw-track" />
          <circle cx="75" cy="75" r={R} className="sw-ring" strokeDasharray={C} strokeDashoffset={C * (1 - (secs % 60) / 60)} /></svg>
        <div className="sw-read"><b className="num">{secs.toFixed(1)}</b><span>seconds</span></div>
      </div>
      <div className="sw-actions">
        <button className={`btn ${running ? "" : "primary"}`} onClick={() => { if (running) setRunning(false); else { t0.current = Date.now() - secs * 1000; setRunning(true); setSaved(null); } }}>
          {running ? <><Pause size={15} />Stop</> : <><Play size={15} />{secs ? "Resume" : "Start"}</>}</button>
        <button className="btn" disabled={running || !secs} onClick={() => setSecs(0)} aria-label="Reset"><RotateCcw size={15} /></button>
        <button className="btn blue" disabled={running || !secs} onClick={save}>Save timing</button>
      </div>
      {saved && <div className="callout ok fade-in"><CheckCircle2 size={16} />{saved}</div>}
    </article>
  );
}
