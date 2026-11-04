// Human verification queue: every AI answer you received, with verify / edit / reject and (doctors) Share Report.
import { useEffect, useState } from "react";
import { Check, ClipboardCheck, Pencil, X } from "lucide-react";
import { api, QueryResponse } from "../../api/client";
import { useApp } from "../../app/context";
import { AnswerCard } from "../ask/AnswerCard";
import { EmptyState, fmtDate, Loading, Seg, useAsync } from "../../ui/components";

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
  // open the first answer in the list on wide screens, so the queue never starts on an empty panel
  useEffect(() => {
    const first = list.data?.responses[0];
    if (first && !open && window.matchMedia("(min-width: 961px)").matches) load(first.response_id).catch(() => null);
  }, [list.data]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="page">
      <div className="page-head"><div><div className="eyebrow">Human in control</div><h2>Review queue</h2>
        <p>Answers stay “pending review” until you verify, edit or reject them. Only verified patient summaries can be shared as reports.</p></div></div>
      <div className="reviews-grid">
        <div className="card review-side">
          <Seg value={status} onChange={v => { setStatus(v); setOpen(null); }} options={[{ value: "pending_review", label: "Pending" },
            { value: "verified,edited", label: "Verified" }, { value: "rejected", label: "Rejected" }, { value: "all", label: "All" }]} />
          {list.loading ? <Loading /> : !list.data?.responses.length ? (
            <EmptyState icon={<ClipboardCheck size={26} />} title="All clear" text="No answers in this list."
              action={<button className="btn sm" onClick={() => nav("ask")}>Ask a question</button>} />) : (
            <ul className="review-list">{list.data.responses.map(r => (
              <li key={r.response_id}><button className={open?.response_id === r.response_id ? "active" : ""} onClick={() => load(r.response_id)}>
                <span className="rq"><i className={`rs s-${r.status}`} title={r.status.replace(/_/g, " ")} />{r.query}</span>
                <span className="row" style={{ gap: 6 }}><span className="badge neutral">{r.intent.replace(/_/g, " ")}</span>
                  {r.patient_id && <span className="tiny muted">{r.patient_id}</span>}<span className="spacer" />
                  <span className="tiny muted">{fmtDate(r.created_at.slice(0, 10))} {r.created_at.slice(11, 16)}</span></span>
              </button></li>))}</ul>)}
        </div>
        <div>{open ? <AnswerCard key={open.response_id + open.status} res={open} onAsk={(q) => nav("ask", { askText: q })} />
          : <div className="card"><EmptyState icon={<ClipboardCheck size={26} />} title="Pick an answer to review"
              text={<>Check it against the cited sources, then <span className="rv-steps"><span><Check size={13} />Verify</span><span><Pencil size={13} />Edit</span><span><X size={13} />Reject</span></span></>} /></div>}</div>
      </div>
    </div>
  );
}
