// Population analytics (hospital administration): governed, de-identified operational metrics.
import { useState } from "react";
import { Activity, CalendarCheck2, Code2, FlaskConical, Users } from "lucide-react";
import { api, MetricResult } from "../../api/client";
import { useApp } from "../../app/context";
import { ChartCard } from "../../charts/ChartRenderer";
import { DataTable, ErrorNote, Loading, StatTile, useAsync } from "../../ui/components";

const FACILITIES = [{ id: "", name: "All facilities" }, { id: "F1", name: "PHC Hebbal" }, { id: "F2", name: "District Hospital Tumakuru" }, { id: "F3", name: "CHC Anekal" }];

function weighted(data: any[] | undefined, pctKey: string, nKey: string) {
  if (!data?.length) return null;
  const n = data.reduce((a, d) => a + (d[nKey] || 0), 0);
  return n ? Math.round(10 * data.reduce((a, d) => a + (d[pctKey] || 0) * (d[nKey] || 0), 0) / n) / 10 : null;
}

function Metric({ m, wide }: { m: MetricResult; wide?: boolean }) {
  return (
    <div className={`metric ${wide ? "wide" : ""}`}>
      <div className={`grid ${m.charts.length > 1 ? "g2" : ""}`}>
        {m.charts.map((c, i) => <ChartCard key={c.id} spec={c} definition={i === 0 ? m.definition : undefined} caveat={i === m.charts.length - 1 ? m.caveats[0] : undefined} />)}
      </div>
      <div className="metric-foot">
        <p className="small">{m.narrative}</p>
        <details><summary><Code2 size={13} /> SQL</summary><pre className="sql">{m.sql}</pre></details>
      </div>
    </div>
  );
}

export function AnalyticsPage() {
  const { health } = useApp();
  const [fac, setFac] = useState("");
  const d = useAsync(() => api.get<{ metrics: Record<string, MetricResult> }>(`/api/analytics/dashboard?facility_id=${fac}`), [fac]);
  const M = d.data?.metrics;
  const anc4 = (M?.anc_dropoff.charts[0]?.data as any[] | undefined)?.find(x => x.stage === "ANC4+")?.pct ?? null;
  const recall = (() => { const t = M?.followup_completion.charts[0]?.data as any[] | undefined; if (!t?.length) return null;
    const due = t.reduce((a, x) => a + x.due, 0), ok = t.reduce((a, x) => a + x.on_time, 0); return due ? Math.round(1000 * ok / due) / 10 : null; })();
  const noShow = weighted(M?.no_show_trend.charts[0]?.data as any[], "no_show_pct", "booked");
  const early = weighted(M?.registration_timeliness.charts[0]?.data as any[], "first_trimester_pct", "n");

  return (
    <div className="page analytics">
      <div className="page-head">
        <div><div className="eyebrow">Monitor · population analytics</div><h2>Operational analytics</h2>
          <p>Governed metrics on de-identified views. Definitions avoid common biases (e.g. drop-off only for pregnancies whose EDD has passed). Reference date {health?.reference_date}.</p></div>
      </div>
      <div className="filters sticky-filters">
        <label className="field" style={{ flexDirection: "row", alignItems: "center" }}>Facility
          <select className="input" style={{ width: 260 }} value={fac} onChange={e => setFac(e.target.value)}>
            {FACILITIES.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
        <span className="small muted">Scopes every chart below · Synthetic data</span>
      </div>
      <ErrorNote error={d.error} />
      {!M ? <Loading label="Computing metrics" /> : (
        <div className={`col ${d.loading ? "refetching" : ""}`} style={{ gap: 22 }}>
          <div className="grid g4">
            <StatTile label="Follow-ups completed on time (6 mo)" value={recall} unit="%" icon={<CalendarCheck2 size={18} />} tone="brand" hint="Primary KPI - see KPIs & Pilot" />
            <StatTile label="Completed ≥ 4 ANC contacts" value={anc4} unit="%" icon={<Users size={18} />} tone="blue" hint="Pregnancies with EDD in last 12 months" />
            <StatTile label="ANC no-show rate (12 mo)" value={noShow} unit="%" icon={<Activity size={18} />} tone="coral" hint="EHR facilities" />
            <StatTile label="Registered in 1st trimester" value={early} unit="%" icon={<FlaskConical size={18} />} tone="violet" hint="Last 12 months" />
          </div>
          <Section title="Visit volume"><Metric m={M.visit_volume} wide /></Section>
          <Section title="Antenatal continuity & drop-off"><Metric m={M.anc_dropoff} /></Section>
          <Section title="Follow-up (recall) completion"><Metric m={M.followup_completion} /></Section>
          <div className="grid g2">
            <Section title="No-show trend"><Metric m={M.no_show_trend} /></Section>
            <Section title="Visit frequency"><Metric m={M.visit_frequency} /></Section>
          </div>
          <Section title="Investigation utilization"><Metric m={M.investigation_utilization} /></Section>
          <div className="grid g3">
            <Section title="Early registration"><Metric m={M.registration_timeliness} /></Section>
            <Section title="Postnatal contacts"><Metric m={M.pnc_coverage} /></Section>
            <Section title="Child immunization"><Metric m={M.immunization_coverage} /></Section>
          </div>
          <Section title="Facility comparison">
            <div className="grid g2"><ChartCard spec={M.facility_comparison.charts[0]} caveat={M.facility_comparison.caveats[0]} />
              {M.facility_comparison.table && <div className="card"><h3 style={{ marginBottom: 10 }}>Facility table</h3>
                <DataTable columns={M.facility_comparison.table.columns} rows={M.facility_comparison.table.rows} /></div>}</div>
          </Section>
        </div>)}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section><h3 className="section-title">{title}</h3>{children}</section>;
}
