// Human verification queue: every AI answer you received, with verify / edit / reject and (doctors) Share Report.
import { useState } from "react";
import { ClipboardCheck } from "lucide-react";
import { api, QueryResponse } from "../../api/client";
import { useApp } from "../../app/context";
import { AnswerCard } from "../ask/AnswerCard";
import { fmtDate, Loading, Seg, useAsync } from "../../ui/components";

interface Row { response_id: string; created_at: string; query: string; intent: string; route: string; patient_id: string | null; status: string; llm_used: boolean; answer: string }

export function ReviewsPage() {
  const { nav } = useApp();
  const [status, setStatus] = useState("pending_review");
  const [open, setOpen] = useState<QueryResponse | null>(null);
  const list = useAsync(() => api.get<{ responses: Row[] }>(`/api/reviews?status=${status}`), [status]);
  const load = async (id: string) => {
    const r = await api.get<{ payload: QueryResponse; status: string; answer: string }>(`/api/reviews/${id}`);
    setOpen({ ...r.payload, status: r.status === "pending_review" ? "pending_review" : r.payload.status, answer: r.answer } as QueryResponse);
  };
  return (
    <div className="page">
      <div className="page-head"><div><div className="eyebrow">Human in control</div><h2>Review queue</h2>
        <p>Answers stay “pending review” until you verify, edit or reject them. Only verified patient summaries can be shared as reports.</p></div></div>
      <div className="reviews-grid">
        <div className="card">
          <Seg value={status} onChange={v => { setStatus(v); setOpen(null); }} options={[{ value: "pending_review", label: "Pending" },
            { value: "verified,edited", label: "Verified" }, { value: "rejected", label: "Rejected" }, { value: "all", label: "All" }]} />
          {list.loading ? <Loading /> : !list.data?.responses.length ? (
            <div className="empty"><ClipboardCheck size={28} /><p>Nothing here.</p><button className="btn sm" onClick={() => nav("ask")}>Ask a question</button></div>) : (
            <ul className="review-list">{list.data.responses.map(r => (
              <li key={r.response_id}><button className={open?.response_id === r.response_id ? "active" : ""} onClick={() => load(r.response_id)}>
                <span className="rq">{r.query}</span>
                <span className="row" style={{ gap: 6 }}><span className="badge neutral">{r.intent.replace(/_/g, " ")}</span>
                  {r.patient_id && <span className="tiny muted">{r.patient_id}</span>}<span className="spacer" />
                  <span className="tiny muted">{fmtDate(r.created_at.slice(0, 10))} {r.created_at.slice(11, 16)}</span></span>
              </button></li>))}</ul>)}
        </div>
        <div>{open ? <AnswerCard key={open.response_id + open.status} res={open} onAsk={(q) => nav("ask", { askText: q })} />
          : <div className="card empty">Select an answer to review it.</div>}</div>
      </div>
    </div>
  );
}
