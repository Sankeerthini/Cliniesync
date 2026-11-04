import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  BarChart3, BellRing, ClipboardCheck, Cpu, Database, Home, LogOut, Menu, MessageSquareText, Route, Search, ShieldCheck, Target, X,
} from "lucide-react";
import type { Role } from "../api/client";
import { usePageScroll } from "../ui/components";
import { CommandPalette, isMac } from "./CommandPalette";
import { TabId, useApp } from "./context";

export const TABS: { id: TabId; label: string; icon: typeof Home; roles: Role[] }[] = [
  { id: "home", label: "Home", icon: Home, roles: ["doctor", "coordinator", "admin"] },
  { id: "ask", label: "Ask", icon: MessageSquareText, roles: ["doctor", "coordinator", "admin"] },
  { id: "journey", label: "Patient Journey", icon: Route, roles: ["doctor", "coordinator"] },
  { id: "followups", label: "Follow-ups", icon: BellRing, roles: ["coordinator", "doctor"] },
  { id: "analytics", label: "Analytics", icon: BarChart3, roles: ["admin"] },
  { id: "reviews", label: "Reviews", icon: ClipboardCheck, roles: ["doctor", "coordinator", "admin"] },
  { id: "kpi", label: "KPIs & Pilot", icon: Target, roles: ["admin", "doctor", "coordinator"] },
  { id: "data", label: "Data Hub", icon: Database, roles: ["admin"] },
  { id: "trust", label: "Trust Center", icon: ShieldCheck, roles: ["doctor", "coordinator", "admin"] },
];

const ROLE_LABEL: Record<Role, string> = { doctor: "Doctor", coordinator: "Care Coordinator", admin: "Hospital Administration" };

export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#14a3a0" /><stop offset="1" stopColor="#1f5fd1" /></linearGradient></defs>
      <rect width="64" height="64" rx="18" fill="url(#lg)" />
      <circle cx="26" cy="22" r="7" fill="#fff" />
      <path d="M14 46c0-9 6-15 13-15 4 0 7 2 9 4" stroke="#fff" strokeWidth="5" fill="none" strokeLinecap="round" />
      <circle cx="40" cy="38" r="5" fill="#fff" />
      <path d="M46 20a14 14 0 0 1 4 10" stroke="#bff3ee" strokeWidth="4" fill="none" strokeLinecap="round" />
    </svg>
  );
}

const initials = (n: string) => n.replace(/\s*\(.*\)\s*$/, "").replace(/^Dr\.\s*/, "").split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();

export function Header({ tab }: { tab: TabId }) {
  const { user, nav, health, logout } = useApp();
  const tabs = TABS.filter(t => t.roles.includes(user.role));
  const llmOk = health?.llm.available;
  const { p, y } = usePageScroll();
  const [menu, setMenu] = useState(false);
  const [palette, setPalette] = useState(false);
  // ⌘K / Ctrl+K opens the command palette from anywhere
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setMenu(false); setPalette(p => !p); } };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, []);
  const tabsRef = useRef<HTMLElement>(null);
  const [ink, setInk] = useState<{ x: number; w: number } | null>(null);

  // the active-tab pill slides between tabs
  useLayoutEffect(() => {
    const place = () => {
      const bar = tabsRef.current, el = bar?.querySelector<HTMLElement>(".tab.active");
      setInk(el ? { x: el.offsetLeft, w: el.offsetWidth } : null);
      // keep the active tab visible when the bar scrolls sideways (only this bar - never the page)
      if (bar && el && (el.offsetLeft < bar.scrollLeft || el.offsetLeft + el.offsetWidth > bar.scrollLeft + bar.clientWidth))
        bar.scrollTo({ left: el.offsetLeft - 16, behavior: "smooth" });
    };
    place(); window.addEventListener("resize", place);
    document.fonts?.ready.then(place);
    return () => window.removeEventListener("resize", place);
  }, [tab, tabs.length]);

  useEffect(() => {
    if (!menu) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenu(false); };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [menu]);
  const go = (t: TabId) => { setMenu(false); nav(t); };

  return (
    <header className={`app-header ${y > 8 || menu ? "scrolled" : ""}`}>
      <div className="header-inner">
        <button className="brand-logo" onClick={() => go("home")} aria-label="ClinieSync home">
          <Logo size={30} /><b>ClinieSync</b>
        </button>
        <nav className="tabs" ref={tabsRef} aria-label="Main">
          {ink && <span className="tab-ink" style={{ width: ink.w, transform: `translateX(${ink.x}px)` }} aria-hidden="true" />}
          {tabs.map(t => (
            <button key={t.id} className={`tab ${tab === t.id ? "active" : ""}`} onClick={() => go(t.id)}
              aria-current={tab === t.id ? "page" : undefined}>
              <t.icon size={16} /><span>{t.label}</span>
            </button>
          ))}
        </nav>
        <div className="header-right">
          <button className="search-btn" onClick={() => setPalette(true)} aria-label="Search and commands" title={`Search patients, pages or ask (${isMac ? "⌘" : "Ctrl+"}K)`}>
            <Search size={16} /><span className="search-label">Search</span><kbd>{isMac ? "⌘" : "Ctrl"} K</kbd></button>
          {health && (
            <div className="sys-pill" tabIndex={0} aria-label="System status">
              <span className={`dot ${llmOk ? "ok" : "warn"}`} /><Cpu size={14} />
              <span className="sys-label">{llmOk ? "LLM" : "Offline-safe"}</span>
              <div className="sys-pop">
                <div><b>LLM</b><span>{llmOk ? `${health.llm.model} (open-source)` : "Not running - deterministic, record-built answers"}</span></div>
                <div><b>Guardrails</b><span>NVIDIA NeMo · {health.guardrails.status}{health.guardrails.llm_self_check ? " + LLM self-check" : ""}</span></div>
                <div><b>Vector store</b><span>{health.vector_store.backend} · {health.vector_store.chunks ?? "-"} chunks</span></div>
                <div><b>Messaging</b><span>{health.delivery.mode === "sandbox" ? "Sandbox - nothing is delivered"
                  : `E-mail: ${health.delivery.channels.email === "live" ? "direct" : "not set up"} · WhatsApp: ${
                    health.delivery.channels.whatsapp === "live" ? "gateway" : "free link"}`}</span></div>
                <div><b>Data</b><span>Synthetic · {health.database.patients} patients · ref. date {health.reference_date}</span></div>
              </div>
            </div>
          )}
          <div className="user-pill">
            <span className={`user-avatar ${user.role}`} aria-hidden="true">{initials(user.display_name)}</span>
            <span className="user-text"><b>{user.display_name.replace(/\s*\(.*\)\s*$/, "")}</b><small>{ROLE_LABEL[user.role]}</small></span>
            <button className="btn ghost icon" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={16} /></button>
          </div>
          <button className="btn ghost icon menu-btn" onClick={() => setMenu(m => !m)} aria-expanded={menu} aria-controls="app-menu"
            aria-label={menu ? "Close menu" : "Open menu"}>{menu ? <X size={20} /> : <Menu size={20} />}</button>
        </div>
      </div>
      <div className="header-progress" aria-hidden="true"><span style={{ transform: `scaleX(${p})` }} /></div>

      {/* phones and small tablets: every section in one sheet */}
      {menu && <>
        <div className="menu-scrim" onClick={() => setMenu(false)} />
        <nav id="app-menu" className="menu-sheet" aria-label="Main">
          <button className="menu-search" onClick={() => { setMenu(false); setPalette(true); }}><Search size={17} />Search patients, pages or ask…</button>
          <div className="menu-grid">
            {tabs.map((t, i) => (
              <button key={t.id} className={`menu-item ${tab === t.id ? "active" : ""}`} onClick={() => go(t.id)}
                aria-current={tab === t.id ? "page" : undefined} style={{ "--d": `${i * 30}ms` } as React.CSSProperties}>
                <span className="menu-icon"><t.icon size={18} /></span>{t.label}</button>
            ))}
          </div>
          <div className="menu-foot">
            <span className={`user-avatar ${user.role}`} aria-hidden="true">{initials(user.display_name)}</span>
            <span className="user-text"><b>{user.display_name.replace(/\s*\(.*\)\s*$/, "")}</b><small>{ROLE_LABEL[user.role]}</small></span>
            <button className="btn sm" onClick={logout}><LogOut size={15} />Sign out</button>
          </div>
        </nav>
      </>}
      <CommandPalette open={palette} onClose={() => setPalette(false)} tabs={tabs} />
    </header>
  );
}
