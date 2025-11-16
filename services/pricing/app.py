from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis

from services.pricing.v1 import router as v1_router
from services.shared.settings import pricing_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    rds = Redis.from_url(
        pricing_settings.redis_url, encoding="utf-8", decode_responses=True
    )

    app.state.rds = rds
    await rds.ping()
    yield
    await rds.close()


app = FastAPI(
    title="pricing",
    version="0.1.0",
    contact={"name": "sd-command-9"},
    lifespan=lifespan,
)

app.include_router(v1_router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")
