// Doctor-only "Share Report": choose language (EN/HI/BN/KN), recipient (patient, caregiver or someone else by typed
// e-mail / mobile) and channels; preview; confirm consent; send.
//   E-mail   - delivered directly by the server (SMTP), report in the body + attached.
//   WhatsApp - free click-to-chat link (wa.me) with the message and report link filled in; SMS - the phone's SMS app.
// Every message carries an expiring report link.
import { useEffect, useRef, useState } from "react";
import { Copy, ExternalLink, Mail, MessageCircle, Send, Smartphone } from "lucide-react";
import { api } from "../../api/client";
import { useApp } from "../../app/context";
import { ErrorNote, LANG_LABEL, Modal, Seg } from "../../ui/components";

interface Preview {
  html: string; sms_text: string; whatsapp_text: string; translation_engine: string;
  patient: { patient_id: string; name: string; preferred_language: string };
  consent: Record<string, boolean>; recipients: { patient_phone: string; caregiver_phone: string; email: string | null };
}
interface ShareResult {
  results: { channel: string; to?: string; status: string; sandbox?: boolean; detail: string }[];
  report_url: string | null; link_expires_days: number | null; device_links: Record<string, string>;
}
type Lang = "en" | "hi" | "bn" | "kn";
type Recipient = "patient" | "caregiver" | "other";

const CH = [{ id: "email", label: "E-mail", icon: Mail }, { id: "whatsapp", label: "WhatsApp", icon: MessageCircle },
  { id: "sms", label: "SMS", icon: Smartphone }];
const PHONE_OK = (v: string) => { const d = v.replace(/\D/g, ""); return v.trim().startsWith("+") ? d.length >= 8 && d.length <= 15
  : /^0?[6-9]\d{9}$/.test(d) || /^91[6-9]\d{9}$/.test(d); };
const EMAIL_OK = (v: string) => /^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(v.trim());
const LOCAL = /^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/;

export function ShareReportModal({ responseId, open, onClose, defaultLang }: { responseId: string; open: boolean; onClose: () => void; defaultLang?: string }) {
  const { health } = useApp();
  const [lang, setLang] = useState<Lang>((defaultLang as Lang) || "en");
  const [recipient, setRecipient] = useState<Recipient>("patient");
  const [toName, setToName] = useState("");
  const [toPhone, setToPhone] = useState("");
  const [toEmail, setToEmail] = useState("");
  const [channels, setChannels] = useState<Set<string>>(new Set(["sms"]));
  const [consent, setConsent] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [view, setView] = useState<"report" | "sms" | "whatsapp">("report");
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<ShareResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (result) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [result]);

  useEffect(() => {
    if (!open) return;
    setErr(null); setPreview(null); setResult(null);
    api.post<Preview>("/api/reports/preview", { response_id: responseId, language: lang, recipient: recipient === "other" ? "patient" : recipient })
      .then(p => { setPreview(p); if (recipient !== "other") setChannels(new Set(["sms", "whatsapp", "email"].filter(c => p.consent[c]).slice(0, 2))); })
      .catch(e => setErr(e.message));
  }, [open, responseId, lang, recipient]);

  const other = recipient === "other";
  const phoneOk = PHONE_OK(toPhone), emailOk = EMAIL_OK(toEmail);
  const chState = health?.delivery.channels || {};
  const emailReady = chState.email !== "not_configured";
  const usable = (c: string) => (c !== "email" || emailReady) && (other ? (c === "email" ? emailOk : phoneOk) : !!preview?.consent[c]);
  const why = (c: string) => c === "email" && !emailReady ? "e-mail server not set up"
    : other ? (c === "email" ? "enter an e-mail address" : "enter a mobile number") : "no consent on record";
  const how = (c: string) => chState[c] === "live" ? (c === "email" ? "sent directly" : "sent by gateway")
    : chState[c] === "device" ? (c === "whatsapp" ? "free · opens WhatsApp on this device" : "opens this device's SMS app")
    : chState[c] === "sandbox" ? "sandbox" : "";
  const chosen = [...channels].filter(usable);
  const toggle = (c: string) => setChannels(s => { const n = new Set(s); n.has(c) ? n.delete(c) : n.add(c); return n; });
  const pickRecipient = (r: Recipient) => { setRecipient(r); setResult(null); if (r === "other") setChannels(new Set(["email"])); };
  const origin = window.location.origin;

  const send = async () => {
    setBusy(true); setErr(null); setResult(null);
    try {
      setResult(await api.post<ShareResult>("/api/reports/share", {
        response_id: responseId, language: lang, recipient, channels: chosen, consent_confirmed: consent, base_url: origin,
        ...(other ? { to_name: toName || null, to_phone: toPhone || null, to_email: toEmail || null } : {}) }));
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const copy = async (t: string) => { try { await navigator.clipboard.writeText(t); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ } };

  return (
    <Modal open={open} onClose={onClose} title="Share report" wide>
      <div className="share-grid">
        <div className="col">
          <label className="field">Language
            <Seg<Lang> value={lang} onChange={setLang} ariaLabel="Report language"
              options={(["en", "hi", "bn", "kn"] as Lang[]).map(l => ({ value: l, label: <span lang={l}>{LANG_LABEL[l]}</span> }))} /></label>
          {preview && <p className="tiny muted">Patient's preferred language: <b>{LANG_LABEL[preview.patient.preferred_language]}</b></p>}
          <label className="field">Send to
            <Seg<Recipient> value={recipient} onChange={pickRecipient} ariaLabel="Recipient"
              options={[{ value: "patient", label: "Patient" }, { value: "caregiver", label: "Caregiver" }, { value: "other", label: "Someone else" }]} /></label>

          {other ? (
            <div className="col" style={{ gap: 8 }}>
              <input className="input" placeholder="Name (optional)" value={toName} maxLength={80} onChange={e => setToName(e.target.value)} aria-label="Recipient name" />
              <input className="input" type="email" inputMode="email" placeholder="E-mail address (report is delivered here)" value={toEmail} maxLength={120}
                onChange={e => setToEmail(e.target.value)} aria-label="E-mail address" aria-invalid={!!toEmail && !emailOk} />
              {toEmail && !emailOk && <span className="tiny" style={{ color: "var(--bad-ink)" }}>Check the e-mail address</span>}
              <input className="input" type="tel" inputMode="tel" placeholder="Mobile for WhatsApp / SMS (optional), e.g. 98450 12345" value={toPhone} maxLength={24}
                onChange={e => setToPhone(e.target.value)} aria-label="Mobile number" aria-invalid={!!toPhone && !phoneOk} />
              {toPhone && !phoneOk && <span className="tiny" style={{ color: "var(--bad-ink)" }}>10-digit Indian mobile, or + country code</span>}
            </div>
          ) : preview && (
            <p className="tiny muted">On record: {recipient === "caregiver" ? preview.recipients.caregiver_phone : preview.recipients.patient_phone}
              {preview.recipients.email ? ` · ${preview.recipients.email}` : ""} (synthetic)</p>
          )}

          <div className="field"><span>Channels</span>
            <div className="col" style={{ gap: 6 }}>
              {CH.map(c => {
                const ok = usable(c.id);
                return (
                  <label key={c.id} className={`check-row ${ok ? "" : "disabled"}`} title={ok ? "" : why(c.id)}>
                    <input type="checkbox" disabled={!ok} checked={channels.has(c.id) && ok} onChange={() => toggle(c.id)} />
                    <c.icon size={16} />{c.label}{ok ? how(c.id) && <span className="tiny muted">{how(c.id)}</span>
                      : <span className="badge neutral">{why(c.id)}</span>}
                  </label>);
              })}
            </div></div>
          <label className="check-row consent">
            <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
            <span>{other ? "I confirm the patient agreed to share this summary with this person on the selected channels, and I have verified its content."
              : "I confirm the patient consented to receive this summary on the selected channels, and I have verified its content."}</span>
          </label>
          <button className="btn primary" disabled={!consent || !chosen.length || busy || !preview} onClick={send}>
            <Send size={16} />{busy ? "Sending…" : "Share report"}</button>
          <ErrorNote error={err} />
          {result && (
            <div ref={resultRef} className={`callout ${result.results.some(r => (r.status === "sent" && !r.sandbox) || r.status === "device") ? "ok" : "warn"}`}
              style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
              {result.results.map(r => <div key={r.channel}><b>{r.channel === "email" ? "E-MAIL" : r.channel.toUpperCase()}</b>{r.to ? ` → ${r.to}` : ""} - {
                r.sandbox ? "not delivered (sandbox mode)" : r.status === "sent" ? (r.channel === "email" ? "sent ✓" : "sent by gateway ✓")
                  : r.status === "device" ? "ready - tap the button below" : r.status === "skipped" ? "skipped" : "not sent"}
                {r.status !== "sent" && r.status !== "device" && <div className="tiny">{r.detail}</div>}</div>)}
              {Object.keys(result.device_links).length > 0 && (<div>
                <div className="small"><b>Send from this device (free)</b> <span className="tiny muted">opens the app with the message filled in - press send there</span></div>
                <div className="row" style={{ gap: 6, marginTop: 6 }}>
                  {result.device_links.whatsapp && <a className="btn sm" href={result.device_links.whatsapp} target="_blank" rel="noopener noreferrer"><MessageCircle size={14} />Open WhatsApp</a>}
                  {result.device_links.sms && <a className="btn sm" href={result.device_links.sms}><Smartphone size={14} />Open SMS app</a>}
                </div></div>)}
              {result.report_url && (<div>
                <div className="small"><b>Report link</b> <span className="tiny muted">valid {result.link_expires_days} days · included in the message</span></div>
                <div className="row" style={{ gap: 6, marginTop: 6 }}>
                  <button className="btn sm" onClick={() => copy(result.report_url!)}><Copy size={14} />{copied ? "Copied" : "Copy link"}</button>
                  <a className="btn sm" href={result.report_url} target="_blank" rel="noopener noreferrer"><ExternalLink size={14} />Open</a>
                </div></div>)}
            </div>)}
          <p className="tiny muted">
            {chState.email === "live" ? <>E-mails are sent directly from <b>{health?.delivery.email_from}</b>. </>
              : chState.email === "not_configured" ? <>E-mail is not set up yet: run <span className="mono">.venv/bin/python scripts/setup_email.py</span> (free with a Gmail app password) and restart the server. </>
              : <>Delivery is in <b>sandbox</b> mode (nothing leaves the server). </>}
            {LOCAL.test(window.location.hostname) && <>The report link uses <span className="mono">{origin}</span>; open the portal through its public (tunnel) address so recipients can open it.</>}
          </p>
          {preview && preview.translation_engine !== "none" && (
            <p className="tiny muted">Doctor's note translation: {preview.translation_engine === "unavailable"
              ? "kept in English (no translation engine running)" : `${preview.translation_engine} - labelled as machine translation`}.
              Structure &amp; labels use reviewed templates.</p>)}
        </div>
        <div className="col">
          <Seg value={view} onChange={v => setView(v as typeof view)} options={[{ value: "report", label: "Report (e-mail / print)" },
            { value: "whatsapp", label: "WhatsApp" }, { value: "sms", label: "SMS" }]} />
          {!preview ? <div className="empty"><span className="spin" /></div> : view === "report"
            ? <iframe title="Report preview" className="report-frame" srcDoc={preview.html} sandbox="" />
            : <pre className="msg-preview" lang={lang}>{view === "sms" ? preview.sms_text : preview.whatsapp_text}</pre>}
        </div>
      </div>
    </Modal>
  );
}
