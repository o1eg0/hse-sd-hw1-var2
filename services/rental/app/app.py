from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .v1 import router as v1_router


def get_description() -> str:
    with open(Path(__file__).parent.parent / "README.md", "r") as readme:
        return readme.read()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rental",
        description=get_description(),
        contact={"name": "sd-command-9"},
        lifespan=lifespan,
        version="0.1.0",
    )

    app.include_router(v1_router)
    return app
