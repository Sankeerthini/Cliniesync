"""Patient Journey: registry search, profile, longitudinal timeline, measurements, documents."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from backend.app.security import require_roles
from backend.app.services import patient_service as P
from backend.app.services.audit import audit
from common.settings import get_settings
from database.models import Document
from database.session import get_session
from guardrails.policy import ROLE_SCOPES

router = APIRouter(prefix="/api/patients", tags=["patients"])
clinical = require_roles("doctor", "coordinator")


@router.get("")
def search(q: str = "", status: str = "", facility_id: str = "", limit: int = 50,
           user: UserCtx = Depends(clinical), s: Session = Depends(get_session, scope="function")):
    return {"patients": P.list_patients(s, q, status, facility_id, min(limit, 200))}


@router.get("/{pid}")
def get_profile(pid: str, user: UserCtx = Depends(clinical), s: Session = Depends(get_session, scope="function")):
    out = P.profile(s, pid, ROLE_SCOPES[user.role], get_settings().reference_date)
    if not out:
        raise HTTPException(404, "patient not found")
    audit(s, user, "view_patient", target=pid, decision="allowed")
    return out


@router.get("/{pid}/timeline")
def get_timeline(pid: str, user: UserCtx = Depends(clinical), s: Session = Depends(get_session, scope="function")):
    return P.timeline(s, pid, ROLE_SCOPES[user.role], get_settings().reference_date)


@router.get("/{pid}/measurements")
def get_measurements(pid: str, user: UserCtx = Depends(require_roles("doctor")), s: Session = Depends(get_session, scope="function")):
    return {"series": P.measurements(s, pid),
            "note": "Values exactly as documented. ClinieSync does not mark values as normal/abnormal."}


@router.get("/{pid}/documents")
def get_documents(pid: str, user: UserCtx = Depends(require_roles("doctor")), s: Session = Depends(get_session, scope="function")):
    return {"documents": P.documents(s, pid)}


@router.get("/{pid}/documents/{doc_id}")
def get_document(pid: str, doc_id: str, user: UserCtx = Depends(require_roles("doctor")),
                 s: Session = Depends(get_session, scope="function")):
    d = s.get(Document, doc_id)
    if not d or d.patient_id != pid:
        raise HTTPException(404, "document not found")
    audit(s, user, "view_document", target=doc_id, decision="allowed")
    return {"doc_id": d.doc_id, "title": d.title, "doc_type": d.doc_type, "date": d.doc_date.isoformat(),
            "author": d.author, "source": d.source_system, "source_file": d.source_file, "text": d.text}


@router.get("/{pid}/fhir")
def get_fhir(pid: str, user: UserCtx = Depends(require_roles("doctor")), s: Session = Depends(get_session, scope="function")):
    """FHIR R4 Bundle for interoperability with OHC CARE / any FHIR server (see integrations/care_ohc)."""
    from integrations.care_ohc.fhir_export import patient_bundle

    try:
        bundle = patient_bundle(pid)
    except KeyError:
        raise HTTPException(404, "patient not found")
    audit(s, user, "fhir_export", target=pid, decision="allowed")
    return bundle
