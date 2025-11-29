from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from httpx import AsyncClient
from sqlalchemy.exc import ProgrammingError
from sqlmodel.ext.asyncio.session import AsyncSession

from prometheus_fastapi_instrumentator import Instrumentator, metrics

from services.shared.db import create_async_sessionmaker
from services.shared.db_models import RentalDB
from services.shared.model import RentInfo
from services.shared.settings import rental_query_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_maker = await create_async_sessionmaker(rental_query_settings.database_url)
    app.state.sessmaker = session_maker
    yield


async def get_db_session(r: Request):
    async with r.app.state.sessmaker() as sess, sess.begin():
        yield sess


app = FastAPI(
    title="rental-query",
    contact={"name": "sd-command-9"},
    lifespan=lifespan,
    version="0.1.0",
)


instrumentator = Instrumentator().instrument(app).expose(app)
instrumentator.add(metrics.requests())
instrumentator.add(metrics.latency())


@app.get("/get_rent_info", response_model=RentInfo)
async def rental_info(rental_id: str, sess: AsyncSession = Depends(get_db_session)):
    try:
        rental = await sess.get(RentalDB, rental_id)
    except ProgrammingError:
        raise HTTPException(
            500, "Database programming error (most likely table does not exist)"
        )

    if not rental:
        raise HTTPException(404, "Rental not found")

    accrued_amount = rental.total_amount
    ended_at = rental.finish_time

    if not rental.finish_time:
        # аренда ещё идёт — считаем через pricing
        async with AsyncClient() as client:
            resp = await client.post(
                f"{rental_query_settings.pricing_url}/v1/calc-accrued",
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


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
