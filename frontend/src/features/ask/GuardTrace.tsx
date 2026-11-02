// Transparency: shows every safety layer the request passed through (input -> access -> router -> output -> human).
import { useState } from "react";
import { CheckCircle2, ChevronDown, CircleDashed, ShieldAlert, ShieldCheck, UserCheck } from "lucide-react";
import type { QueryResponse } from "../../api/client";

function verdictBadge(v: string) {
  const cls = v === "pass" || v === "route" ? "ok" : v === "block" || v === "fail" ? "bad" : v === "skipped" ? "neutral" : "warn";
  return <span className={`badge ${cls}`}>{v}</span>;
}

export function GuardTrace({ res, defaultOpen = false }: { res: QueryResponse; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const t = res.guard_trace;
  const inBlocked = t.input.some(l => l.verdict === "block" || l.verdict === "decline");
  const accBlocked = t.access?.verdict === "block";
  const outFail = t.output.some(c => c.verdict === "fail");
  const steps = [
    { label: "Input guard", state: inBlocked ? "bad" : "ok", n: t.input.filter(l => l.layer?.startsWith("L")).length },
    { label: "Access", state: inBlocked ? "idle" : accBlocked ? "bad" : t.access ? "ok" : "idle" },
    { label: res.route && res.route !== "blocked" ? `Router · ${res.route}` : "Router", state: inBlocked || accBlocked ? "idle" : "ok" },
    { label: "Output guard", state: t.output.length ? (outFail ? "warn" : "ok") : "idle" },
    { label: "Human review", state: res.status === "pending_review" ? "pending" : "idle" },
  ];
  return (
    <div className="trace">
      <button className="trace-bar" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        {steps.map((s, i) => (
          <span key={s.label} className={`step ${s.state}`}>
            {s.state === "ok" ? <CheckCircle2 size={14} /> : s.state === "bad" ? <ShieldAlert size={14} /> :
              s.state === "pending" ? <UserCheck size={14} /> : <CircleDashed size={14} />}
            {s.label}{i < steps.length - 1 && <i className="arrow" />}
          </span>
        ))}
        <span className="spacer" /><span className="small muted">{open ? "Hide" : "Safety checks"}</span>
        <ChevronDown size={15} style={{ transform: open ? "rotate(180deg)" : undefined, transition: "transform .2s" }} />
      </button>
      {open && (
        <div className="trace-body fade-in">
          <div className="trace-col">
            <h4><ShieldCheck size={14} /> Input guard</h4>
            {t.input.map((l, i) => <div key={i} className="trace-row">{verdictBadge(l.verdict)}<b>{l.layer}</b><span className="muted">{l.detail}</span></div>)}
          </div>
          {t.access && <div className="trace-col"><h4>Access control</h4>
            <div className="trace-row">{verdictBadge(t.access.verdict)}<span className="muted">{t.access.detail}</span></div></div>}
          {t.output.length > 0 && <div className="trace-col"><h4>Output guard</h4>
            {t.output.map((c, i) => <div key={i} className="trace-row">{verdictBadge(c.verdict)}<b>{c.check}</b><span className="muted">{c.detail}</span></div>)}</div>}
        </div>
      )}
    </div>
  );
}
