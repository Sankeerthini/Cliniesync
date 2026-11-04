// Patient Journey: registry search -> patient header (3D) -> longitudinal timeline, measurements, visits, documents.
import { useEffect, useState } from "react";
import { Baby, CalendarClock, FileText, Link2, MessageSquareText, Phone, Search, Sparkles, UserRound } from "lucide-react";
import { api } from "../../api/client";
import { useApp } from "../../app/context";
import { Swimlane, TimelineData, TLEvent } from "../../charts/Swimlane";
import { DataTable, Drawer, EmptyState, ErrorNote, fmtDate, LANG_LABEL, Loading, Seg, useAsync } from "../../ui/components";
import { MeasureMultiples, Series } from "./MeasureMultiples";

interface PatientRow { patient_id: string; name: string; age: number; village: string; facility: string; language: string; status: string; edd: string; anc_visits: number; open_followups: number }
interface Profile {
  patient_id: string; name: string; age: number; language: string; village: string; facility: string; rch_id: string; sources: string[];
  pregnancy: { gravida: number; parity: number; lmp: string; edd: string; status: string; registration_date: string; registration_ga_weeks: number;
    delivery_date: string | null; delivery_mode: string | null; anc_visits_completed: number; ga_today_weeks: number | null } | null;
  children: { child_id: string; name: string; sex: string; dob: string; birth_weight_g: number }[];
  contact?: { phone: string; caregiver_name: string; caregiver_relation: string; caregiver_phone: string; consent: Record<string, boolean> };
  scopes: string[];
}
const STATUS_LABEL: Record<string, string> = { antenatal: "Antenatal", delivered: "Delivered (< 6 w)", postnatal_closed: "Postnatal completed", no_recent_contact: "No recent contact" };
const STATUS_TONE: Record<string, string> = { antenatal: "brand", delivered: "info", postnatal_closed: "neutral", no_recent_contact: "warn" };
const initials = (n: string) => n.split(" ").map(w => w[0]).slice(0, 2).join("");

// where she is in the pregnancy: week of 40 with trimester marks (GA is computed by the backend at the reference date)
function PregnancyProgress({ ga }: { ga: number | null }) {
  if (ga === null || ga === undefined) return null;
  const w = Math.min(42, Math.max(0, ga)), tri = w < 13 ? "1st" : w < 28 ? "2nd" : "3rd";
  return (
    <div className="preg">
      <div className="preg-top"><b>Week {Math.round(w)}</b><span>of 40 · {tri} trimester</span></div>
      <div className="preg-track"><span className="preg-fill" style={{ width: `${Math.min(100, (w / 40) * 100)}%` }} />
        <i style={{ left: "32.5%" }} /><i style={{ left: "70%" }} /></div>
      <div className="preg-scale"><span>LMP</span><span style={{ left: "32.5%" }}>13 w</span><span style={{ left: "70%" }}>28 w</span><span>EDD</span></div>
    </div>);
}

export function JourneyPage() {
  const { user, patientId, setPatientId, nav } = useApp();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const list = useAsync(() => api.get<{ patients: PatientRow[] }>(`/api/patients?q=${encodeURIComponent(q)}&status=${status}&limit=80`), [q, status]);
  useEffect(() => {   // default: a patient with a complete mother-baby journey (most informative timeline)
    const ps = list.data?.patients; if (patientId || !ps?.length) return;
    api.get<{ patients: PatientRow[] }>("/api/patients?status=delivered&limit=1")
      .then(r => setPatientId((r.patients[0] || ps[0]).patient_id)).catch(() => setPatientId(ps[0].patient_id));
  }, [list.data]); // eslint-disable-line

  return (
    <div className="page journey">
      <div className="page-head"><div><div className="eyebrow">Summarize instead of reconstruct</div><h2>Patient Journey</h2>
        <p>One longitudinal mother–baby timeline, linked across EHR exports, registers and lab PDFs.</p></div></div>
      <div className="journey-grid">
        <aside className="card patient-list">
          <label className="search-pill"><Search size={16} /><input placeholder="Name, CS-ID, RCH ID or village" value={q} onChange={e => setQ(e.target.value)} aria-label="Search patients" /></label>
          <select className="input" value={status} onChange={e => setStatus(e.target.value)} aria-label="Filter by status">
            <option value="">All statuses</option>{Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          {list.loading && !list.data ? <Loading /> : (
            <ul>{list.data?.patients.map(p => (
              <li key={p.patient_id}><button className={p.patient_id === patientId ? "active" : ""} onClick={() => setPatientId(p.patient_id)}
                aria-current={p.patient_id === patientId ? "true" : undefined}>
                <span className={`pl-avatar s-${p.status}`}>{initials(p.name)}</span>
                <span className="pl-text">
                  <span className="pl-name">{p.name}{p.open_followups > 0 && <span className="pl-open" title={`${p.open_followups} open follow-ups`}>{p.open_followups}</span>}</span>
                  <span className="pl-meta">{p.patient_id} · {p.age} y · {LANG_LABEL[p.language]}</span>
                  <span className={`pl-status s-${p.status}`}><i />{STATUS_LABEL[p.status]}</span>
                </span>
              </button></li>))}
              {!list.data?.patients.length && <li><EmptyState title="No patients found" text="Try a different name, ID or status." /></li>}</ul>)}
        </aside>
        <section>{patientId ? <PatientDetail key={patientId} pid={patientId} canClinical={user.role === "doctor"}
          onAsk={(t) => nav("ask", { patientId, askText: t })} /> : <div className="card"><EmptyState icon={<UserRound size={26} />} title="Select a patient" text="Pick a mother from the list to see her linked journey." /></div>}</section>
      </div>
    </div>
  );
}

function PatientDetail({ pid, canClinical, onAsk }: { pid: string; canClinical: boolean; onAsk: (t: string) => void }) {
  const prof = useAsync(() => api.get<Profile>(`/api/patients/${pid}`), [pid]);
  const tl = useAsync(() => api.get<TimelineData>(`/api/patients/${pid}/timeline`), [pid]);
  const [view, setView] = useState<"timeline" | "measures" | "visits" | "docs">("timeline");
  const [sel, setSel] = useState<TLEvent | null>(null);
  const [doc, setDoc] = useState<{ title: string; text: string; date: string; source: string } | null>(null);
  const meas = useAsync(() => canClinical ? api.get<{ series: Record<string, Series> }>(`/api/patients/${pid}/measurements`) : Promise.resolve(null), [pid, canClinical]);
  const docs = useAsync(() => canClinical ? api.get<{ documents: { doc_id: string; title: string; date: string; doc_type: string; source: string }[] }>(`/api/patients/${pid}/documents`) : Promise.resolve(null), [pid, canClinical]);
  if (prof.error) return <ErrorNote error={prof.error} />;
  if (!prof.data) return <Loading />;
  const p = prof.data; const pr = p.pregnancy;
  const visits = (tl.data?.events || []).filter(e => e.ref_type === "visit").slice().reverse();

  return (
    <div className="col" style={{ gap: 16 }}>
      <section className="patient-head">
        <div className="ph-main">
          <div className="avatar">{initials(p.name)}</div>
          <div>
            <h2>{p.name}</h2>
            <div className="small muted">{p.patient_id} · RCH {p.rch_id || "-"} · {p.age} y · prefers <b>{LANG_LABEL[p.language]}</b> · {p.village}, {p.facility}</div>
            <div className="row" style={{ gap: 6, marginTop: 8 }}>
              {pr && <span className={`badge ${STATUS_TONE[pr.status]}`}>{STATUS_LABEL[pr.status]}</span>}
              {p.sources.map(s => <span key={s} className="badge outline" title="Linked source record (master patient index)"><Link2 size={11} />{s.replace("_", " ")}</span>)}
            </div>
          </div>
          <span className="spacer" />
          <div className="ph-actions">
            <button className="btn primary sm" onClick={() => onAsk("Summarize the patient's pregnancy journey so far")}><Sparkles size={15} />Summarize journey</button>
            <button className="btn sm" onClick={() => onAsk("Show the patient's last 3 visits")}><MessageSquareText size={15} />Last 3 visits</button>
          </div>
        </div>
        {pr && <PregnancyProgress ga={pr.ga_today_weeks} />}
        {pr && (
          <div className="ph-facts">
            <div><span>G / P</span><b>G{pr.gravida} P{pr.parity}</b></div>
            <div><span>LMP</span><b>{fmtDate(pr.lmp)}</b></div>
            <div><span>EDD</span><b>{fmtDate(pr.edd)}</b></div>
            <div><span>Registered</span><b>{fmtDate(pr.registration_date)}</b><small>{pr.registration_ga_weeks} w</small></div>
            <div><span>ANC contacts</span><b>{pr.anc_visits_completed}</b></div>
            {pr.ga_today_weeks !== null ? <div><span>GA today (by LMP)</span><b>{pr.ga_today_weeks} w</b></div>
              : pr.delivery_date ? <div><span>Delivered</span><b>{fmtDate(pr.delivery_date)}</b><small>{pr.delivery_mode}</small></div> : null}
          </div>)}
        <div className="ph-foot">
          {p.contact && <span className="small"><Phone size={13} /> {p.contact.phone} · Caregiver: {p.contact.caregiver_name} ({p.contact.caregiver_relation})
            <span className="muted"> · consent: {Object.entries(p.contact.consent).filter(([, v]) => v).map(([k]) => k).join(", ") || "none"}</span></span>}
          {p.children.map(c => <span key={c.child_id} className="small"><Baby size={13} /> {c.name} · {c.sex} · born {fmtDate(c.dob)} · {c.birth_weight_g} g</span>)}
        </div>
      </section>

      <div className="card journey-views">
        <div className="card-head">
          <Seg value={view} onChange={setView} ariaLabel="Journey view" options={[
            { value: "timeline", label: <><CalendarClock size={14} /> Timeline</> },
            ...(canClinical ? [{ value: "measures" as const, label: <>Recorded values</> }] : []),
            { value: "visits", label: <>Visits</> },
            ...(canClinical ? [{ value: "docs" as const, label: <><FileText size={14} /> Documents</> }] : []),
          ]} />
          <span className="spacer" />
          {!canClinical && <span className="badge neutral" title="Minimum-necessary access">Operational view (no clinical values)</span>}
        </div>
        {view === "timeline" && (tl.data ? <Swimlane data={tl.data} onSelect={setSel} /> : <Loading />)}
        {view === "measures" && (meas.data ? <MeasureMultiples series={meas.data.series} /> : <Loading />)}
        {view === "visits" && <DataTable rows={visits} columns={[
          { key: "date", label: "Date", render: r => fmtDate(r.date) }, { key: "label", label: "Visit" },
          { key: "status", label: "Status", render: r => <span className={`badge ${r.status === "completed" ? "ok" : "warn"}`}>{r.status.replace("_", "-")}</span> },
          { key: "detail", label: "Facility · GA" }]} />}
        {view === "docs" && <DataTable rows={docs.data?.documents || []} onRowClick={async (r) => {
          const d = await api.get<{ title: string; text: string; date: string; source: string }>(`/api/patients/${pid}/documents/${r.doc_id}`); setDoc(d); }}
          columns={[{ key: "date", label: "Date", render: r => fmtDate(r.date) }, { key: "title", label: "Document" },
            { key: "doc_type", label: "Type" }, { key: "source", label: "Source system" }]} />}
      </div>

      <Drawer open={!!sel} onClose={() => setSel(null)} title={sel?.label || ""}>
        {sel && <div className="col"><div className="row"><span className="badge neutral">{sel.lane}</span><span className="small">{fmtDate(sel.date)}</span>
          <span className="badge outline">{sel.status}</span></div><p>{sel.detail}</p>
          <p className="tiny muted mono">{sel.ref_type}:{sel.ref_id}</p>
          <button className="btn sm" onClick={() => onAsk(`Show the notes from her ${sel.label} visit`)}>Ask about this event</button></div>}
      </Drawer>
      <Drawer open={!!doc} onClose={() => setDoc(null)} title={doc?.title || ""}>
        {doc && <div className="col"><span className="small muted">{fmtDate(doc.date)} · {doc.source}</span><pre className="source-text">{doc.text}</pre></div>}
      </Drawer>
    </div>
  );
}
