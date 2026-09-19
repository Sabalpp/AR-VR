from fastapi import HTTPException
from sqlalchemy import select

from app.models import Access, Assignment, Device, Patient, Session


def patient_access(db, user, patient_id):
    p = db.get(Patient, patient_id)
    allowed = p and (
        p.user_id == user.id
        or (
            user.role == "therapist"
            and db.scalar(
                select(Access).where(
                    Access.therapist_id == user.id, Access.patient_id == patient_id
                )
            )
        )
    )
    if not allowed:
        raise HTTPException(404, "Patient not found")
    return p


def session_access(db, principal, session_id, lock=False):
    q = select(Session).where(Session.id == session_id)
    if lock:
        q = q.with_for_update()
    s = db.scalar(q)
    if not s:
        raise HTTPException(404, "Session not found")
    if isinstance(principal, Device):
        if principal.session_id != s.id:
            raise HTTPException(403, "Device is scoped to another session")
    else:
        patient_access(db, principal, db.get(Assignment, s.assignment_id).patient_id)
    return s
