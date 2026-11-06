"""End-to-end API tests on synthetic data (requires `python -m data_generator.run` + `python -m etl.pipeline`)."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(client, username):
    r = client.post("/api/auth/login", json={"username": username, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def doc(client):
    return login(client, "dr.ananya")


@pytest.fixture(scope="module")
def coord(client):
    return login(client, "rekha.coord")


@pytest.fixture(scope="module")
def admin(client):
    return login(client, "admin.ops")


def a_patient(client, doc):
    pts = client.get("/api/patients?status=postnatal_closed", headers=doc).json()["patients"]
    return pts[0]["patient_id"]


def test_auth_required(client):
    assert client.get("/api/overview").status_code == 401
    assert client.post("/api/auth/login", json={"username": "dr.ananya", "password": "x"}).status_code == 401


def test_overview_per_role(client, doc, coord, admin):
    for h in (doc, coord, admin):
        r = client.get("/api/overview", headers=h)
        assert r.status_code == 200 and len(r.json()["tiles"]) == 4


def test_role_boundaries(client, doc, coord, admin):
    pid = a_patient(client, doc)
    assert client.get("/api/patients", headers=admin).status_code == 403            # admin: aggregates only
    assert client.get(f"/api/patients/{pid}/measurements", headers=coord).status_code == 403  # coordinator: no values
    prof = client.get(f"/api/patients/{pid}", headers=coord).json()
    assert "contact" in prof and "clinical_values" not in prof["scopes"]
    assert client.post("/api/reports/preview", headers=coord, json={"response_id": "x"}).status_code == 403


def test_doctor_summary_review_and_share(client, doc):
    pid = a_patient(client, doc)
    r = client.post("/api/query", headers=doc, json={"text": "Summarize the patient's pregnancy journey so far",
                                                     "patient_id": pid}).json()
    assert r["status"] == "pending_review" and r["intent"] == "patient_summary" and r["citations"]
    rid = r["response_id"]
    # cannot share before verification
    assert client.post("/api/reports/preview", headers=doc, json={"response_id": rid, "language": "kn"}).status_code == 409
    # an edit that introduces advice is rejected
    bad = client.post(f"/api/reviews/{rid}", headers=doc, json={"action": "edit", "edited_text": "I recommend starting iron."})
    assert bad.status_code == 422
    assert client.post(f"/api/reviews/{rid}", headers=doc, json={"action": "verify"}).json()["status"] == "verified"
    for lang in ("en", "hi", "bn", "kn"):
        p = client.post("/api/reports/preview", headers=doc, json={"response_id": rid, "language": lang})
        assert p.status_code == 200 and "<html" in p.json()["html"]
    assert client.post("/api/reports/share", headers=doc, json={"response_id": rid, "language": "hi",
                                                                "channels": ["sms"], "consent_confirmed": False}).status_code == 400
    sh = client.post("/api/reports/share", headers=doc, json={"response_id": rid, "language": "hi", "channels": ["sms", "whatsapp"],
                                                              "consent_confirmed": True}).json()
    assert sh["results"] and all(x["status"] in ("sent", "skipped") for x in sh["results"])


def test_parameter_retrieval_by_role(client, doc, coord):
    pid = a_patient(client, doc)
    q = {"text": "Show me the Haemoglobins reading or all Haemoglobin test results", "patient_id": pid}
    r = client.post("/api/query", headers=doc, json=q).json()
    assert r["status"] == "pending_review" and r["intent"] == "patient_retrieval", r.get("refusal")
    rows = r["table"]["rows"]
    assert rows and {x["parameter"] for x in rows} == {"Haemoglobin"} and r["citations"]
    assert any(x["source"].startswith("Lab report") for x in rows) and r["measurements"]["hemoglobin"]
    # coordinator: order / result status only, never the values (minimum-necessary access)
    c = client.post("/api/query", headers=coord, json=q).json()
    assert c["status"] == "pending_review" and "doctors only" in c["answer"]
    assert all("documented_result" not in x and "value" not in x for x in c.get("table", {}).get("rows", []))


def test_share_report_to_typed_contact(client, doc):
    pid = a_patient(client, doc)
    rid = client.post("/api/query", headers=doc, json={"text": "Show the patient's last 3 visits", "patient_id": pid}).json()["response_id"]
    client.post(f"/api/reviews/{rid}", headers=doc, json={"action": "verify"})
    base = {"response_id": rid, "language": "kn", "recipient": "other", "consent_confirmed": True,
            "base_url": "https://demo.example.org"}
    bad = client.post("/api/reports/share", headers=doc, json={**base, "channels": ["sms"], "to_phone": "12345"})
    assert bad.status_code == 422
    assert client.post("/api/reports/share", headers=doc, json={**base, "channels": ["email"],
                                                                "to_email": "not-an-email"}).status_code == 422
    r = client.post("/api/reports/share", headers=doc, json={**base, "channels": ["whatsapp", "sms", "email"],
                                                             "to_name": "Asha", "to_phone": "98450 12345",
                                                             "to_email": "asha@example.org"}).json()
    assert r["status"] == "shared" and {x["channel"] for x in r["results"] if x["status"] == "sent"} == {"whatsapp", "sms", "email"}
    assert r["device_links"]["whatsapp"].startswith("https://wa.me/919845012345?text=")
    assert r["device_links"]["sms"].startswith("sms:+919845012345") and "email" not in r["device_links"]
    assert r["report_url"].startswith("https://demo.example.org/r/")
    token = r["report_url"].rsplit("/", 1)[1]
    page = client.get(f"/r/{token}")
    assert page.status_code == 200 and "<html" in page.text and page.headers["x-robots-tag"].startswith("noindex")
    assert client.get("/r/not-a-real-token").status_code == 404
    # the full contact is not written to the audit trail
    entry = next(e for e in client.get("/api/trust/audit?action=share_report", headers=doc).json()["entries"]
                 if (e.get("detail") or {}).get("recipient") == "other")
    assert "9845012345" not in str(entry)


class _MailCatcher:
    """Minimal local SMTP server (no TLS / auth) that stores what it receives - exercises the real SMTP send path."""

    def __init__(self):
        import socket
        import threading

        self.messages = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            conn, _ = self.sock.accept()
            f = conn.makefile("rwb")
            say = lambda s: (f.write(s.encode() + b"\r\n"), f.flush())  # noqa: E731
            say("220 test")
            rcpt, data = [], None
            while (line := f.readline().decode().rstrip("\r\n")) is not None:
                cmd = line[:4].upper()
                if cmd in ("EHLO", "HELO"):
                    say("250 test")
                elif cmd == "MAIL":
                    say("250 ok")
                elif cmd == "RCPT":
                    rcpt.append(line.split(":", 1)[1].strip(" <>"))
                    say("250 ok")
                elif cmd == "DATA":
                    say("354 go")
                    buf = []
                    while (d := f.readline().decode()) not in (".\r\n", ""):
                        buf.append(d)
                    self.messages.append({"rcpt": rcpt, "data": "".join(buf)})
                    say("250 queued")
                elif cmd == "QUIT":
                    say("221 bye")
                    break
                else:
                    say("250 ok")
            conn.close()


def test_share_report_email_is_delivered_directly(client, doc, monkeypatch):
    import email

    from common.settings import get_settings

    catcher = _MailCatcher()
    for k, v in {"DELIVERY_MODE": "auto", "SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(catcher.port),
                 "SMTP_USER": "", "SMTP_FROM": "clinic@example.org"}.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    try:
        assert client.get("/api/health").json()["delivery"]["channels"] == {"sms": "device", "whatsapp": "device", "email": "live"}
        pid = a_patient(client, doc)
        rid = client.post("/api/query", headers=doc, json={"text": "Show the patient's last 3 visits", "patient_id": pid}).json()["response_id"]
        client.post(f"/api/reviews/{rid}", headers=doc, json={"action": "verify"})
        r = client.post("/api/reports/share", headers=doc, json={
            "response_id": rid, "language": "hi", "recipient": "other", "consent_confirmed": True, "channels": ["email", "whatsapp"],
            "to_email": "someone@example.org", "to_phone": "9845012345", "base_url": "https://demo.example.org"}).json()
        by = {x["channel"]: x for x in r["results"]}
        assert by["email"]["status"] == "sent" and not by["email"]["sandbox"], by["email"]
        assert by["whatsapp"]["status"] == "device" and r["device_links"]["whatsapp"].startswith("https://wa.me/919845012345")
        assert len(catcher.messages) == 1 and catcher.messages[0]["rcpt"] == ["someone@example.org"]
        msg = email.message_from_string(catcher.messages[0]["data"])
        assert msg["To"] == "someone@example.org" and "clinic@example.org" in msg["From"]
        names = [part.get_filename() for part in msg.walk() if part.get_filename()]
        assert names and names[0].startswith("ClinieSync_report_") and names[0].endswith(".html")
        html = next(part.get_payload(decode=True).decode() for part in msg.walk()
                    if part.get_content_type() == "text/html" and not part.get_filename())
        assert "https://demo.example.org/r/" in html and "<html" in html
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_blocked_query_is_logged(client, doc):
    r = client.post("/api/query", headers=doc, json={"text": "What dose of iron should she take?"}).json()
    assert r["status"] == "blocked" and r["refusal"]["category"] == "treatment_prescription"
    entries = client.get("/api/trust/audit?action=query", headers=doc).json()["entries"]
    assert any(e["decision"] == "blocked" for e in entries)


def test_reminder_workflow_requires_approval(client, coord):
    q = client.get("/api/followups", headers=coord).json()["followups"]
    ids = [f["followup_id"] for f in q if f["consent_sms"]][:2]
    drafts = client.post("/api/followups/drafts", headers=coord, json={"followup_ids": ids, "channel": "sms"}).json()["drafts"]
    mid = drafts[0]["message_id"]
    assert client.post(f"/api/outbox/{mid}", headers=coord, json={"action": "send"}).status_code == 409
    assert client.post(f"/api/outbox/{mid}", headers=coord, json={"action": "approve"}).json()["status"] == "approved"
    sent = client.post(f"/api/outbox/{mid}", headers=coord, json={"action": "send"}).json()
    assert sent["status"] == "sent" and "sandbox" in sent["delivery_detail"]
    # batch approve-and-send (the click is the approval)
    more = client.post("/api/followups/drafts", headers=coord, json={"followup_ids": ids, "channel": "sms"}).json()["drafts"]
    b = client.post("/api/outbox/approve-and-send", headers=coord, json={"message_ids": [m["message_id"] for m in more if m["status"] == "draft"]})
    assert b.status_code == 200 and all(m["status"] == "sent" for m in b.json()["messages"])
    c = client.post(f"/api/followups/{ids[0]}/contact", headers=coord, json={"outcome": "scheduled", "channel": "phone"})
    assert c.json()["workflow_state"] == "scheduled"
    assert client.post(f"/api/followups/{ids[0]}/override", headers=coord, json={"status": "completed", "reason": ""}).status_code == 422


def test_admin_analytics_and_kpi(client, admin):
    d = client.get("/api/analytics/dashboard", headers=admin).json()
    assert {"visit_volume", "anc_dropoff", "followup_completion"} <= set(d["metrics"])
    r = client.post("/api/query", headers=admin, json={"text": "How many maternal and child healthcare visits occurred this month?"}).json()
    assert r["intent"] == "population_analytics" and r["charts"]
    r = client.post("/api/query", headers=admin, json={"text": "Summarize CS-000010"}).json()
    assert r["status"] == "blocked" and r["intent"] == "access"
    k = client.get("/api/kpi", headers=admin).json()
    assert k["primary"]["baseline"]["n"] > 0 and k["primary"]["pilot"]["n"] > 0
    assert client.post("/api/kpi/timing", headers=admin, json={"task": "last 3 visits", "method": "manual",
                                                               "seconds": 95}).json()["ok"]


def test_playground(client, coord):
    r = client.post("/api/trust/playground", headers=coord, json={"text": "Which patients are high risk?"}).json()
    assert not r["allowed"] and r["category"] == "risk_scoring"


def test_read_only_sql_connection_does_not_poison_pool(client, doc):
    """LLM-generated SQL runs read-only; that must never make later writes fail."""
    from sqlalchemy import text

    from database.session import read_only_connection

    c = read_only_connection()
    with pytest.raises(Exception):
        c.execute(text("CREATE TABLE should_fail (a INT)"))
    c.close()
    r = client.post("/api/query", headers=doc, json={"text": "Drop off rate trends"})
    assert r.status_code == 200 and r.json()["status"] == "pending_review"
