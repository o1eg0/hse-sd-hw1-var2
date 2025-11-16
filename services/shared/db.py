from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_engine_from_config, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession


async def create_async_sessionmaker(url: str):
    engine = async_engine_from_config({"url": url}, prefix="")
    sessmaker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Аналог ping
    async with sessmaker() as sess:
        await sess.exec(text("SELECT 1"))
    return sessmaker
