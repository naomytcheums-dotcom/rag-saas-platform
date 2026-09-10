"""Partie 11.6 -- reads the real system_logs table (fed by
api/security/system_log_handler.py's real logging.Handler)."""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.admin import SystemLog


async def list_system_logs(db: AsyncSession, *, level: str | None = None, logger_name: str | None = None, search: str | None = None, since: dt.datetime | None = None, limit: int = 50, offset: int = 0) -> tuple[list[SystemLog], int]:
    filters = []
    if level:
        filters.append(SystemLog.level == level)
    if logger_name:
        filters.append(SystemLog.logger_name == logger_name)
    if search:
        filters.append(SystemLog.message.ilike(f"%{search}%"))
    if since:
        filters.append(SystemLog.created_at >= since)

    total = await db.scalar(select(func.count()).select_from(SystemLog).where(*filters)) or 0
    rows = list((await db.scalars(select(SystemLog).where(*filters).order_by(SystemLog.created_at.desc()).limit(limit).offset(offset))).all())
    return rows, total


async def get_system_log(db: AsyncSession, log_id: uuid.UUID) -> SystemLog | None:
    return await db.get(SystemLog, log_id)


async def get_logs_stats(db: AsyncSession, days: int = 7) -> dict:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    by_level = (await db.execute(select(SystemLog.level, func.count()).where(SystemLog.created_at >= since).group_by(SystemLog.level))).all()
    by_logger = (await db.execute(
        select(SystemLog.logger_name, func.count()).where(SystemLog.created_at >= since).group_by(SystemLog.logger_name).order_by(func.count().desc()).limit(10)
    )).all()
    return {"by_level": dict(by_level), "top_loggers": dict(by_logger)}


async def get_log_sources(db: AsyncSession) -> list[str]:
    rows = (await db.scalars(select(SystemLog.logger_name).distinct())).all()
    return sorted(rows)


async def purge_old_system_logs(db: AsyncSession, days: int) -> int:
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = (await db.scalars(select(SystemLog).where(SystemLog.created_at < threshold))).all()
    count = len(rows)
    for row in rows:
        await db.delete(row)
    await db.flush()
    return count
