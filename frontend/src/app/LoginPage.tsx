// Sign-in page: a scroll-driven story (population -> one mother -> her journey through time), then the role cards.
import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowRight, BarChart3, ClipboardList, Database, Eye, EyeOff, LogIn, ShieldCheck, Stethoscope, UserCheck } from "lucide-react";
import { api, setToken, User } from "../api/client";
import { Aurora, BackToTop, prefersReducedMotion, usePageScroll } from "../ui/components";
import { Logo } from "./Header";
import { ease, GlobeCanvas, PregnancyClock, seg, STAGES, TAU_END, useScrollProgress } from "./intro/CareJourneyScene";

const ROLE_INFO = {
  doctor: { icon: Stethoscope, kicker: "Clinician", tone: "brand",
    skills: ["Patient history", "Longitudinal timelines", "EHR queries", "Clinical summaries", "Share Report"] },
  coordinator: { icon: ClipboardList, kicker: "Care coordination", tone: "blue",
    skills: ["Follow-up queues", "Patient tracking", "Multilingual reminders with approval"] },
  admin: { icon: BarChart3, kicker: "Hospital operations", tone: "violet",
    skills: ["Population analytics", "Visit volume", "Investigation utilization", "KPIs"] },
} as const;

const PRINCIPLES = [
  { icon: ShieldCheck, title: "Assistive, not diagnostic", text: "AI only retrieves, organises, summarises and coordinates." },
  { icon: UserCheck, title: "Verified by a human", text: "Every answer is checked by a person before anyone acts on it." },
  { icon: Database, title: "Synthetic data only", text: "This demo runs on a simulated registry - no real patients." },
];

const CHAPTERS = [{ at: 0, label: "600 mothers" }, { at: 0.24, label: "One mother" }, { at: 0.48, label: "Her journey" }, { at: 0.96, label: "Sign in" }];

// "Rekha S. (Care Coordinator)" -> "Rekha S."; the role is shown separately on the card
export const shortName = (n: string) => n.replace(/\s*\(.*\)\s*$/, "");

// true while the element is on screen; `once` keeps it true after the first sighting (for reveal animations)
function useInView(ref: React.RefObject<Element>, once = false) {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setSeen(true); if (once) io.disconnect(); } else if (!once) setSeen(false);
    }, { rootMargin: "0px 0px -15% 0px" });
    io.observe(el); return () => io.disconnect();
  }, [ref, once]);
  return seen;
}

export function LoginPage({ onLogin }: { onLogin: (u: User) => void }) {
  const [demo, setDemo] = useState<{ password: string; users: User[] } | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const scroller = useRef<HTMLElement>(null);
  const copy = useRef<HTMLDivElement>(null);
  const roles = useRef<HTMLElement>(null);
  const p = useScrollProgress(scroller);
  const page = usePageScroll();
  const rolesShown = useInView(roles, true);
  const rolesOnScreen = useInView(roles);
  const reduce = prefersReducedMotion();
  useEffect(() => { api.get<{ password: string; users: User[] }>("/api/auth/demo-users").then(setDemo).catch(() => null); }, []);

  const login = async (u: string, pw: string) => {
    setPending(u); setErr(null);
    try {
      const r = await api.post<{ token: string; user: User }>("/api/auth/login", { username: u, password: pw });
      setToken(r.token); onLogin(r.user);
    } catch (e: any) { setErr(e.message); setPending(null); }
  };

  const behavior = reduce ? "auto" : "smooth";
  const toRoles = () => roles.current?.scrollIntoView({ behavior });
  const toPoint = (at: number) => {
    const el = scroller.current; if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY + at * (el.offsetHeight - window.innerHeight);
    window.scrollTo({ top: top + 2, behavior });
  };
  const glow = (e: React.PointerEvent<HTMLElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`); e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  const copyOut = seg(p, 0.08, 0.2);
  const caption = seg(p, 0.2, 0.27) * (1 - seg(p, 0.4, 0.46));
  const clockIn = seg(p, 0.44, 0.5);
  const tau = ease(seg(p, 0.5, 0.94)) * TAU_END;
  const chapter = CHAPTERS.reduce((a, c, i) => (p >= c.at - 0.001 ? i : a), 0);

  return (
    <div className="intro">
      <Aurora />

      {/* transparent over the hero; frosts once the page scrolls. The sign-in button steps aside when the role cards are on screen. */}
      <header className={`intro-nav ${page.y > 8 ? "scrolled" : ""}`}>
        <div className="intro-nav-inner">
          <button className="intro-brand" onClick={() => window.scrollTo({ top: 0, behavior })} aria-label="ClinieSync, back to top">
            <Logo size={30} /><b>ClinieSync</b></button>
          <button className={`cta primary sm nav-signin ${rolesOnScreen ? "away" : ""}`} onClick={toRoles} tabIndex={rolesOnScreen ? -1 : 0}>
            <LogIn size={15} />Sign in</button>
        </div>
        <div className="intro-progress" aria-hidden="true"><span style={{ transform: `scaleX(${page.p})` }} /></div>
      </header>

      <section className="intro-scroll" ref={scroller} aria-label="ClinieSync introduction">
        <div className="intro-sticky">
          <GlobeCanvas progress={p} reduce={reduce} avoid={copy} />

          <div className="intro-copy" ref={copy} style={{ opacity: 1 - copyOut, transform: `translateY(${-copyOut * 30}px)`, pointerEvents: copyOut > 0.6 ? "none" : undefined }}>
            <div className="eyebrow rise">Health-a-thon 2026 · Team ClinieSync · TANUH, IISc Bangalore</div>
            <h1 className="rise" style={{ "--d": "80ms" } as React.CSSProperties}>Every mother.<br />Every visit.<br /><span className="grad">In sync.</span></h1>
            <p className="lead rise" style={{ "--d": "160ms" } as React.CSSProperties}>The maternal &amp; child health copilot that turns scattered records into answers, timelines and timely follow-ups - in the patient's language.</p>
            <div className="intro-ctas rise" style={{ "--d": "240ms" } as React.CSSProperties}>
              <button className="cta primary" onClick={toRoles}>Sign in<span className="arr"><ArrowRight size={17} /></span></button>
              <button className="cta glass" onClick={() => toPoint(0.5)}>Explore her journey<span className="arr"><ArrowDown size={17} /></span></button>
            </div>
            <ul className="intro-legend rise" style={{ "--d": "320ms" } as React.CSSProperties} aria-label="Dot colours">
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

      <section id="roles" ref={roles} className={`intro-roles ${rolesShown ? "in" : ""}`}>
        <div className="roles-head">
          <div>
            <div className="eyebrow">Choose your role</div>
            <h2>One record. Three ways to work.</h2>
          </div>
          <p className="muted">Pick a demo account to step straight in.</p>
        </div>

        <div className="role-grid">
          {(demo?.users || []).map((u, i) => {
            const info = ROLE_INFO[u.role]; const Icon = info.icon; const name = shortName(u.display_name);
            return (
              <button key={u.username} className={`role-card tone-${info.tone}`} style={{ "--d": `${i * 90}ms` } as React.CSSProperties}
                disabled={!!pending} onPointerMove={glow} onClick={() => login(u.username, demo!.password)}
                aria-label={`Continue as ${u.display_name}`}>
                <span className="role-icon"><Icon size={24} /></span>
                <span className="role-body">
                  <span className="role-kicker">{info.kicker}</span>
                  <span className="role-name">{name}</span>
                  <span className="role-skills">{info.skills.map(s => <span key={s}>{s}</span>)}</span>
                </span>
                <span className="role-go">
                  {pending === u.username ? <><span className="spin" />Signing in…</> : <span className="role-go-label">Continue as {name.split(" ").slice(0, 2).join(" ")}</span>}
                  <span className="arr"><ArrowRight size={16} /></span>
                </span>
              </button>
            );
          })}
          {!demo && [0, 1, 2].map(i => <div key={i} className="role-card skeleton" aria-hidden="true" />)}
        </div>

        <div className="or-line"><span>or sign in with a username</span></div>

        <form className="signin-card" onSubmit={e => { e.preventDefault(); login(username, password); }}>
          <label className="sf">Username
            <input className="input" autoComplete="username" placeholder="e.g. dr.ananya" value={username} onChange={e => setUsername(e.target.value)} required />
          </label>
          <label className="sf">Password
            <span className="pw">
              <input className="input" type={showPw ? "text" : "password"} autoComplete="current-password" placeholder="Your password"
                value={password} onChange={e => setPassword(e.target.value)} required />
              <button type="button" className="pw-eye" onClick={() => setShowPw(v => !v)} aria-label={showPw ? "Hide password" : "Show password"}>
                {showPw ? <EyeOff size={17} /> : <Eye size={17} />}</button>
            </span>
          </label>
          <button className="cta primary" disabled={!!pending}>
            {pending && pending === username ? <><span className="spin light" />Signing in…</> : <>Sign in<span className="arr"><ArrowRight size={17} /></span></>}</button>
          {demo && <p className="sf-hint">Demo password: <button type="button" className="linkish" onClick={() => setPassword(demo.password)}>
            <span className="mono">{demo.password}</span> · use it</button></p>}
        </form>
        {err && <div className="callout bad fade-in" role="alert" style={{ marginTop: 14 }}>{err}</div>}

        <ul className="principles">
          {PRINCIPLES.map(({ icon: Icon, title, text }) => (
            <li key={title}><span className="pr-icon"><Icon size={18} /></span><span><b>{title}</b>{text}</span></li>))}
        </ul>
      </section>

      <footer className="intro-foot">
        <Logo size={20} /><span>ClinieSync · Health-a-thon 2026 · TANUH, IISc Bangalore</span>
      </footer>

      <BackToTop />
    </div>
  );
}
