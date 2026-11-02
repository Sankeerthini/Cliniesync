import { useEffect, useRef, useState } from "react";
import { ArrowUp, Mic, MicOff, ShieldCheck, Sparkles, User as UserIcon, X } from "lucide-react";
import { api, QueryResponse } from "../../api/client";
import { useApp } from "../../app/context";
import { ErrorNote } from "../../ui/components";
import { AnswerCard } from "./AnswerCard";
import { useSpeech } from "./useSpeech";

interface Turn { id: number; q: string; mode: "text" | "voice"; res?: QueryResponse; error?: string; loading: boolean }

const PIPE = ["Text / voice", "Guardrails + access", "Query router", "SQL · RAG", "Grounded answer", "Human review"];

export function AskPage() {
  const { user, patientId, setPatientId, pendingAsk, clearPendingAsk, health } = useApp();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"text" | "voice">("text");
  const [examples, setExamples] = useState<{ examples: string[]; blocked_examples: string[] } | null>(null);
  const [stage, setStage] = useState(-1);
  const end = useRef<HTMLDivElement>(null);
  const speech = useSpeech((t, final) => { setText(t); setMode("voice"); if (final) setTimeout(() => ask(t, undefined, "voice"), 250); });

  useEffect(() => { api.get<typeof examples>("/api/query/examples").then(setExamples).catch(() => null); }, []);
  useEffect(() => { if (pendingAsk) { ask(pendingAsk); clearPendingAsk(); } /* eslint-disable-next-line */ }, [pendingAsk]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns]);

  async function ask(q: string, pid?: string, m: "text" | "voice" = mode) {
    const query = q.trim(); if (!query) return;
    const id = Date.now();
    setTurns(t => [...t, { id, q: query, mode: m, loading: true }]); setText(""); setMode("text");
    setStage(0); const timer = setInterval(() => setStage(s => Math.min(s + 1, PIPE.length - 2)), 220);
    try {
      const res = await api.post<QueryResponse>("/api/query", { text: query, patient_id: pid ?? patientId, input_mode: m });
      setTurns(t => t.map(x => x.id === id ? { ...x, res, loading: false } : x));
    } catch (e: any) {
      setTurns(t => t.map(x => x.id === id ? { ...x, error: e.message, loading: false } : x));
    } finally { clearInterval(timer); setStage(-1); }
  }

  return (
    <div className="page ask">
      <div className="ask-main">
        <div className="page-head">
          <div><div className="eyebrow">Ask instead of search</div><h2>Ask ClinieSync</h2>
            <p>Type or speak (English). Every request passes the safety pipeline; every answer cites its sources and waits for your verification.</p></div>
        </div>

        <div className="pipeline" aria-label="Request pipeline">
          {PIPE.map((p, i) => <span key={p} className={`pipe-step ${stage === i ? "active" : stage > i ? "done" : ""}`}>{p}</span>)}
        </div>

        <div className="thread">
          {turns.length === 0 && (
            <div className="welcome card fade-in">
              <Sparkles size={22} color="#0f7c80" />
              <div><h3>What would you like to know, {user.display_name}?</h3>
                <p className="small muted">Start with one of these, or ask your own question.</p></div>
            </div>)}
          {turns.map(t => (
            <div key={t.id} className="turn">
              <div className="bubble-q"><span>{t.mode === "voice" && <Mic size={13} />} {t.q}</span></div>
              {t.loading && <div className="answer loading"><span className="spin" /> Checking safety rules and retrieving records…</div>}
              {t.error && <ErrorNote error={t.error} />}
              {t.res && <AnswerCard res={t.res} onAsk={(q, pid) => ask(q, pid)} />}
            </div>))}
          <div ref={end} />
        </div>

        <div className="composer">
          {patientId && <span className="ctx-chip"><UserIcon size={13} />Patient in focus: <b>{patientId}</b>
            <button aria-label="Clear patient context" onClick={() => setPatientId(null)}><X size={13} /></button></span>}
          <form className="composer-box" onSubmit={e => { e.preventDefault(); ask(text); }}>
            <button type="button" className={`mic ${speech.listening ? "on" : ""}`} onClick={() => speech.listening ? speech.stop() : speech.start()}
              aria-label={speech.listening ? "Stop listening" : "Speak your question"} title={speech.browserSTT ? "Voice (browser, en-IN)" : health?.voice.server_stt ? "Voice (server Whisper)" : "Voice"}>
              {speech.listening ? <MicOff size={18} /> : <Mic size={18} />}</button>
            <input className="composer-input" value={text} onChange={e => { setText(e.target.value); setMode("text"); }}
              placeholder={speech.listening ? "Listening… speak now" : patientId ? "Ask about this patient…" : "Ask about patients, follow-ups or analytics…"} aria-label="Your question" />
            <button className="send" disabled={!text.trim()} aria-label="Send"><ArrowUp size={18} /></button>
          </form>
          <ErrorNote error={speech.error} />
        </div>
      </div>

      <aside className="ask-side">
        <div className="card">
          <h3>Try asking</h3>
          <div className="col" style={{ gap: 8, marginTop: 10 }}>
            {examples?.examples.map(e => <button key={e} className="chip-btn left" onClick={() => ask(e)}>{e}</button>)}
          </div>
        </div>
        <div className="card">
          <h3><ShieldCheck size={16} /> Blocked by design</h3>
          <p className="tiny muted" style={{ margin: "6px 0 10px" }}>See the guardrails refuse clinical decision-making:</p>
          <div className="col" style={{ gap: 8 }}>
            {examples?.blocked_examples.map(e => <button key={e} className="chip-btn left danger" onClick={() => ask(e)}>{e}</button>)}
          </div>
        </div>
      </aside>
    </div>
  );
}
