// Shared UI primitives for ClinieSync.
import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

/* ---------------------------------------------------------------- 3D tilt card */
export function Card3D({ children, className = "", tilt = 5, style, onClick }:
  { children: ReactNode; className?: string; tilt?: number; style?: React.CSSProperties; onClick?: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const move = (e: React.PointerEvent) => {
    const el = ref.current; if (!el || reduce || e.pointerType === "touch") return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
    el.style.setProperty("--ry", `${(px - .5) * tilt}deg`);
    el.style.setProperty("--rx", `${(.5 - py) * tilt}deg`);
    el.style.setProperty("--mx", `${px * 100}%`); el.style.setProperty("--my", `${py * 100}%`);
    el.classList.add("tilting");
  };
  const leave = () => {
    const el = ref.current; if (!el) return;
    el.style.setProperty("--rx", "0deg"); el.style.setProperty("--ry", "0deg"); el.classList.remove("tilting");
  };
  return <div ref={ref} className={`card-3d ${className}`} style={style} onPointerMove={move} onPointerLeave={leave}
    onClick={onClick}>{children}</div>;
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
  if (!rows.length) return <div className="empty">No rows</div>;
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
      <div className={`modal fade-in ${wide ? "wide" : ""}`} onClick={e => e.stopPropagation()}>
        <div className="modal-head"><h2>{title}</h2><span className="spacer" />
          <button className="btn ghost icon" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
        <div className="modal-body">{children}</div>
      </div>
    </div>, document.body);
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  if (!open) return null;
  return createPortal(
    <div className="overlay right" onClick={onClose}>
      <aside className="drawer fade-in" onClick={e => e.stopPropagation()}>
        <div className="modal-head"><h3>{title}</h3><span className="spacer" />
          <button className="btn ghost icon" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
        <div className="modal-body">{children}</div>
      </aside>
    </div>, document.body);
}

/* ---------------------------------------------------------------- stat tile */
export function StatTile({ label, value, unit, hint, icon, tone = "brand" }:
  { label: string; value: ReactNode; unit?: string; hint?: ReactNode; icon?: ReactNode; tone?: "brand" | "blue" | "violet" | "coral" }) {
  return (
    <Card3D className={`stat tone-${tone}`}>
      <div className="row" style={{ gap: 10 }}>
        {icon && <span className="stat-icon lift">{icon}</span>}
        <span className="stat-label">{label}</span>
      </div>
      <div className="stat-value">{value ?? "-"}{unit && value !== null && value !== undefined && <span className="stat-unit">{unit}</span>}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </Card3D>
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
  return <div className="empty"><span className="spin" /> <span style={{ marginLeft: 8 }}>{label}…</span></div>;
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
