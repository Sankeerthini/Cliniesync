// Care coordination: documented follow-up queue -> multilingual reminder drafts -> human approval -> send -> contact outcome.
import { useMemo, useState } from "react";
import { AlarmClock, BellRing, Check, CheckCheck, Clock, Hourglass, MailCheck, PhoneCall, Send, ShieldCheck, Undo2, X } from "lucide-react";
import { api } from "../../api/client";
import { ChartCard } from "../../charts/ChartRenderer";
import { DataTable, EmptyState, ErrorNote, fmtDate, LANG_LABEL, Loading, Modal, Seg, StatTile, useAsync } from "../../ui/components";

interface FU { followup_id: string; patient_id: string; patient: string; followup_type: string; due_on: string; days_past_due: number; status: string;
  facility: string; language: string; phone: string; caregiver: string | null; consent_sms: boolean; consent_whatsapp: boolean; workflow_state: string;
  contact_attempts: number; last_contact_on: string | null; documented_instruction: string; origin: string }
interface Msg { message_id: string; patient: string; patient_id: string; channel: string; language: string; body: string; status: string;
  recipient: string; recipient_type: string; created_at: string; approved_by: string | null; delivery_detail: string | null; kind: string }
interface Summary { counts: Record<string, number>; aging: { bucket: string; followups: number }[]; open_by_type: { followup_type: string; open: number }[]; drafts_awaiting_approval: number }

const STATUS_ICON: Record<string, JSX.Element> = {
  due: <span className="badge warn"><Clock size={12} />due</span>, overdue: <span className="badge warn"><AlarmClock size={12} />overdue</span>,
  missed: <span className="badge bad"><Hourglass size={12} />missed</span>, upcoming: <span className="badge neutral">upcoming</span>,
  completed: <span className="badge ok"><Check size={12} />completed</span>,
};
const WF: Record<string, string> = { none: "-", reminder_drafted: "Draft ready", reminder_sent: "Reminder sent", contacted: "Reached", scheduled: "Scheduled",
  unreachable: "Unreachable", declined: "Declined" };

export function FollowupsPage() {
  const [tab, setTab] = useState<"queue" | "outbox">("queue");
  const [statusF, setStatusF] = useState("due,overdue");
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [channel, setChannel] = useState<"sms" | "whatsapp">("sms");
  const [recipient, setRecipient] = useState<"patient" | "caregiver">("patient");
  const [lang, setLang] = useState("auto");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [contactFor, setContactFor] = useState<FU | null>(null);
  const [overrideFor, setOverrideFor] = useState<FU | null>(null);

  const sum = useAsync(() => api.get<Summary>("/api/followups/summary"), []);
  const queue = useAsync(() => api.get<{ followups: FU[] }>(`/api/followups?status=${statusF}&followup_type=${encodeURIComponent(type)}&q=${encodeURIComponent(q)}`), [statusF, type, q]);
  const outbox = useAsync(() => api.get<{ messages: Msg[] }>("/api/outbox?kind=followup_reminder"), [tab]);

  const toggle = (id: string) => setSel(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const rows = queue.data?.followups || [];
  const allSelected = rows.length > 0 && rows.slice(0, 50).every(r => sel.has(r.followup_id));

  const draft = async () => {
    setErr(null);
    try {
      const r = await api.post<{ drafts: Msg[] }>("/api/followups/drafts", { followup_ids: [...sel], channel, recipient, language: lang });
      const blocked = r.drafts.filter(d => d.status !== "draft").length;
      setMsg(`${r.drafts.length - blocked} drafts created${blocked ? `, ${blocked} skipped (no consent / no number on record)` : ""}. Review them in the outbox - nothing is sent until you approve.`);
      setSel(new Set()); queue.reload(); sum.reload(); setTab("outbox");
    } catch (e: any) { setErr(e.message); }
  };

  const agingSpec = useMemo(() => sum.data && ({ id: "aging", type: "bar" as const, title: "Overdue & missed follow-ups by days past due",
    x: "bucket", series: [{ key: "followups", label: "Follow-ups" }], data: sum.data.aging, value_format: "int" as const }), [sum.data]);
  const typeSpec = useMemo(() => sum.data && ({ id: "types", type: "hbar" as const, title: "Open follow-ups (due + overdue) by type",
    x: "followup_type", series: [{ key: "open", label: "Open" }], data: sum.data.open_by_type, value_format: "int" as const }), [sum.data]);

  return (
    <div className="page">
      <div className="page-head"><div><div className="eyebrow">Coordinate instead of chase · Prompt instead of depend on memory</div>
        <h2>Follow-up queue</h2><p>Only follow-ups documented by clinic staff (appointments, registers, notes) appear here. Ordered by days past due - an operational order, not a clinical priority.</p></div></div>

      <div className="grid g4">
        <StatTile label="Due in next 7 days" value={sum.data?.counts.due ?? "-"} icon={<Clock size={18} />} tone="brand" />
        <StatTile label="Overdue (≤ 28 days)" value={sum.data?.counts.overdue ?? "-"} icon={<AlarmClock size={18} />} tone="coral" />
        <StatTile label="Missed (> 28 days)" value={sum.data?.counts.missed ?? "-"} icon={<Hourglass size={18} />} tone="violet" />
        <StatTile label="Drafts awaiting approval" value={sum.data?.drafts_awaiting_approval ?? "-"} icon={<MailCheck size={18} />} tone="blue" />
      </div>
      {sum.data && <div className="grid g2" style={{ marginTop: 18 }}>
        <ChartCard spec={agingSpec!} height={220} /><ChartCard spec={typeSpec!} height={200} /></div>}

      <div className="card" style={{ marginTop: 18 }}>
        <div className="card-head">
          <Seg value={tab} onChange={setTab} options={[{ value: "queue", label: <><BellRing size={14} /> Queue</> },
            { value: "outbox", label: <><MailCheck size={14} /> Reminder outbox</> }]} />
          <span className="spacer" />
          <span className="badge brand"><ShieldCheck size={12} />Human approval required before sending</span>
        </div>

        {tab === "queue" && (<>
          <div className="filters">
            <Seg value={statusF} onChange={v => { setStatusF(v); setSel(new Set()); }} ariaLabel="Status" options={[
              { value: "due,overdue", label: "Due & overdue" }, { value: "missed", label: "Missed" }, { value: "upcoming", label: "Upcoming" }, { value: "completed", label: "Completed" }]} />
            <select className="input" style={{ maxWidth: 220 }} value={type} onChange={e => setType(e.target.value)} aria-label="Follow-up type">
              <option value="">All types</option>{["ANC visit", "PNC visit", "Immunization", "Investigation review"].map(t => <option key={t}>{t}</option>)}</select>
            <input className="input" style={{ maxWidth: 240 }} placeholder="Search patient" value={q} onChange={e => setQ(e.target.value)} />
          </div>
          <div className={`bulk-bar ${sel.size ? "has-sel" : ""}`}>
            <label className="check-row"><input type="checkbox" checked={allSelected} onChange={() => setSel(allSelected ? new Set() : new Set(rows.slice(0, 50).map(r => r.followup_id)))} />Select top 50</label>
            <span className="sel-count"><b>{sel.size}</b> selected</span><span className="spacer" />
            <Seg value={channel} onChange={setChannel} ariaLabel="Channel" options={[{ value: "sms", label: "SMS" }, { value: "whatsapp", label: "WhatsApp" }]} />
            <Seg value={recipient} onChange={setRecipient} ariaLabel="Recipient" options={[{ value: "patient", label: "Patient" }, { value: "caregiver", label: "Caregiver" }]} />
            <select className="input" style={{ width: 200 }} value={lang} onChange={e => setLang(e.target.value)} aria-label="Language">
              <option value="auto">Preferred language</option>{Object.entries(LANG_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
            <button className="btn primary sm" disabled={!sel.size} onClick={draft}><BellRing size={14} />Draft reminders</button>
          </div>
          {msg && <div className="callout ok" style={{ marginBottom: 10 }}>{msg}</div>}
          <ErrorNote error={err} />
          {queue.loading && !queue.data ? <Loading /> : (
            <DataTable rows={rows} rowKey="followup_id" selectable selected={sel} onToggle={toggle} columns={[
              { key: "patient", label: "Patient", render: r => <><b>{r.patient}</b><div className="tiny muted">{r.patient_id} · {r.facility}</div></> },
              { key: "followup_type", label: "Follow-up" },
              { key: "due_on", label: "Due", render: r => fmtDate(r.due_on) },
              { key: "days_past_due", label: "Days past due", render: r => <span className="num">{r.days_past_due}</span> },
              { key: "status", label: "Status", render: r => STATUS_ICON[r.status] || r.status },
              { key: "language", label: "Language", render: r => LANG_LABEL[r.language] },
              { key: "consent", label: "Consent", render: r => <span className="tiny">{r.consent_sms ? "SMS " : ""}{r.consent_whatsapp ? "WA" : ""}{!r.consent_sms && !r.consent_whatsapp ? "none" : ""}</span> },
              { key: "workflow_state", label: "Coordination", render: r => <>{WF[r.workflow_state] || r.workflow_state}{r.contact_attempts > 0 && <div className="tiny muted">{r.contact_attempts} attempt(s)</div>}</> },
              { key: "documented_instruction", label: "Documented instruction", render: r => <span className="small clamp" title={r.documented_instruction}>{r.documented_instruction}</span> },
              { key: "actions", label: "", render: r => <div className="row" style={{ gap: 4, flexWrap: "nowrap" }}>
                <button className="btn icon-sm" onClick={e => { e.stopPropagation(); setContactFor(r); }} title="Log contact" aria-label={`Log contact for ${r.patient}`}><PhoneCall size={14} /></button>
                <button className="btn icon-sm" onClick={e => { e.stopPropagation(); setOverrideFor(r); }} title="Override status" aria-label={`Override status for ${r.patient}`}><Undo2 size={14} /></button></div> },
            ]} />)}
        </>)}

        {tab === "outbox" && <Outbox messages={outbox.data?.messages || []} reload={() => { outbox.reload(); sum.reload(); queue.reload(); }} />}
      </div>

      {contactFor && <ContactModal fu={contactFor} onClose={() => setContactFor(null)} onDone={() => { setContactFor(null); queue.reload(); }} />}
      {overrideFor && <OverrideModal fu={overrideFor} onClose={() => setOverrideFor(null)} onDone={() => { setOverrideFor(null); queue.reload(); sum.reload(); }} />}
    </div>
  );
}

function Outbox({ messages, reload }: { messages: Msg[]; reload: () => void }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("draft");
  const [limit, setLimit] = useState(12);
  const act = async (id: string, action: string, b?: string) => {
    setErr(null);
    try { await api.post(`/api/outbox/${id}`, { action, body: b }); setEditing(null); reload(); } catch (e: any) { setErr(e.message); }
  };
  const shown = messages.filter(m => filter === "all" || m.status === filter);
  const drafts = messages.filter(m => m.status === "draft");
  const approveAll = async () => {
    setErr(null);
    try { await api.post("/api/outbox/approve-and-send", { message_ids: drafts.map(d => d.message_id) }); reload(); } catch (e: any) { setErr(e.message); }
  };
  return (<>
    <div className="filters">
      <Seg value={filter} onChange={setFilter} options={[{ value: "draft", label: `Drafts (${drafts.length})` }, { value: "approved", label: "Approved" },
        { value: "sent", label: "Sent" }, { value: "rejected", label: "Rejected" }, { value: "all", label: "All" }]} />
      <span className="spacer" />
      {filter === "draft" && drafts.length > 0 && <button className="btn primary sm" onClick={approveAll}><CheckCheck size={14} />I have reviewed all - approve &amp; send {drafts.length}</button>}
    </div>
    <ErrorNote error={err} />
    {!shown.length ? <EmptyState icon={<MailCheck size={26} />} title="No messages here" text="Select follow-ups in the queue and click “Draft reminders”. Nothing is sent until you approve it." /> : (
      <><div className="msg-grid">{shown.slice(0, limit).map(m => (
        <div key={m.message_id} className="msg-card card">
          <div className="row" style={{ gap: 6 }}>
            <b>{m.patient}</b><span className="tiny muted">{m.patient_id}</span><span className="spacer" />
            <span className="badge outline">{m.channel.toUpperCase()}</span><span className="badge neutral">{LANG_LABEL[m.language]}</span>
            <span className={`badge ${m.status === "sent" ? "ok" : m.status === "draft" ? "warn" : m.status === "rejected" || m.status === "failed" ? "bad" : "info"}`}>{m.status.replace(/_/g, " ")}</span>
          </div>
          <div className="tiny muted">To {m.recipient_type}: {m.recipient}</div>
          {editing === m.message_id ? <textarea className="input" rows={5} value={body} onChange={e => setBody(e.target.value)} lang={m.language} />
            : <p className="msg-body" lang={m.language}>{m.body}</p>}
          {m.delivery_detail && <div className="tiny muted">{m.delivery_detail}</div>}
          <div className="row" style={{ gap: 6 }}>
            {m.status === "draft" && (editing === m.message_id ? <>
              <button className="btn sm primary" onClick={() => act(m.message_id, "edit", body)}>Save</button>
              <button className="btn sm" onClick={() => setEditing(null)}>Cancel</button></> : <>
              <button className="btn sm primary" onClick={() => act(m.message_id, "approve")}><Check size={13} />Approve</button>
              <button className="btn sm" onClick={() => { setEditing(m.message_id); setBody(m.body); }}>Edit</button>
              <button className="btn sm danger" onClick={() => act(m.message_id, "reject")}><X size={13} />Reject</button></>)}
            {m.status === "approved" && <button className="btn sm blue" onClick={() => act(m.message_id, "send")}><Send size={13} />Send</button>}
            {m.approved_by && <span className="tiny muted">approved by {m.approved_by}</span>}
          </div>
        </div>))}</div>
      {shown.length > limit && <div className="row" style={{ justifyContent: "center", marginTop: 12 }}>
        <button className="btn sm" onClick={() => setLimit(l => l + 24)}>Show more ({shown.length - limit} remaining)</button></div>}</>)}
  </>);
}

function ContactModal({ fu, onClose, onDone }: { fu: FU; onClose: () => void; onDone: () => void }) {
  const [channel, setChannel] = useState("phone"); const [outcome, setOutcome] = useState("reached"); const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const save = async () => { try { await api.post(`/api/followups/${fu.followup_id}/contact`, { channel, outcome, note }); onDone(); } catch (e: any) { setErr(e.message); } };
  return (
    <Modal open onClose={onClose} title={`Log contact · ${fu.patient}`}>
      <div className="col">
        <p className="small muted">{fu.followup_type} due {fmtDate(fu.due_on)} · {fu.phone}{fu.caregiver ? ` · caregiver ${fu.caregiver}` : ""}</p>
        <label className="field">Channel<Seg value={channel} onChange={setChannel} options={[{ value: "phone", label: "Phone" }, { value: "home_visit", label: "Home visit" },
          { value: "in_person", label: "In person" }, { value: "whatsapp", label: "WhatsApp" }]} /></label>
        <label className="field">Outcome<Seg value={outcome} onChange={setOutcome} options={[{ value: "reached", label: "Reached" }, { value: "scheduled", label: "Visit scheduled" },
          { value: "unreachable", label: "Unreachable" }, { value: "declined", label: "Declined" }]} /></label>
        <label className="field">Note (optional, operational only)<input className="input" value={note} onChange={e => setNote(e.target.value)} /></label>
        <ErrorNote error={err} />
        <button className="btn primary" onClick={save}>Save to audit trail</button>
      </div>
    </Modal>);
}

function OverrideModal({ fu, onClose, onDone }: { fu: FU; onClose: () => void; onDone: () => void }) {
  const [status, setStatus] = useState("completed"); const [reason, setReason] = useState(""); const [err, setErr] = useState<string | null>(null);
  const save = async () => { try { await api.post(`/api/followups/${fu.followup_id}/override`, { status, reason }); onDone(); } catch (e: any) { setErr(e.message); } };
  return (
    <Modal open onClose={onClose} title="Override follow-up status">
      <div className="col">
        <p className="small">The status is derived from the records. Override it when you know better - e.g. the visit happened at another facility. A reason is mandatory and is written to the audit trail.</p>
        <label className="field">New status<Seg value={status} onChange={setStatus} options={[{ value: "completed", label: "Completed" }, { value: "cancelled", label: "Cancelled" }, { value: "missed", label: "Missed" }]} /></label>
        <label className="field">Reason<input className="input" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Seen at DH Tumakuru on 12 Oct (per caregiver)" /></label>
        <ErrorNote error={err} />
        <button className="btn primary" disabled={reason.trim().length < 3} onClick={save}>Save override</button>
      </div>
    </Modal>);
}
