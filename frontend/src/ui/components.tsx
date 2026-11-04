// Shared UI primitives for ClinieSync.
import { ReactNode, useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ArrowUp, X } from "lucide-react";

/* ---------------------------------------------------------------- glass card */
// A calm surface: soft light follows the pointer and the card lifts on hover. (It used to tilt in 3D; on data-heavy
// screens that read as wobble, so `tilt` is kept only for call-site compatibility.)
export function Card3D({ children, className = "", style, onClick }:
  { children: ReactNode; className?: string; tilt?: number; style?: React.CSSProperties; onClick?: () => void }) {
  const move = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType === "touch") return;
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`); e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
  };
  return <div className={`card-3d ${className}`} style={style} onPointerMove={move} onClick={onClick}>{children}</div>;
}

/* ---------------------------------------------------------------- markdown (tiny, safe: no HTML injection) */
function inline(text: string, onCite?: (id: string) => void): ReactNode[] {
  const parts: ReactNode[] = [];
  const rx = /(\*\*[^*]+\*\*|\[S\d+\])/g;
  let last = 0; let m: RegExpExecArray | null; let k = 0;
  while ((m = rx.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) parts.push(<strong key={k++}>{tok.slice(2, -2)}</strong>);
    else {
      const id = tok.slice(1, -1);
      parts.push(<button key={k++} className="cite" onClick={() => onCite?.(id)} title={`Open source ${id}`}>{id}</button>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function Markdown({ text, onCite }: { text: string; onCite?: (id: string) => void }) {
  const lines = text.split("\n");
  const out: ReactNode[] = []; let list: ReactNode[] = [];
  const flush = () => { if (list.length) { out.push(<ul key={`u${out.length}`}>{list}</ul>); list = []; } };
  lines.forEach((ln, i) => {
    const t = ln.trimEnd();
    if (/^\s*[-•]\s+/.test(t)) list.push(<li key={i}>{inline(t.replace(/^\s*[-•]\s+/, ""), onCite)}</li>);
    else { flush(); if (t.trim()) out.push(<p key={i}>{inline(t, onCite)}</p>); }
  });
  flush();
  return <div className="md">{out}</div>;
}

/* ---------------------------------------------------------------- data table */
export function DataTable({ columns, rows, max = 200, onRowClick, selectable, selected, onToggle, rowKey }: {
  columns: { key: string; label: string; render?: (row: any) => ReactNode }[]; rows: any[]; max?: number;
  onRowClick?: (row: any) => void; selectable?: boolean; selected?: Set<string>; onToggle?: (id: string) => void;
  rowKey?: string;
}) {
  if (!rows.length) return <EmptyState title="Nothing to show" text="No rows match the current view." />;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr>
          {selectable && <th style={{ width: 32 }} />}
          {columns.map(c => <th key={c.key}>{c.label}</th>)}
        </tr></thead>
        <tbody>
          {rows.slice(0, max).map((r, i) => {
            const id = rowKey ? String(r[rowKey]) : String(i);
            const sel = selected?.has(id);
            return (
              <tr key={id} className={sel ? "selected" : ""} onClick={() => onRowClick?.(r)}
                style={{ cursor: onRowClick ? "pointer" : undefined }}>
                {selectable && <td><input type="checkbox" aria-label="select row" checked={!!sel}
                  onChange={() => onToggle?.(id)} onClick={e => e.stopPropagation()} /></td>}
                {columns.map(c => <td key={c.key}>{c.render ? c.render(r) : fmtCell(r[c.key])}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function fmtCell(v: unknown): ReactNode {
  if (v === null || v === undefined || v === "") return <span className="muted">-</span>;
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

/* ---------------------------------------------------------------- modal & drawer */
export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  // Portal to <body> so modals are never trapped under sticky/animated stacking contexts.
  return createPortal(
    <div className="overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className={`modal ${wide ? "wide" : ""}`} onClick={e => e.stopPropagation()}>
        <div className="modal-head"><h2>{title}</h2><span className="spacer" />
          <button className="btn ghost icon" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
        <div className="modal-body">{children}</div>
      </div>
    </div>, document.body);
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return createPortal(
    <div className="overlay right" onClick={onClose} role="dialog" aria-modal="true">
      <aside className="drawer" onClick={e => e.stopPropagation()}>
        <div className="modal-head"><h3>{title}</h3><span className="spacer" />
          <button className="btn ghost icon" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
        <div className="modal-body">{children}</div>
      </aside>
    </div>, document.body);
}

/* ---------------------------------------------------------------- stat tile */
// Same tile as the home page: icon, a number that counts up, label, optional hint.
export function StatTile({ label, value, unit, hint, icon, tone = "brand" }:
  { label: string; value: ReactNode; unit?: string; hint?: ReactNode; icon?: ReactNode; tone?: "brand" | "blue" | "violet" | "coral" }) {
  const counted = useCountUp(typeof value === "number" ? value : null);
  const shown = typeof value === "number" ? counted : value;
  return (
    <div className="tile stat">
      {icon && <span className="tile-top"><span className={`tile-icon tone-${tone}`}>{icon}</span></span>}
      <span className="tile-value num">{shown ?? "-"}{unit && value !== null && value !== undefined && value !== "-" && <small>{unit}</small>}</span>
      <span className="tile-label">{label}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

/* ---------------------------------------------------------------- empty state */
export function EmptyState({ icon, title, text, action }: { icon?: ReactNode; title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty-state">
      {icon && <span className="empty-icon">{icon}</span>}
      <b>{title}</b>{text && <p>{text}</p>}{action}
    </div>
  );
}

/* ---------------------------------------------------------------- segmented control */
export function Seg<T extends string>({ value, options, onChange, ariaLabel }:
  { value: T; options: { value: T; label: ReactNode }[]; onChange: (v: T) => void; ariaLabel?: string }) {
  return (
    <div className="seg" role="group" aria-label={ariaLabel}>
      {options.map(o => <button key={o.value} aria-pressed={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>)}
    </div>
  );
}

/* ---------------------------------------------------------------- async hook */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const run = useCallback(() => {
    setLoading(true); setError(null);
    fn().then(d => { setData(d); setLoading(false); }).catch(e => { setError(e.message || String(e)); setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { data, error, loading, reload: run, setData };
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="loading-state" role="status"><span className="spin" /><span>{label}…</span></div>;
}

export function ErrorNote({ error }: { error: string | null }) {
  return error ? <div className="callout bad">{error}</div> : null;
}

export const LANG_LABEL: Record<string, string> = { en: "English", hi: "हिन्दी", bn: "বাংলা", kn: "ಕನ್ನಡ" };

export function fmtDate(iso?: string | null) {
  if (!iso) return "-";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

/* ---------------------------------------------------------------- page chrome shared by sign-in and the app */
// living background: slow aurora blobs over a faint dot grid
export function Aurora() {
  return <div className="aurora" aria-hidden="true"><i className="b1" /><i className="b2" /><i className="b3" /><i className="grid-dots" /></div>;
}

export const prefersReducedMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// whole-page scroll position: p = 0..1, y = px, max = scrollable px.
// Also re-measures when the page grows or shrinks (data loading in, tabs switching), not only on scroll.
export function usePageScroll() {
  const [s, setS] = useState({ p: 0, y: 0, max: 0 });
  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0; const max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight), y = window.scrollY;
      setS(o => (o.y === y && o.max === max ? o : { p: max > 0 ? Math.min(1, y / max) : 0, y, max }));
    };
    const on = () => { if (!raf) raf = requestAnimationFrame(update); };
    const ro = new ResizeObserver(on); ro.observe(document.getElementById("root") || document.body);
    update(); window.addEventListener("scroll", on, { passive: true }); window.addEventListener("resize", on);
    return () => { ro.disconnect(); window.removeEventListener("scroll", on); window.removeEventListener("resize", on); if (raf) cancelAnimationFrame(raf); };
  }, []);
  return s;
}

// back to top, with a ring that fills as you scroll
// appears once you are a little way down any page long enough to need it
export function BackToTop() {
  const { p, y, max } = usePageScroll();
  const RING = 2 * Math.PI * 23;
  const show = max > 240 && y > Math.min(320, max * 0.4);
  return (
    <button className={`to-top ${show ? "show" : ""}`} aria-label="Back to top" tabIndex={show ? 0 : -1} aria-hidden={!show}
      onClick={() => window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" })}>
      <svg className="ring-svg" viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="26" r="23" />
        <circle className="ring" cx="26" cy="26" r="23" strokeDasharray={RING} strokeDashoffset={RING * (1 - p)} /></svg>
      <ArrowUp size={19} />
    </button>
  );
}

// animates a number from 0 to `to` once it is known (keeps the decimals of the target)
export function useCountUp(to: number | null | undefined, ms = 900) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (to == null) return;
    if (prefersReducedMotion()) { setV(to); return; }
    let raf = 0; const t0 = performance.now();
    const tick = (now: number) => { const k = Math.min(1, (now - t0) / ms); setV(to * (1 - Math.pow(1 - k, 3))); if (k < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
  }, [to, ms]);
  if (to == null) return null;
  const dp = Number.isInteger(to) ? 0 : 1;
  return v.toLocaleString("en-IN", { minimumFractionDigits: dp, maximumFractionDigits: dp });
}
