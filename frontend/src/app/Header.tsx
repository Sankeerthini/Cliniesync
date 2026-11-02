import {
  BarChart3, BellRing, ClipboardCheck, Cpu, Database, Home, LogOut, MessageSquareText, Route, ShieldCheck, Target,
} from "lucide-react";
import type { Role } from "../api/client";
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

export function Header({ tab }: { tab: TabId }) {
  const { user, nav, health, logout } = useApp();
  const tabs = TABS.filter(t => t.roles.includes(user.role));
  const llmOk = health?.llm.available;
  return (
    <header className="app-header">
      <div className="header-inner">
        <button className="brand-logo" onClick={() => nav("home")} aria-label="ClinieSync home">
          <Logo /><span><b>ClinieSync</b><small>MCH Operations Copilot</small></span>
        </button>
        <nav className="tabs" aria-label="Main">
          {tabs.map(t => (
            <button key={t.id} className={`tab ${tab === t.id ? "active" : ""}`} onClick={() => nav(t.id)}
              aria-current={tab === t.id ? "page" : undefined}>
              <t.icon size={16} /><span>{t.label}</span>
            </button>
          ))}
        </nav>
        <div className="header-right">
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
            <span className={`role-dot ${user.role}`} />
            <span className="user-text"><b>{user.display_name}</b><small>{ROLE_LABEL[user.role]}</small></span>
            <button className="btn ghost icon" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={16} /></button>
          </div>
        </div>
      </div>
    </header>
  );
}
