from fastapi import Header, HTTPException, Request


async def get_db_session(r: Request):
    async with r.app.state.sessmaker() as sess, sess.begin():
        yield sess


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
