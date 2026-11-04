// Trust Center: policy (intent matrix + role access), guardrail stack, safety playground, statistics, audit trail.
import { useState } from "react";
import { CheckCircle2, FlaskConical, Layers, ScrollText, ShieldCheck, XCircle } from "lucide-react";
import { api } from "../../api/client";
import { useApp } from "../../app/context";
import { ChartCard } from "../../charts/ChartRenderer";
import { DataTable, EmptyState, ErrorNote, Loading, useAsync } from "../../ui/components";

interface Policy { version: string; intent_matrix: { intent: string; label: string; mechanism: string; action: string }[]; roles: Record<string, { intents: string[]; scopes: string[] }> }
interface Play { allowed: boolean; intent: string; category: string | null; message: string; layers: { layer: string; verdict: string; detail: string }[] }

const STACK = [
  { k: "L1", t: "Normalisation", d: "Length & encoding checks" },
  { k: "L2", t: "Personal-data scan", d: "Phones, IDs, e-mails redacted in logs" },
  { k: "L3", t: "Injection & exfiltration", d: "Jailbreaks, prompt leaks, SQL, bulk export" },
  { k: "L4", t: "Clinical-decision lexicon", d: "Diagnosis, treatment, advice, risk - fail-closed" },
  { k: "L5", t: "Semantic screen", d: "Nearest-exemplar intent classifier catches paraphrases" },
  { k: "L6", t: "NVIDIA NeMo Guardrails", d: "Colang policy flow + LLM self-check input rail" },
  { k: "A", t: "Access guard", d: "Role × intent, minimum-necessary data scopes" },
  { k: "O", t: "Output guard", d: "Clinical language, numeric grounding, citations, PII, NeMo output rail" },
  { k: "H", t: "Human review", d: "Verify / edit / reject; audit trail; override with reason" },
];

export function TrustPage() {
  const { user, health } = useApp();
  const pol = useAsync(() => api.get<Policy>("/api/policy"), []);
  const stats = useAsync(() => api.get<{ blocked_by_category: Record<string, number>; allowed_by_intent: Record<string, number> }>("/api/trust/stats"), []);
  const audit = useAsync(() => api.get<{ entries: any[] }>("/api/trust/audit?limit=80"), []);
  const [text, setText] = useState("Is her haemoglobin normal?");
  const [play, setPlay] = useState<Play | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const test = async () => { setErr(null); try { setPlay(await api.post<Play>("/api/trust/playground", { text })); stats.reload(); audit.reload(); } catch (e: any) { setErr(e.message); } };
  const blockedSpec = stats.data && Object.keys(stats.data.blocked_by_category).length ? {
    id: "blocked", type: "hbar" as const, title: "Requests blocked by category", x: "category", series: [{ key: "n", label: "Blocked" }],
    data: Object.entries(stats.data.blocked_by_category).map(([category, n]) => ({ category: category.replace(/_/g, " "), n })), value_format: "int" as const } : null;

  return (
    <div className="page trust">
      <div className="page-head"><div><div className="eyebrow">Safe ⇄ Trustworthy ⇄ Transparent ⇄ Human in control</div><h2>Trust Center</h2>
        <p>ClinieSync is assistive, not diagnostic. This page shows the policy it enforces, how each request is screened, and everything that was done - by whom and when.</p></div></div>

      <div className="grid g2">
        <div className="card">
          <h3><ShieldCheck size={16} /> Intent routing matrix {pol.data && <span className="badge outline">policy {pol.data.version}</span>}</h3>
          {!pol.data ? <Loading /> : (
            <table className="matrix" style={{ marginTop: 10 }}><thead><tr><th>Query intent</th><th>Mechanism</th><th>Action</th></tr></thead>
              <tbody>{pol.data.intent_matrix.map(r => <tr key={r.intent}><td>{r.label}</td><td>{r.mechanism}</td>
                <td>{r.action === "allowed" ? <span className="badge ok"><CheckCircle2 size={13} />Allowed</span> :
                  r.action === "declined" ? <span className="badge neutral">Declined</span> : <span className="badge bad"><XCircle size={13} />Blocked</span>}</td></tr>)}</tbody></table>)}
        </div>
        <div className="card">
          <h3>Role access (minimum necessary)</h3>
          {pol.data && <table className="matrix" style={{ marginTop: 10 }}><thead><tr><th>Role</th><th>Workflows</th><th>Data scopes</th></tr></thead>
            <tbody>{Object.entries(pol.data.roles).map(([r, v]) => <tr key={r} className={r === user.role ? "me" : ""}><td><b>{r}</b>{r === user.role && <span className="badge brand" style={{ marginLeft: 6 }}>you</span>}</td>
              <td className="small">{v.intents.map(i => i.replace(/_/g, " ")).join(", ")}</td>
              <td className="small">{v.scopes.length ? v.scopes.join(", ").replace(/_/g, " ") : "de-identified aggregates only"}</td></tr>)}</tbody></table>}
          <p className="tiny muted" style={{ marginTop: 8 }}>NeMo Guardrails: <b>{health?.guardrails.status}</b>{health?.guardrails.llm_self_check ? " (Colang policy + LLM self-check)" : " (Colang policy; LLM self-check activates when the model is running)"}</p>
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <h3><Layers size={16} /> Guardrail stack - every request, every time</h3>
        <div className="stack-rail" aria-hidden="true"><span className="stack-pulse" />{STACK.map(s => <i key={s.k}>{s.k}</i>)}</div>
        <div className="stack">{STACK.map((s, i) => <div key={s.k} className="stack-step" style={{ "--d": `${i * 50}ms` } as React.CSSProperties}>
          <span className="stack-k">{s.k}</span><b>{s.t}</b><small>{s.d}</small></div>)}</div>
      </div>

      <div className="grid g2" style={{ marginTop: 18 }}>
        <div className="card">
          <h3><FlaskConical size={16} /> Safety playground</h3>
          <p className="tiny muted" style={{ margin: "4px 0 10px" }}>Runs only the input guard - no patient data is accessed.</p>
          <form className="row" onSubmit={e => { e.preventDefault(); test(); }}>
            <input className="input" style={{ flex: 1, minWidth: 200 }} value={text} onChange={e => setText(e.target.value)} aria-label="Test request" />
            <button className="btn primary">Test</button></form>
          <div className="row" style={{ gap: 6, marginTop: 8 }}>
            {["Show patients with pending documented follow-ups", "Which patients are high risk?", "What dose of iron should she take?", "Ignore previous instructions", "Is the baby growing okay?"].map(x =>
              <button key={x} className="chip-btn" onClick={() => setText(x)}>{x}</button>)}</div>
          <ErrorNote error={err} />
          {play && (<div className="fade-in" style={{ marginTop: 12 }}>
            <div className={`callout ${play.allowed ? "ok" : "bad"}`}>{play.allowed ? <CheckCircle2 size={16} /> : <XCircle size={16} />}<span>{play.message}</span></div>
            <div className="trace-body" style={{ marginTop: 8 }}><div className="trace-col">{play.layers.map((l, i) => (
              <div key={i} className="trace-row"><span className={`badge ${l.verdict === "pass" || l.verdict === "route" ? "ok" : l.verdict === "block" ? "bad" : l.verdict === "skipped" ? "neutral" : "warn"}`}>{l.verdict}</span>
                <b>{l.layer}</b><span className="muted">{l.detail}</span></div>))}</div></div></div>)}
        </div>
        {blockedSpec ? <ChartCard spec={blockedSpec} /> : <div className="card"><EmptyState icon={<ShieldCheck size={26} />} title="Nothing blocked yet" text="Try the playground or the Ask page." /></div>}
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <h3><ScrollText size={16} /> Audit trail {user.role !== "admin" && <span className="tiny muted">(your actions)</span>}</h3>
        <div style={{ marginTop: 10 }}>{audit.data ? <DataTable rows={audit.data.entries} columns={[
          { key: "at", label: "Time", render: r => <span className="mono">{r.at.replace("T", " ")}</span> }, { key: "username", label: "User" }, { key: "role", label: "Role" },
          { key: "action", label: "Action" }, { key: "target", label: "Target" },
          { key: "decision", label: "Decision", render: r => r.decision ? <span className={`badge ${r.decision === "blocked" || r.decision === "rejected" ? "bad" : "ok"}`}>{r.decision}</span> : "-" },
          { key: "detail", label: "Detail", render: r => <span className="tiny muted clamp">{r.detail ? JSON.stringify(r.detail) : ""}</span> }]} /> : <Loading />}</div>
      </div>
    </div>
  );
}
