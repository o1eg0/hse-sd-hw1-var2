from fastapi import Header, HTTPException
from sqlmodel import Session

from services.shared.db import get_session


def get_db_session() -> Session:
    return next(get_session())


def get_idempotency_key(
    key: str | None = Header(
        None,
        alias="Idempotency-Key",
        description="Required for idempotent rental start",
    ),
) -> str:
    if not key:
        raise HTTPException(400, "Idempotency-Key header is required")
    return key
