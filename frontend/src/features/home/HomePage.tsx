// Home: a personal start screen - greeting, ask bar, today's numbers for this role, and four ways in.
import { useEffect, useState } from "react";
import {
  Activity, ArrowRight, ArrowUp, BadgeCheck, Baby, BellRing, CalendarClock, CheckCircle2, ClipboardCheck, FlaskConical,
  HeartPulse, Languages, MessageSquareText, Route, Search, ShieldAlert, ShieldCheck, Sparkles,
} from "lucide-react";
import { api } from "../../api/client";
import { TabId, useApp } from "../../app/context";
import { TABS } from "../../app/Header";
import { shortName } from "../../app/LoginPage";
import { fmtDate, useAsync, useCountUp } from "../../ui/components";
import { MotherIllustration } from "./MotherIllustration";

interface Overview { reference_date: string; tiles: { label: string; value: number | null; unit?: string }[]; suggestions: string[] }

// icon, colour and destination for each overview tile, matched on its label
const TILE_KIND: { test: RegExp; icon: typeof Route; tone: string; tab: TabId }[] = [
  { test: /review/i, icon: ClipboardCheck, tone: "violet", tab: "reviews" },
  { test: /overdue/i, icon: CalendarClock, tone: "coral", tab: "followups" },
  { test: /on time/i, icon: CheckCircle2, tone: "brand", tab: "kpi" },
  { test: /due|follow-up/i, icon: CheckCircle2, tone: "brand", tab: "followups" },
  { test: /reminder/i, icon: BellRing, tone: "blue", tab: "followups" },
  { test: /result/i, icon: FlaskConical, tone: "coral", tab: "journey" },
  { test: /antenatal/i, icon: Baby, tone: "brand", tab: "journey" },
  { test: /ANC/, icon: HeartPulse, tone: "brand", tab: "analytics" },
  { test: /visit/i, icon: Activity, tone: "blue", tab: "analytics" },
  { test: /guardrail|blocked/i, icon: ShieldAlert, tone: "violet", tab: "trust" },
];

const LEAD = {
  doctor: "Records, timelines and verified summaries for every patient - one question away.",
  coordinator: "Today's follow-ups, reminders and patient tracking, in one place.",
  admin: "Visit volume, ANC completion and follow-up performance across the registry.",
};

// greeting and date follow the clinic's clock (IST), whatever the viewer's device is set to
const IST = "Asia/Kolkata";
const istHour = (d: Date) => Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone: IST }).format(d));
const greeting = (d: Date) => { const h = istHour(d); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; };
const longDate = (d: Date) => new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: IST }).format(d);

// re-renders once a minute so a page left open rolls over to the next greeting / day
function useNow() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 60_000); return () => clearInterval(id); }, []);
  return now;
}

function Tile({ label, value, unit, onOpen }: { label: string; value: number | null; unit?: string; onOpen?: () => void }) {
  const k = TILE_KIND.find(t => t.test.test(label)); const Icon = k?.icon || Activity;
  const shown = useCountUp(value);
  const body = <>
    <span className="tile-top"><span className={`tile-icon tone-${k?.tone || "brand"}`}><Icon size={18} /></span>
      {onOpen && <ArrowRight className="tile-go" size={16} />}</span>
    <span className="tile-value num">{shown ?? "-"}{unit && value != null && <small>{unit}</small>}</span>
    <span className="tile-label">{label}</span>
  </>;
  return onOpen ? <button className="tile" onClick={onOpen}>{body}</button> : <div className="tile">{body}</div>;
}

export function HomePage() {
  const { user, nav } = useApp();
  const [q, setQ] = useState("");
  const now = useNow();
  const ov = useAsync(() => api.get<Overview>("/api/overview"), []);
  const admin = user.role === "admin";
  const allowed = new Set(TABS.filter(t => t.roles.includes(user.role)).map(t => t.id));
  const pending = ov.data?.tiles.find(t => /review/i.test(t.label))?.value || 0;
  const primary = user.role === "coordinator" ? { label: "Open follow-ups", tab: "followups" as TabId }
    : admin ? { label: "Open analytics", tab: "analytics" as TabId } : { label: "Open patient journey", tab: "journey" as TabId };
  const name = admin ? "" : user.role === "doctor" ? shortName(user.display_name).split(" ").slice(0, 2).join(" ") : shortName(user.display_name).split(" ")[0];
  const ask = (text: string) => { if (text.trim()) nav("ask", { askText: text.trim() }); };

  const PILLARS: { title: string; text: string; icon: typeof Route; tone: string; tab: TabId }[] = [
    { title: "Ask", text: "Question the record in plain English - or by voice.", icon: MessageSquareText, tone: "blue", tab: "ask" },
    { title: "Journey", text: "One mother–baby timeline across every source.", icon: Route, tone: "brand", tab: admin ? "analytics" : "journey" },
    { title: "Monitor", text: "Follow-ups and trends, before anyone is missed.", icon: BellRing, tone: "violet", tab: admin ? "analytics" : "followups" },
    { title: "Communicate", text: "Reports and reminders in Kannada, Hindi, Bengali.", icon: Languages, tone: "coral", tab: admin ? "kpi" : user.role === "doctor" ? "journey" : "followups" },
  ];

  return (
    <div className="page home">
      <section className="home-hero">
        <div className="home-copy">
          <div className="eyebrow rise">{longDate(now)}</div>
          <h1 className="rise" style={{ "--d": "60ms" } as React.CSSProperties}>{name ? <>{greeting(now)},<br />{name}.</> : `${greeting(now)}.`}</h1>
          <p className="lead rise" style={{ "--d": "120ms" } as React.CSSProperties}>{LEAD[user.role]}</p>

          <form className="ask-bar rise" style={{ "--d": "180ms" } as React.CSSProperties} onSubmit={e => { e.preventDefault(); ask(q); }} role="search">
            <Search size={19} className="ask-bar-icon" aria-hidden="true" />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Ask anything about your patients…" aria-label="Ask ClinieSync" />
            <button className="ask-bar-go" disabled={!q.trim()} aria-label="Ask"><ArrowUp size={18} /></button>
          </form>
          {!!ov.data?.suggestions.length && (
            <div className="ask-suggest rise" style={{ "--d": "240ms" } as React.CSSProperties}>
              <span><Sparkles size={14} />Try</span>
              {ov.data.suggestions.map(s => <button key={s} className="chip-btn" onClick={() => ask(s)}>{s}</button>)}
            </div>)}

          <div className="home-actions rise" style={{ "--d": "300ms" } as React.CSSProperties}>
            <button className="btn primary lg" onClick={() => nav(primary.tab)}>{primary.label}<ArrowRight size={17} /></button>
            {pending > 0 && allowed.has("reviews") && (
              <button className="nudge" onClick={() => nav("reviews")}>
                <span className="nudge-dot" /><b>{pending}</b> answers awaiting review<ArrowRight size={14} /></button>)}
          </div>
        </div>

        <div className="home-art" aria-hidden="true">
          <MotherIllustration className="landing-illus" />
          <div className="float-card fc-1">
            <span className="fc-icon brand"><BadgeCheck size={16} /></span>
            <div><b>Summary verified</b><small>8 sources cited</small></div>
          </div>
          <div className="float-card fc-2">
            <span className="fc-icon coral"><CalendarClock size={16} /></span>
            <div><b>PNC visit · day 7</b><small lang="kn">ಜ್ಞಾಪನೆ ಕಳುಹಿಸಲಾಗಿದೆ</small></div>
          </div>
        </div>
      </section>

      <section className="home-section">
        <div className="home-section-head"><h2>At a glance</h2>{ov.data && <span className="muted small">Synthetic registry · data as of {fmtDate(ov.data.reference_date)}</span>}</div>
        <div className="tiles">
          {ov.data ? ov.data.tiles.map(t => {
            const dest = TILE_KIND.find(k => k.test.test(t.label))?.tab;
            return <Tile key={t.label} {...t} onOpen={dest && allowed.has(dest) ? () => nav(dest) : undefined} />;
          }) : [0, 1, 2, 3].map(i => <div key={i} className="tile skeleton" />)}
        </div>
      </section>

      <section className="home-section">
        <div className="home-section-head"><h2>Four ways in</h2></div>
        <div className="pillars">
          {PILLARS.map(p => (
            <button key={p.title} className={`pillar tone-${p.tone}`} onClick={() => nav(p.tab)}
              onPointerMove={e => { const r = e.currentTarget.getBoundingClientRect();
                e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`); e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`); }}>
              <span className="pillar-icon"><p.icon size={20} /></span>
              <b>{p.title}</b>
              <span className="pillar-text">{p.text}</span>
              <span className="pillar-go"><ArrowRight size={15} /></span>
            </button>
          ))}
        </div>
      </section>

      <footer className="foot">
        <span><ShieldCheck size={14} />Assistive, not diagnostic · every answer cited and verified by a clinician</span>
        <span>Team ClinieSync · TANUH, IISc Bangalore · Synthetic data only</span>
      </footer>
    </div>
  );
}
