"""
core/database.py — Async SQLAlchemy 2.0 engine и фабрика сессий.

Использование в FastAPI:
    from app.core.database import get_session

    @router.get("/history")
    async def handler(db: AsyncSession = Depends(get_session)):
        ...

Использование в агентах (вне FastAPI):
    async with db_session() as session:
        session.add(trade)
        await session.commit()
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.postgres_url,
    pool_size=5,
    max_overflow=10,
    echo=settings.log_level == "DEBUG",
)

_SessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Контекстный менеджер сессии для использования вне FastAPI (агенты, задачи)."""
    async with _SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends: инъекция сессии в роутеры."""
    async with _SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
