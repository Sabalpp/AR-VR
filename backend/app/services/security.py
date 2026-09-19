import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Device, User

bearer = HTTPBearer()


def password_hash(value):
    salt = secrets.token_hex(16)
    return salt + ":" + hashlib.scrypt(value.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()


def password_verify(value, hashed):
    salt, expected = hashed.split(":")
    return hmac.compare_digest(
        hashlib.scrypt(value.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex(),
        expected,
    )


def token(subject, kind, session_id=None):
    return jwt.encode(
        {
            "sub": subject,
            "kind": kind,
            "session_id": session_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=8 if kind == "user" else 4),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def authenticate(raw, db):
    try:
        claims = jwt.decode(raw, settings.jwt_secret, algorithms=["HS256"])
        entity = db.get(User if claims["kind"] == "user" else Device, claims["sub"])
        if not entity or (
            isinstance(entity, Device)
            and (not entity.paired or entity.session_id != claims["session_id"])
        ):
            raise ValueError()
        return entity
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token")


def principal(auth: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    return authenticate(auth.credentials, db)


def user(entity=Depends(principal)):
    if not isinstance(entity, User):
        raise HTTPException(403, "User authentication required")
    return entity
