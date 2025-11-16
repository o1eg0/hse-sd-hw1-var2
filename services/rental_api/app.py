from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from services.rental_api.v1 import router as v1_router
from services.shared.db import create_async_sessionmaker
from services.shared.settings import rental_query_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_maker = await create_async_sessionmaker(rental_query_settings.database_url)
    app.state.sessmaker = session_maker
    yield


app = FastAPI(
    title="rental-api",
    contact={"name": "sd-command-9"},
    lifespan=lifespan,
    version="0.1.0",
)
app.include_router(v1_router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
