from fastapi import Request
from redis.asyncio import Redis


async def get_redis(r: Request) -> Redis:
    return r.app.state.rds
