// Command palette (⌘K / Ctrl+K): jump to any page, open a patient, or ask ClinieSync - without leaving the keyboard.
// Patient search only appears for roles that may open patient journeys (minimum-necessary access, same as the API).
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ArrowRight, CornerDownLeft, LogOut, MessageSquareText, Search, Sparkles, UserRound } from "lucide-react";
import { api } from "../api/client";
import { LANG_LABEL } from "../ui/components";
import { TabId, useApp } from "./context";

interface Hit { patient_id: string; name: string; age: number; village: string; language: string; status: string }
interface Item { id: string; group: string; icon: JSX.Element; label: string; hint?: string; run: () => void }

export const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

type Tab = { id: TabId; label: string; icon: typeof Search };

export function CommandPalette({ open, onClose, tabs }: { open: boolean; onClose: () => void; tabs: Tab[] }) {
  const { nav, setPatientId, logout } = useApp();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [at, setAt] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const canPatients = tabs.some(t => t.id === "journey");

  useEffect(() => { if (open) { setQ(""); setHits([]); setAt(0); setTimeout(() => input.current?.focus(), 0); } }, [open]);
  useEffect(() => {   // debounced patient search
    if (!open || !canPatients || q.trim().length < 2) { setHits([]); return; }
    const id = setTimeout(() => api.get<{ patients: Hit[] }>(`/api/patients?q=${encodeURIComponent(q.trim())}&limit=5`)
      .then(r => setHits(r.patients)).catch(() => setHits([])), 180);
    return () => clearTimeout(id);
  }, [q, open, canPatients]);

  const go = (t: TabId, opts?: { patientId?: string; askText?: string }) => { onClose(); nav(t, opts); };
  const items = useMemo<Item[]>(() => {
    const s = q.trim(), low = s.toLowerCase(), out: Item[] = [];
    if (s) out.push({ id: "ask", group: "Ask", icon: <Sparkles size={17} />, label: `Ask ClinieSync “${s}”`, hint: "Runs through the safety pipeline", run: () => go("ask", { askText: s }) });
    hits.forEach(p => out.push({ id: `p-${p.patient_id}`, group: "Patients", icon: <UserRound size={17} />, label: p.name,
      hint: `${p.patient_id} · ${p.age} y · ${LANG_LABEL[p.language] || p.language} · ${p.village}`, run: () => { setPatientId(p.patient_id); go("journey"); } }));
    tabs.filter(t => !low || t.label.toLowerCase().includes(low)).forEach(t => out.push({ id: `t-${t.id}`, group: "Go to", icon: <t.icon size={17} />, label: t.label, run: () => go(t.id) }));
    if (!s) out.push({ id: "ask-open", group: "Ask", icon: <MessageSquareText size={17} />, label: "Open Ask ClinieSync", run: () => go("ask") });
    if (!low || "sign out".includes(low) || "log out".includes(low)) out.push({ id: "out", group: "Account", icon: <LogOut size={17} />, label: "Sign out", run: () => { onClose(); logout(); } });
    return out;
  }, [q, hits, tabs.length]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setAt(0); }, [q, hits]);
  useEffect(() => { list.current?.querySelector<HTMLElement>(`[data-i="${at}"]`)?.scrollIntoView({ block: "nearest" }); }, [at]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setAt(i => Math.min(items.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setAt(i => Math.max(0, i - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); items[at]?.run(); }
    else if (e.key === "Escape") { e.preventDefault(); onClose(); }
  };
  if (!open) return null;

  let last = "";
  return createPortal(
    <div className="overlay palette-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Search and commands">
      <div className="palette" onClick={e => e.stopPropagation()} onKeyDown={onKey}>
        <div className="palette-input">
          <Search size={19} aria-hidden="true" />
          <input ref={input} value={q} onChange={e => setQ(e.target.value)} role="combobox" aria-expanded="true" aria-controls="palette-list"
            aria-activedescendant={items[at] ? `pi-${items[at].id}` : undefined}
            placeholder={canPatients ? "Search patients, pages - or ask a question…" : "Jump to a page - or ask a question…"} />
          <kbd>esc</kbd>
        </div>
        <div className="palette-list" id="palette-list" role="listbox" ref={list}>
          {items.map((it, i) => {
            const head = it.group !== last ? (last = it.group) : null;
            return (
              <div key={it.id}>
                {head && <div className="palette-group">{head}</div>}
                <button id={`pi-${it.id}`} data-i={i} role="option" aria-selected={i === at} className={`palette-item ${i === at ? "on" : ""}`}
                  onMouseMove={() => at !== i && setAt(i)} onClick={it.run}>
                  <span className="pi-icon">{it.icon}</span>
                  <span className="pi-text"><b>{it.label}</b>{it.hint && <small>{it.hint}</small>}</span>
                  {i === at ? <CornerDownLeft size={15} className="pi-go" /> : <ArrowRight size={15} className="pi-go dim" />}
                </button>
              </div>);
          })}
          {!items.length && <div className="palette-empty">No matches. Press <kbd>esc</kbd> to close.</div>}
        </div>
        <div className="palette-foot"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>↵</kbd> open</span><span><kbd>{isMac ? "⌘" : "Ctrl"}</kbd><kbd>K</kbd> toggle</span></div>
      </div>
    </div>, document.body);
}
