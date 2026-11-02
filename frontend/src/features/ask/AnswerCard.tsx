// One AI answer: badges, cited markdown, charts/tables, SQL, guard trace, and the human review loop.
import { useState } from "react";
import {
  BellRing, Check, Code2, Cpu, FileText, Flag, Mic, Pencil, Send, ShieldAlert, ThumbsUp, User as UserIcon, X,
} from "lucide-react";
import { api, Citation, QueryResponse } from "../../api/client";
import { useApp } from "../../app/context";
import { ChartCard, fmtValue } from "../../charts/ChartRenderer";
import { MeasureMultiples } from "../journey/MeasureMultiples";
import { ShareReportModal } from "../reports/ShareReportModal";
import { DataTable, Drawer, ErrorNote, fmtDate, Markdown } from "../../ui/components";
import { GuardTrace } from "./GuardTrace";

const CATEGORY_LABEL: Record<string, string> = {
  diagnosis: "Diagnosis / interpretation", treatment_prescription: "Treatment / prescription", clinical_advice: "Clinical advice",
  risk_scoring: "Risk scoring / prediction", prompt_injection: "Prompt injection", bulk_data_export: "Bulk data export",
  out_of_scope: "Out of scope", access: "Access control",
};

export function AnswerCard({ res, onAsk }: { res: QueryResponse; onAsk: (q: string, patientId?: string) => void }) {
  const { user, nav, setPatientId } = useApp();
  const [status, setStatus] = useState<string>(res.status);
  const [answer, setAnswer] = useState(res.answer);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(res.answer);
  const [cite, setCite] = useState<Citation | null>(null);
  const [share, setShare] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [flagged, setFlagged] = useState(false);
  const [info, setInfo] = useState<string | null>(null);

  const review = async (action: "verify" | "edit" | "reject") => {
    setErr(null);
    try {
      const r = await api.post<{ status: string; answer: string }>(`/api/reviews/${res.response_id}`,
        action === "edit" ? { action, edited_text: draft } : { action });
      setStatus(r.status); setAnswer(r.answer); setEditing(false);
    } catch (e: any) { setErr(e.message); }
  };
  const feedback = async (kind: string) => {
    await api.post("/api/trust/feedback", { response_id: res.response_id, kind }).catch(() => null); setFlagged(true);
  };
  const openCite = (id: string) => setCite(res.citations?.find(c => c.id === id) || null);
  const draftReminders = async (ids: string[]) => {
    try {
      const r = await api.post<{ drafts: unknown[] }>("/api/followups/drafts", { followup_ids: ids, channel: "sms", recipient: "patient", language: "auto" });
      setInfo(`${r.drafts.length} reminder drafts created in each patient's preferred language. Nothing is sent until you approve them.`);
    } catch (e: any) { setErr(e.message); }
  };

  if (res.status === "blocked") {
    return (
      <div className="answer blocked fade-in">
        <div className="answer-head">
          <span className="badge bad"><ShieldAlert size={13} />Blocked · {CATEGORY_LABEL[res.refusal?.category || ""] || res.intent}</span>
          <span className="spacer" /><span className="tiny muted">{res.latency_ms} ms</span>
        </div>
        <p className="refusal">{res.answer}</p>
        {res.refusal?.alternatives?.length ? (
          <div className="row" style={{ gap: 8 }}><span className="small muted">Try instead:</span>
            {res.refusal.alternatives.map(a => <button key={a} className="chip-btn" onClick={() => onAsk(a)}>{a}</button>)}</div>) : null}
        <GuardTrace res={res} defaultOpen />
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn ghost sm" disabled={flagged} onClick={() => feedback("wrong_block")}><Flag size={14} />
            {flagged ? "Reported for review - thank you" : "Report as wrongly blocked"}</button>
        </div>
      </div>
    );
  }

  if (res.status === "needs_clarification") {
    return (
      <div className="answer fade-in">
        <Markdown text={res.answer} />
        {!!res.candidates?.length && <div className="row" style={{ marginTop: 10 }}>{res.candidates.map(c => (
          <button key={c.patient_id} className="chip-btn" onClick={() => { setPatientId(c.patient_id); onAsk(res.query, c.patient_id); }}>
            {c.name} · {c.patient_id}</button>))}</div>}
        <button className="btn sm" style={{ marginTop: 10 }} onClick={() => nav("journey")}>Choose a patient</button>
      </div>
    );
  }

  const llm = res.generated_by === "llm";
  return (
    <div className={`answer fade-in status-${status}`}>
      <div className="answer-head">
        <span className="badge brand">{res.intent_label}</span>
        <span className="badge info">{res.route}</span>
        <span className={`badge ${llm ? "violet" : "neutral"}`}><Cpu size={12} />{llm ? res.llm_model : "Record-built (deterministic)"}</span>
        {res.input_mode === "voice" && <span className="badge outline"><Mic size={12} />voice</span>}
        {res.patient && <button className="badge outline as-link" onClick={() => { setPatientId(res.patient!.patient_id); nav("journey"); }}>
          <UserIcon size={12} />{res.patient.name} · {res.patient.patient_id}</button>}
        <span className="spacer" /><span className="tiny muted">{res.latency_ms} ms</span>
      </div>

      {editing ? (
        <div className="col"><textarea className="input" rows={8} value={draft} onChange={e => setDraft(e.target.value)} />
          <div className="row"><button className="btn primary sm" onClick={() => review("edit")}><Check size={14} />Save edit &amp; verify</button>
            <button className="btn sm" onClick={() => setEditing(false)}>Cancel</button></div></div>
      ) : <Markdown text={answer} onCite={openCite} />}

      {!!res.stats?.length && (
        <div className="mini-stats">{res.stats.map(s => (
          <div key={s.label} className="mini-stat"><span>{s.label}</span><b>{fmtValue(s.value, "int")}{s.unit || ""}</b>
            {s.delta !== undefined && <small className={s.delta >= 0 ? "up" : "down"}>{s.delta >= 0 ? "+" : ""}{s.delta} {s.delta_label}</small>}</div>))}
        </div>)}
      {res.measurements && <MeasureMultiples series={Object.fromEntries(Object.entries(res.measurements).map(([k, v]) => [k, { code: k, display: k.replace(/_/g, " "), unit: "", points: v }]))} />}
      {!!res.charts?.length && <div className={`grid ${res.charts.length > 1 ? "g2" : ""}`} style={{ marginTop: 12 }}>
        {res.charts.map(c => <ChartCard key={c.id} spec={c} definition={res.definition} />)}</div>}
      {res.table && res.table.rows.length > 0 && (
        <details open={!res.charts?.length} style={{ marginTop: 12 }}>
          <summary>Data ({res.table.rows.length} rows)</summary>
          <div style={{ marginTop: 8 }}><DataTable columns={res.table.columns} rows={res.table.rows} max={100} /></div>
        </details>)}
      {res.sql && <details style={{ marginTop: 10 }}><summary><Code2 size={13} /> SQL used (de-identified views, read-only)</summary>
        <pre className="sql">{res.sql}</pre></details>}
      {!!res.caveats?.length && <ul className="caveats">{res.caveats.map(c => <li key={c}>{c}</li>)}</ul>}
      {res.notes?.map(n => <div key={n} className="callout warn" style={{ marginTop: 8 }}>{n}</div>)}
      {!!res.citations?.length && (
        <div className="sources"><span className="small muted"><FileText size={13} /> Sources:</span>
          {res.citations.slice(0, 18).map(c => <button key={c.id} className="cite" onClick={() => setCite(c)} title={c.title}>{c.id}</button>)}
          {res.citations.length > 18 && <span className="tiny muted">+{res.citations.length - 18} more</span>}</div>)}

      <GuardTrace res={res} />

      <div className="review-bar">
        {status === "pending_review" ? (<>
          <span className="small"><b>Human review required</b> - verify against the source before use.</span><span className="spacer" />
          <button className="btn primary sm" onClick={() => review("verify")}><Check size={14} />Verify</button>
          <button className="btn sm" onClick={() => { setDraft(answer); setEditing(true); }}><Pencil size={14} />Edit</button>
          <button className="btn danger sm" onClick={() => review("reject")}><X size={14} />Reject</button>
        </>) : (<>
          <span className={`badge ${status === "rejected" ? "bad" : "ok"}`}>{status === "rejected" ? <X size={12} /> : <Check size={12} />}
            {status === "verified" ? "Verified by you" : status === "edited" ? "Edited & verified by you" : "Rejected"}</span>
          <span className="spacer" />
          {user.role === "doctor" && res.patient && status !== "rejected" && (
            <button className="btn blue sm" onClick={() => setShare(true)}><Send size={14} />Share report</button>)}
          <button className="btn ghost sm" disabled={flagged} onClick={() => feedback("helpful")}><ThumbsUp size={14} />{flagged ? "Thanks" : "Helpful"}</button>
        </>)}
        {res.actions?.filter(a => a.type === "draft_reminders").map(a => (
          <button key={a.type} className="btn sm" onClick={() => draftReminders(a.followup_ids || [])}><BellRing size={14} />{a.label}</button>))}
        {res.actions?.filter(a => a.type === "open_followups").map(a => (
          <button key={a.type} className="btn sm" onClick={() => nav("followups")}><BellRing size={14} />{a.label}</button>))}
      </div>
      {info && <div className="callout ok" style={{ marginTop: 8 }}>{info} <button className="btn sm" onClick={() => nav("followups")}>Review drafts</button></div>}
      <ErrorNote error={err} />
      <p className="tiny muted" style={{ marginTop: 8 }}>{res.disclaimer}</p>

      <Drawer open={!!cite} onClose={() => setCite(null)} title={cite ? `${cite.id} · ${cite.title}` : ""}>
        {cite && (<div className="col">
          <div className="row"><span className="badge neutral">{cite.kind}</span>{cite.date && <span className="small muted">{fmtDate(cite.date)}</span>}
            <span className="tiny muted mono">{cite.ref_type}:{cite.ref_id}</span></div>
          <pre className="source-text">{cite.text}</pre>
          <p className="tiny muted">Verbatim from the unified record (source system and lineage kept by the ETL).</p></div>)}
      </Drawer>
      {share && <ShareReportModal open={share} onClose={() => setShare(false)} responseId={res.response_id} defaultLang={res.patient?.preferred_language} />}
    </div>
  );
}
