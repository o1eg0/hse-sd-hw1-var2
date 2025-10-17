from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routes import router as routes_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="sd-hw1-var2",
        contact={"name": "sd-command-9"},
        lifespan=lifespan,
        version="0.1.0",
    )

    app.include_router(routes_router)
    return app
