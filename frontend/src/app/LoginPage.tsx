// Sign-in page: a scroll-driven story (population -> one mother -> her journey through time), then the role cards.
import { useEffect, useRef, useState } from "react";
import { ArrowDown, BarChart3, ClipboardList, LogIn, ShieldCheck, Stethoscope } from "lucide-react";
import { api, setToken, User } from "../api/client";
import { Card3D } from "../ui/components";
import { Logo } from "./Header";
import { ease, GlobeCanvas, PregnancyClock, seg, STAGES, TAU_END, useScrollProgress } from "./intro/CareJourneyScene";

const ROLE_INFO = {
  doctor: { icon: Stethoscope, blurb: "Patient history, longitudinal timelines, EHR queries, clinical summaries, Share Report", tone: "brand" },
  coordinator: { icon: ClipboardList, blurb: "Follow-up queues, patient tracking, multilingual reminders with approval", tone: "blue" },
  admin: { icon: BarChart3, blurb: "Population analytics, visit volume, investigation utilization, KPIs", tone: "violet" },
} as const;

const CHAPTERS = [{ at: 0, label: "600 mothers" }, { at: 0.24, label: "One mother" }, { at: 0.48, label: "Her journey" }, { at: 0.96, label: "Sign in" }];

export function LoginPage({ onLogin }: { onLogin: (u: User) => void }) {
  const [demo, setDemo] = useState<{ password: string; users: User[] } | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const scroller = useRef<HTMLElement>(null);
  const p = useScrollProgress(scroller);
  const reduce = typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  useEffect(() => { api.get<{ password: string; users: User[] }>("/api/auth/demo-users").then(setDemo).catch(() => null); }, []);

  const login = async (u: string, pw: string) => {
    setBusy(true); setErr(null);
    try {
      const r = await api.post<{ token: string; user: User }>("/api/auth/login", { username: u, password: pw });
      setToken(r.token); onLogin(r.user);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const toRoles = () => document.getElementById("roles")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
  const toPoint = (at: number) => {
    const el = scroller.current; if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY + at * (el.offsetHeight - window.innerHeight);
    window.scrollTo({ top: top + 2, behavior: reduce ? "auto" : "smooth" });
  };

  const copyOut = seg(p, 0.08, 0.2);
  const caption = seg(p, 0.2, 0.27) * (1 - seg(p, 0.4, 0.46));
  const clockIn = seg(p, 0.44, 0.5);
  const tau = ease(seg(p, 0.5, 0.94)) * TAU_END;
  const chapter = CHAPTERS.reduce((a, c, i) => (p >= c.at - 0.001 ? i : a), 0);

  return (
    <div className="intro">
      <header className="intro-nav">
        <div className="intro-brand"><Logo size={34} /><span><b>ClinieSync</b><small>MCH Operations Copilot</small></span></div>
        <div className="intro-progress" aria-hidden="true"><span style={{ transform: `scaleX(${p})` }} /></div>
        <button className="btn primary sm" onClick={toRoles}><LogIn size={15} />Sign in</button>
      </header>

      <section className="intro-scroll" ref={scroller} aria-label="ClinieSync introduction">
        <div className="intro-sticky">
          <GlobeCanvas progress={p} reduce={reduce} />

          <div className="intro-copy" style={{ opacity: 1 - copyOut, transform: `translateY(${-copyOut * 30}px)`, pointerEvents: copyOut > 0.6 ? "none" : undefined }}>
            <div className="eyebrow">Health-a-thon 2026 · Team ClinieSync · TANUH, IISc Bangalore</div>
            <h1>Every mother.<br />Every visit.<br /><span className="grad">In sync.</span></h1>
            <p className="lead">The maternal &amp; child health copilot that turns scattered records into answers, timelines and timely follow-ups - in the patient's language.</p>
            <div className="row" style={{ gap: 12, marginTop: 24 }}>
              <button className="btn primary lg" onClick={toRoles}><LogIn size={18} />Sign in</button>
              <button className="btn lg" onClick={() => toPoint(0.5)}>Explore her journey<ArrowDown size={17} /></button>
            </div>
            <ul className="intro-legend" aria-label="Dot colours">
              {STAGES.map(s => <li key={s.key}><i style={{ background: `rgb(${s.color.join(",")})` }} />{s.label}</li>)}
            </ul>
          </div>

          <div className="intro-caption" style={{ opacity: caption }} aria-hidden={caption < 0.5}>
            <b>Every dot is a mother in the registry.</b><span>Let's zoom in on one of them.</span>
          </div>

          <PregnancyClock tau={tau} visible={clockIn} />

          <nav className="intro-chapters" aria-label="Story chapters">
            {CHAPTERS.map((c, i) => (
              <button key={c.label} className={i === chapter ? "on" : ""} onClick={() => i === CHAPTERS.length - 1 ? toRoles() : toPoint(c.at)}>
                <i /><span>{c.label}</span></button>))}
          </nav>
          <div className="intro-hint" style={{ opacity: 1 - seg(p, 0, 0.05) }} aria-hidden="true"><span className="mouse" />Scroll to explore</div>
        </div>
      </section>

      <section id="roles" className="intro-roles">
        <div className="eyebrow">Choose your role</div>
        <h2>One record. Three ways to work.</h2>
        <div className="grid g3" style={{ marginTop: 22 }}>
          {(demo?.users || []).map(u => {
            const info = ROLE_INFO[u.role]; const Icon = info.icon;
            return (
              <Card3D key={u.username} className={`role-card tone-${info.tone}`} tilt={8}>
                <span className="role-icon lift"><Icon size={26} /></span>
                <h3 className="lift">{u.display_name}</h3>
                <p className="small muted">{info.blurb}</p>
                <button className="btn primary" disabled={busy} onClick={() => login(u.username, demo!.password)}>Continue</button>
              </Card3D>
            );
          })}
        </div>
        <details style={{ marginTop: 18 }}>
          <summary>Sign in with username &amp; password</summary>
          <form className="row" style={{ marginTop: 10 }} onSubmit={e => { e.preventDefault(); login(username, password); }}>
            <input className="input" style={{ maxWidth: 220 }} placeholder="username" value={username} onChange={e => setUsername(e.target.value)} />
            <input className="input" style={{ maxWidth: 220 }} type="password" placeholder="password" value={password} onChange={e => setPassword(e.target.value)} />
            <button className="btn primary" disabled={busy}>Sign in</button>
          </form>
          {demo && <p className="tiny muted" style={{ marginTop: 6 }}>Demo password: <span className="mono">{demo.password}</span></p>}
        </details>
        {err && <div className="callout bad" style={{ marginTop: 12 }}>{err}</div>}
        <div className="callout brand" style={{ marginTop: 22, maxWidth: 680 }}><ShieldCheck size={18} />
          <span>Assistive, not diagnostic. AI only retrieves, organises, summarises and coordinates; every answer is verified by a human.
            This demo runs on <b>synthetic data only</b>.</span></div>
      </section>
    </div>
  );
}
