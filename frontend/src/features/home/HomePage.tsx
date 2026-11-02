// Home: a calm landing page - one message, one illustration, four ways in. Detail lives in the feature tabs.
import { ArrowRight, BadgeCheck, BellRing, CalendarClock, Languages, MessageSquareText, Route, ShieldCheck } from "lucide-react";
import { api } from "../../api/client";
import { TabId, useApp } from "../../app/context";
import { useAsync } from "../../ui/components";
import { MotherIllustration } from "./MotherIllustration";

export function HomePage() {
  const { user, nav } = useApp();
  const ov = useAsync(() => api.get<{ tiles: { label: string; value: number | null }[] }>("/api/overview"), []);
  const pending = ov.data?.tiles.find(t => /review/i.test(t.label))?.value || 0;
  const admin = user.role === "admin";
  const primary = user.role === "coordinator" ? { label: "Open follow-ups", tab: "followups" as TabId }
    : admin ? { label: "Open analytics", tab: "analytics" as TabId } : { label: "Open patient journey", tab: "journey" as TabId };

  const PILLARS: { title: string; text: string; icon: typeof Route; tone: string; tab: TabId }[] = [
    { title: "Ask", text: "Question the record in plain English - or by voice.", icon: MessageSquareText, tone: "blue", tab: "ask" },
    { title: "Journey", text: "One mother–baby timeline across every source.", icon: Route, tone: "brand", tab: admin ? "analytics" : "journey" },
    { title: "Monitor", text: "Follow-ups and trends, before anyone is missed.", icon: BellRing, tone: "violet", tab: admin ? "analytics" : "followups" },
    { title: "Communicate", text: "Reports and reminders in Kannada, Hindi, Bengali.", icon: Languages, tone: "coral", tab: admin ? "kpi" : user.role === "doctor" ? "journey" : "followups" },
  ];

  return (
    <div className="page landing">
      <section className="landing-hero">
        <div className="landing-copy fade-in">
          <div className="eyebrow">Maternal &amp; child health · Operations copilot</div>
          <h1>Every mother's<br />journey, <span className="grad">in sync.</span></h1>
          <p className="lead">Ask the record, follow the timeline and keep every follow-up on track - so clinicians spend time with mothers, not screens.</p>
          <div className="row landing-cta">
            <button className="btn primary lg" onClick={() => nav("ask")}><MessageSquareText size={18} />Ask ClinieSync</button>
            <button className="btn lg" onClick={() => nav(primary.tab)}>{primary.label}<ArrowRight size={17} /></button>
          </div>
          {pending > 0 && (
            <button className="nudge" onClick={() => nav("reviews")}>
              <span className="nudge-dot" /><b>{pending}</b> answers awaiting your review<ArrowRight size={14} /></button>)}
          <p className="landing-trust"><ShieldCheck size={15} />Assistive, not diagnostic · every answer cited and verified by a clinician</p>
        </div>

        <div className="landing-art">
          <MotherIllustration className="landing-illus" />
          <div className="float-card fc-1" aria-hidden="true">
            <span className="fc-icon brand"><BadgeCheck size={16} /></span>
            <div><b>Summary verified</b><small>8 sources cited</small></div>
          </div>
          <div className="float-card fc-2" aria-hidden="true">
            <span className="fc-icon coral"><CalendarClock size={16} /></span>
            <div><b>PNC visit · day 7</b><small lang="kn">ಜ್ಞಾಪನೆ ಕಳುಹಿಸಲಾಗಿದೆ</small></div>
          </div>
        </div>
      </section>

      <section className="pillars">
        {PILLARS.map(p => (
          <button key={p.title} className={`pillar tone-${p.tone}`} onClick={() => nav(p.tab)}>
            <span className="pillar-icon"><p.icon size={20} /></span>
            <b>{p.title}</b>
            <span className="pillar-text">{p.text}</span>
            <ArrowRight className="pillar-go" size={16} />
          </button>
        ))}
      </section>

      <footer className="foot">
        <span>Team ClinieSync · TANUH, IISc Bangalore · Health-a-thon 2026</span>
        <span>Synthetic data only · Not for clinical use</span>
      </footer>
    </div>
  );
}
