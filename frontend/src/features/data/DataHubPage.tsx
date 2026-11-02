// Data Hub (admin): sources -> ETL stages -> unified layer -> SQL + vector stores, with data-quality evidence.
import { useState } from "react";
import { Database, FileSpreadsheet, FileText, GitMerge, Play, Server, Sparkles, Upload } from "lucide-react";
import { api } from "../../api/client";
import { Card3D, DataTable, ErrorNote, Loading, useAsync } from "../../ui/components";

export function DataHubPage() {
  const q = useAsync(() => api.get<{ report: any; manifest: any; etl: { running: boolean; last_finished: string | null; last_error: string | null } }>("/api/data/quality"), []);
  const [preview, setPreview] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  if (!q.data) return <div className="page"><Loading /></div>;
  const r = q.data.report;
  const steps = r?.steps || {};
  const upload = async (f: File) => {
    setErr(null); setPreview(null);
    const fd = new FormData(); fd.append("file", f);
    try { setPreview(await api.upload("/api/data/register/preview", fd)); } catch (e: any) { setErr(e.message); }
  };
  const runEtl = async () => { setErr(null); try { await api.post("/api/data/etl/run"); setMsg("ETL started in the background - refresh in a minute."); } catch (e: any) { setErr(e.message); } };
  const SRC_ICON: Record<string, JSX.Element> = { "EHR CSV export": <Server size={18} />, "Excel ANC register (wide)": <FileSpreadsheet size={18} />, "PDF lab/imaging reports": <FileText size={18} /> };

  return (
    <div className="page datahub">
      <div className="page-head"><div><div className="eyebrow">Meet the clinic where it is</div><h2>Data Hub</h2>
        <p>Light-touch integration: ClinieSync reads what clinics already have - EHR/HMIS exports, Excel registers, PDF reports and notes - and builds one unified, traceable layer. Last run {r?.run_at?.replace("T", " ")}.</p></div>
        <span className="spacer" /><button className="btn" onClick={runEtl} disabled={q.data.etl.running}><Play size={15} />{q.data.etl.running ? "ETL running…" : "Re-run ETL"}</button></div>
      {msg && <div className="callout ok">{msg}</div>}<ErrorNote error={err} />

      <div className="flow">
        <div className="flow-col"><h4>1 · Sources</h4>
          {r?.sources.map((s: any) => (
            <Card3D key={s.source} className="flow-card" tilt={6}><span className="lift flow-icon">{SRC_ICON[s.type] || <Database size={18} />}</span>
              <b>{s.type}</b><span className="tiny muted mono">{s.source}</span>
              <span className="tiny">{Object.entries(s.rows).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ")}</span></Card3D>))}
        </div>
        <div className="flow-col"><h4>2 · ETL &amp; cleaning</h4>
          <Card3D className="flow-card" tilt={6}><b>Clean</b><span className="tiny">Day-first date parsing (4 formats), phone → E.164, name casing, de-duplication
            ({steps.visits?.duplicates_removed ?? 0} visit + {steps.observations?.duplicates_removed ?? 0} observation duplicates)</span></Card3D>
          <Card3D className="flow-card" tilt={6}><b>Quarantine</b><span className="tiny">{r?.quarantine.total} rows failed data-entry plausibility checks - kept with reasons, never silently dropped</span>
            {Object.entries(r?.quarantine.by_reason || {}).map(([k, v]) => <span key={k} className="tiny muted">{k}: {String(v)}</span>)}</Card3D>
        </div>
        <div className="flow-col"><h4>3 · Normalise &amp; link</h4>
          <Card3D className="flow-card" tilt={6}><b>Controlled vocabulary</b><span className="tiny">Local names → canonical codes + LOINC (Hb 718-7, weight 29463-7, BP 8480-6/8462-4…); units g% → g/dL, grams → kg; wide register melted to visits</span></Card3D>
          <Card3D className="flow-card" tilt={6}><span className="lift flow-icon"><GitMerge size={18} /></span><b>Master patient index</b>
            <span className="tiny">{steps.patient_linkage?.source_records} source records → <b>{steps.patient_linkage?.canonical_patients}</b> patients
              ({steps.patient_linkage?.by_rch_id} via RCH ID, {steps.patient_linkage?.by_name_phone} via name + phone); {steps.patient_linkage?.patients_in_multiple_sources} patients seen in 2+ sources</span></Card3D>
          <Card3D className="flow-card" tilt={6}><span className="lift flow-icon"><Sparkles size={18} /></span><b>Documented follow-ups</b>
            <span className="tiny">{r?.followups.extracted_from_notes} instructions extracted from notes; {r?.followups.note_instructions_matched_to_appointments} matched to bookings, {r?.followups.new_followups_from_notes} unbooked</span></Card3D>
        </div>
        <div className="flow-col"><h4>4 · Unified storage</h4>
          <Card3D className="flow-card" tilt={6}><span className="lift flow-icon"><Database size={18} /></span><b>Structured (SQL)</b>
            <span className="tiny">{Object.entries(r?.load.rows_loaded || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}</span></Card3D>
          <Card3D className="flow-card" tilt={6}><span className="lift flow-icon"><FileText size={18} /></span><b>Unstructured (vector)</b>
            <span className="tiny">{r?.index.backend} · {r?.index.chunks_indexed} chunks · {r?.index.embedding_model}</span></Card3D>
        </div>
      </div>

      <div className="grid g2" style={{ marginTop: 18 }}>
        <div className="card">
          <h3><Upload size={16} /> Validate a new Excel ANC register</h3>
          <p className="tiny muted" style={{ margin: "4px 0 10px" }}>Preview what the ETL would extract (no data is loaded). Use the generated file in data/raw/register_F3/ to try it.</p>
          <input type="file" accept=".xlsx,.xls" onChange={e => e.target.files?.[0] && upload(e.target.files[0])} />
          {preview && (<div className="col fade-in" style={{ marginTop: 12 }}>
            <div className="kpi-mini four">{Object.entries(preview.checks).map(([k, v]) => <div key={k}><span>{k.replace(/_/g, " ")}</span><b>{String(v)}</b></div>)}</div>
            <DataTable rows={preview.sample} columns={Object.keys(preview.sample[0] || {}).slice(0, 7).map(k => ({ key: k, label: k.replace(/_/g, " ") }))} /></div>)}
        </div>
        <div className="card">
          <h3>Quarantine examples</h3>
          <DataTable rows={(r?.quarantine.examples || []).map((x: any) => ({ source: x.source, table: x.table, reason: x.reason, record: JSON.stringify(x.record).slice(0, 120) }))}
            columns={[{ key: "source", label: "Source" }, { key: "table", label: "Table" }, { key: "reason", label: "Reason" }, { key: "record", label: "Record" }]} />
          <p className="tiny muted" style={{ marginTop: 8 }}>ETL timings: {Object.entries(r?.timings || {}).map(([k, v]) => `${k} ${v}s`).join(" · ")}</p>
        </div>
      </div>
    </div>
  );
}
