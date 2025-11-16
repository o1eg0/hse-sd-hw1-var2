from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from aioredis import from_url as redis_from_url
from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.shared.model import RentInfo


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.DATABASE_URL, pool_size=30, max_overflow=30)
    sessmaker = async_sessionmaker(engine, expire_on_commit=False)

    app.state.sessmaker = sessmaker
    app.state.rds = await redis_from_url(settings.REDIS_URL, decode_responses=True)
    yield


app = FastAPI(
    title="rental-query",
    contact={"name": "sd-command-9"},
    lifespan=lifespan,
    version="0.1.0",
)


@app.get("/get_rent_info", response_model=RentInfo)
async def rental_info(oid: str):
    """
    - читаем RentalDB
    - если аренда активна: зовём pricing /v1/calc-accrued
    - если завершена: берём total_amount из БД
    """
    rental = db.get(RentalDB, rental_id)
    if not rental:
        raise HTTPException(404, "Rental not found")

    accrued_amount = rental.total_amount
    ended_at = rental.finish_time

    if rental.finish_time is None:
        # аренда ещё идёт — считаем через pricing
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://pricing:9000/v1/calc-accrued",
                json={
                    "price_per_hour": rental.price_per_hour,
                    "free_period_min": rental.free_period_min,
                    "started_at": rental.start_time.isoformat(),
                    "ended_at": datetime.utcnow().isoformat(),
                },
            )
        if resp.status_code != 200:
            raise HTTPException(502, "Pricing service unavailable")
        accrued_amount = resp.json()["accrued_amount"]

    return RentInfo(
        order_id=rental.id,
        status=rental.status.value,
        country=rental.country,
        currency=rental.currency,
        started_at=rental.start_time,
        ended_at=ended_at,
        accrued_amount=accrued_amount,
    )
