"""Deterministic seed/import of educational content into PostgreSQL (M26).

The seed *source* remains ``app.learning.content``; this module is the only
place that copies it into the database. The process is:

- deterministic — the same content always produces the same rows,
- idempotent — existing lessons are updated in place, keyed by slug, never
  duplicated, so re-running it is always safe,
- repeatable — safe to run at any time (e.g. after pulling content changes).

Run it manually against a configured database::

    cd backend && python -m app.learning.seed

Every seeded lesson is published, because those lessons were already
student-visible in M24/M25 — the database-backed catalog therefore matches the
previous behaviour exactly. ``lesson_progress`` rows stay valid because slugs
are preserved.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.learning.content import get_lessons
from app.repositories.content import ContentRepository

logger = logging.getLogger(__name__)


async def seed_content(db: AsyncSession) -> dict[str, int]:
    """Insert/refresh every seeded lesson and return simple counters.

    Args:
        db: Async database session (the caller commits).

    Returns:
        Counters: ``{"lessons": n, "created": n, "updated": n}``.
    """
    repo = ContentRepository(db)
    created = 0
    updated = 0
    for lesson in get_lessons():
        existed = await repo.slug_exists(lesson.slug)
        await repo.upsert_lesson(lesson, published=True)
        if existed:
            updated += 1
        else:
            created += 1
    return {"lessons": created + updated, "created": created, "updated": updated}


async def _main() -> None:
    """CLI entry point: seed the configured database and commit."""
    from app.db.session import async_session_factory

    logging.basicConfig(level=logging.INFO)
    async with async_session_factory() as session:
        try:
            counts = await seed_content(session)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    logger.info("Seeded %s lesson(s) (%s new, %s updated)", counts["lessons"], counts["created"], counts["updated"])


if __name__ == "__main__":
    asyncio.run(_main())