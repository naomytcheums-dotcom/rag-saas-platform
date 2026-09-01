"""
Async SQLAlchemy 2.0 engine/session setup. One engine per process, one
AsyncSession per request via the get_db dependency (api/dependencies.py) --
never a global session shared across requests, which would leak state
between unrelated users under concurrency.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from api.config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency (`Depends(get_db)`) every route uses to get a
    database session. Opens a fresh session per request and closes it
    automatically when the request finishes (the `async with` block) --
    a route function never has to remember to close anything itself.
    """
    async with AsyncSessionLocal() as session:
        yield session
