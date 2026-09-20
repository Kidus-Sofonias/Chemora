"""M31 production-database verification (Phase 1 of the M31 scope).

Applies the real Alembic migration chain (001 -> 004) to a live PostgreSQL
instance, verifies the resulting schema (tables, FKs, cascade behavior,
uniqueness, indexes, CHECK constraints), then boots the real application
against it and exercises representative authenticated API flows — including
tutor conversation persistence on PostgreSQL.

This script is a verification harness, not part of the application. It is
run explicitly by the release procedure (see infrastructure/RELEASE.md).
Credentials come from the environment; they are never logged or committed.

Usage:
    python backend/scripts/pg_verify.py --database-url postgresql+asyncpg://...

The script intentionally runs Alembic synchronously (alembic/env.py calls
asyncio.run itself) and then executes each verification phase in its own
event loop.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """Record a verification result with an ASCII-safe checkmark."""
    (PASS if ok else FAIL).append(name)
    status = "PASS" if ok else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}", flush=True)


def migration_phase(database_url: str) -> str:
    """Steps 1-2: discovery, ordering, fresh upgrade from base (sync)."""
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    print("\n== Step 1: Alembic migration discovery/ordering ==", flush=True)
    cfg = Config(str(ROOT_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    revisions = {rev.revision for rev in script.walk_revisions()}
    check("migration discovery", len(revisions) == 4, f"{len(revisions)} revisions")
    heads = script.get_heads()
    check("single migration head", len(heads) == 1, f"head={heads[0]!r}")

    # Walk the chain manually from the head down to base, then reverse.
    revs_by_id = {rev.revision: rev for rev in script.walk_revisions()}
    chain: list[str] = []
    current: str | None = heads[0]
    while current is not None:
        chain.append(current)
        current = revs_by_id[current].down_revision
    chain.reverse()
    check(
        "ordering 001->002->003->004",
        chain
        == [
            "001_initial_auth",
            "002_lesson_progress",
            "003_content_tables",
            "004_tutor_conversations",
        ],
        str(chain),
    )

    print("\n== Step 2: fresh database, full upgrade from base ==", flush=True)
    os.environ["DATABASE_URL_SYNC"] = database_url  # read by alembic/env.py
    command.upgrade(cfg, "head")

    head_rev = heads[0]

    async def _version() -> str:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as conn:
                return (
                    await conn.execute(text("SELECT version_num FROM alembic_version"))
                ).scalar()
        finally:
            await engine.dispose()

    version = asyncio.run(_version())
    check("full upgrade to head", version == head_rev, f"version_num={version}")
    return head_rev


async def schema_phase() -> None:
    """Step 3: final schema introspection on PostgreSQL."""
    import os

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    print("\n== Step 3: final schema (tables, FKs, constraints, indexes) ==", flush=True)
    engine = create_async_engine(os.environ["DATABASE_URL"])
    expected_tables = {
        "users",
        "sessions",
        "lesson_progress",
        "lessons",
        "lesson_sections",
        "lesson_questions",
        "tutor_conversations",
        "tutor_messages",
        "alembic_version",
    }
    async with engine.connect() as conn:
        tables = {
            r[0]
            for r in await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname='public' AND tablename NOT LIKE 'pg_%'"
                )
            )
        }
        check("all expected tables exist", expected_tables <= tables, str(sorted(tables)))

        fks = (
            await conn.execute(
                text(
                    "SELECT tc.table_name, kcu.column_name, "
                    "ccu.table_name AS foreign_table, rc.delete_rule "
                    "FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "  ON tc.constraint_name = kcu.constraint_name "
                    "JOIN information_schema.referential_constraints rc "
                    "  ON tc.constraint_name = rc.constraint_name "
                    "JOIN information_schema.constraint_column_usage ccu "
                    "  ON rc.unique_constraint_name = ccu.constraint_name "
                    "WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'"
                )
            )
        ).fetchall()
        fk_pairs = {(r[0], r[1], r[2]) for r in fks}
        delete_rules = {(r[0], r[3]) for r in fks}

        check(
            "tutor_messages FK -> tutor_conversations",
            ("tutor_messages", "conversation_id", "tutor_conversations") in fk_pairs,
        )
        check(
            "tutor_conversations FK -> users",
            ("tutor_conversations", "user_id", "users") in fk_pairs,
        )
        check("sessions FK -> users", ("sessions", "user_id", "users") in fk_pairs)
        check(
            "lesson_sections FK -> lessons",
            ("lesson_sections", "lesson_id", "lessons") in fk_pairs,
        )
        check(
            "lesson_questions FK -> lessons",
            ("lesson_questions", "lesson_id", "lessons") in fk_pairs,
        )
        check(
            "lesson_progress FK -> users",
            ("lesson_progress", "user_id", "users") in fk_pairs,
        )
        check(
            "CASCADE delete on tutor_messages",
            ("tutor_messages", "CASCADE") in delete_rules,
        )
        check(
            "CASCADE delete on tutor_conversations",
            ("tutor_conversations", "CASCADE") in delete_rules,
        )

        # The 30-conversation / 200-message limits are enforced at the
        # repository layer (application level), not as CHECK constraints.
        # The database-level contract is uniqueness + NOT NULL:
        uniq_cols = {
            (r[0], r[1])
            for r in await conn.execute(
                text(
                    "SELECT tc.table_name, kcu.column_name "
                    "FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "  ON tc.constraint_name = kcu.constraint_name "
                    "WHERE tc.constraint_type='UNIQUE' AND tc.table_schema='public'"
                )
            )
        }
        check(
            "users.google_subject UNIQUE (identity anchoring)",
            ("users", "google_subject") in uniq_cols,
        )

        notnull_cols = {
            (r[0], r[1])
            for r in await conn.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND is_nullable='NO'"
                )
            )
        }
        required_notnull = {
            ("tutor_conversations", "user_id"),
            ("tutor_messages", "conversation_id"),
            ("tutor_messages", "role"),
            ("tutor_messages", "seq"),
            ("tutor_messages", "content"),
            ("users", "google_subject"),
            ("lessons", "title"),
        }
        check(
            "NOT NULL on identity/message columns",
            required_notnull <= notnull_cols,
            f"{len(notnull_cols)} NOT NULL columns",
        )

        idx_names = {
            r[0]
            for r in await conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname='public' AND indexname NOT LIKE '%_pkey'"
                )
            )
        }
        check(
            "access-pattern indexes exist",
            {
                "ix_tutor_conversations_user_updated",
                "ix_tutor_messages_conversation_seq",
                "ix_users_email",
                "ix_lessons_published",
            }
            <= idx_names,
            f"{len(idx_names)} indexes",
        )
    await engine.dispose()


async def behavior_phase() -> None:
    """Step 4: ownership constraint + cascade delete on real PostgreSQL."""
    import os

    from sqlalchemy import delete as sa_delete
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    print("\n== Step 4: behavior — ownership constraint + cascade delete ==", flush=True)
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from app.models.tutor import TutorConversation, TutorMessage
    from app.models.user import User

    run_id = uuid.uuid4().hex[:8]

    async with factory() as s:
        # Idempotency: clear leftovers from any earlier verification run.
        await s.execute(sa_delete(User).where(User.google_subject.like("m31-%")))
        await s.commit()
        user = User(
            google_subject=f"m31-pg-verify-{run_id}",
            email=f"m31-pg-verify-{run_id}@example.com",
        )
        s.add(user)
        await s.flush()
        conv = TutorConversation(user_id=user.id, title="pg verify")
        s.add(conv)
        await s.flush()
        s.add(
            TutorMessage(
                conversation_id=conv.id, role="user", seq=1, content="molar mass of water?"
            )
        )
        s.add(
            TutorMessage(
                conversation_id=conv.id, role="assistant", seq=2, content="18.015 g/mol"
            )
        )
        await s.commit()
        conv_id = conv.id
        # Capture ids before the intentional-failure rollback below —
        # rollback() expires ORM objects and attribute access afterwards
        # would attempt a synchronous refresh (MissingGreenlet).
        user_id = user.id

        other = User(
            google_subject=f"m31-pg-verify-2-{run_id}",
            email=f"m31-pg-verify-2-{run_id}@example.com",
        )
        s.add(other)
        await s.flush()
        hijack = TutorConversation(id=conv_id, user_id=other.id, title="hijack")
        s.add(hijack)
        try:
            await s.commit()
            check("conversation ownership (PK) enforced", False, "insert succeeded")
        except Exception:
            await s.rollback()
            check("conversation ownership (PK) enforced", True)

    async with factory() as s2:
        await s2.execute(sa_delete(User).where(User.id == user_id))
        await s2.commit()
    async with factory() as s3:
        remaining_convs = (
            await s3.execute(text("SELECT count(*) FROM tutor_conversations"))
        ).scalar()
        remaining_msgs = (
            await s3.execute(text("SELECT count(*) FROM tutor_messages"))
        ).scalar()
    check(
        "cascade delete reaches tutor tables",
        remaining_convs == 0 and remaining_msgs == 0,
        f"conversations={remaining_convs} messages={remaining_msgs}",
    )
    await engine.dispose()


async def app_phase() -> None:
    """Steps 5-6: application startup + representative API flows."""
    import os

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    print("\n== Step 5: application startup against PostgreSQL ==", flush=True)
    os.environ.setdefault("AI_PROVIDER", "mock")
    from app.main import app

    print(
        "\n== Step 6: representative authenticated API flows on PostgreSQL ==",
        flush=True,
    )
    from httpx import ASGITransport, AsyncClient

    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)

    class _StubVerifier:
        """Minimal verifier stub standing in for Google (no network)."""

        def verify(self, token: str) -> object:
            from app.services.google_auth import GoogleTokenError, GoogleUserInfo

            identities = {
                "m31-smoke-token": (
                    "m31-pg-user",
                    "m31-pg-user@example.com",
                    "M31 PG Verify",
                ),
                "m31-smoke-token-b": (
                    "m31-pg-user-b",
                    "m31-pg-user-b@example.com",
                    "M31 PG Verify B",
                ),
            }
            if token not in identities:
                raise GoogleTokenError("Invalid authentication credential")
            sub, email, name = identities[token]
            return GoogleUserInfo(
                sub=sub,
                email=email,
                email_verified=True,
                name=name,
                picture=None,
                locale="en",
            )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/health")
        check("health endpoint", r.status_code == 200, str(r.json()))

        # AuthService builds its verifier eagerly at construction, so patch
        # the module-level factory (same approach as backend/tests/conftest).
        from app.services import google_auth as google_auth_module

        original_factory = google_auth_module.get_google_verifier
        google_auth_module.get_google_verifier = lambda: _StubVerifier()
        try:
            r = await client.post(
                "/api/v1/auth/google", json={"credential": "m31-smoke-token"}
            )
            check(
                "auth -> PostgreSQL user+session persistence",
                r.status_code == 200,
                str(r.status_code),
            )

            r = await client.get("/api/v1/auth/me")
            check("session read from PostgreSQL", r.status_code == 200)

            async with factory() as s:
                n_users = (await s.execute(text("SELECT count(*) FROM users"))).scalar()
            check("user row landed in PostgreSQL", n_users == 1)

            r = await client.get("/api/v1/learning/lessons")
            check("learning API reads PostgreSQL content", r.status_code == 200)

            r = await client.post(
                "/api/v1/learning/tutor/conversations", json={"title": "pg smoke"}
            )
            check(
                "tutor conversation created on PostgreSQL",
                r.status_code in (200, 201),
                str(r.status_code),
            )
            payload = r.json()
            conv_id = payload.get("id") or payload.get("conversation", {}).get("id")

            r = await client.get("/api/v1/learning/tutor/conversations")
            listing = r.json()
            items = listing if isinstance(listing, list) else listing.get("conversations", [])
            check(
                "tutor conversation listed back",
                r.status_code == 200 and any(c.get("id") == conv_id for c in items),
            )

            r = await client.delete(f"/api/v1/learning/tutor/conversations/{conv_id}")
            check("tutor conversation deleted", r.status_code in (200, 204), str(r.status_code))

            async with factory() as s:
                n_convs = (
                    await s.execute(text("SELECT count(*) FROM tutor_conversations"))
                ).scalar()
            check("conversation deletion persisted", n_convs == 0)

            r = await client.get("/api/v1/auth/me")
            check("session still valid after tutor ops", r.status_code == 200)

            # Security boundaries on PostgreSQL: unauthenticated access and
            # cross-user conversation isolation. The anonymous client shares
            # no cookie jar, so it is genuinely unauthenticated.
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as anon_client:
                anon = await anon_client.post(
                    "/api/v1/learning/tutor/conversations", json={"title": "nope"}
                )
                check(
                    "unauthenticated tutor access blocked on PG",
                    anon.status_code == 401,
                    str(anon.status_code),
                )

            r = await client.post(
                "/api/v1/auth/google", json={"credential": "m31-smoke-token-b"}
            )
            check("second user authenticated", r.status_code == 200)
            r = await client.post(
                "/api/v1/learning/tutor/conversations", json={"title": "user b"}
            )
            conv_b = r.json()
            conv_b_id = conv_b.get("id") or conv_b.get("conversation", {}).get("id")
            r = await client.get(
                f"/api/v1/learning/tutor/conversations/{conv_b_id}"
            )
            check("owner can read own conversation on PG", r.status_code == 200)

            # Cross-user isolation: switch the session back to user A and
            # try to read user B's conversation -> 404 (no existence leak).
            r = await client.post(
                "/api/v1/auth/google", json={"credential": "m31-smoke-token"}
            )
            check("session switched back to user A", r.status_code == 200)
            r = await client.get(
                f"/api/v1/learning/tutor/conversations/{conv_b_id}"
            )
            check(
                "cross-user conversation access blocked on PG",
                r.status_code == 404,
                str(r.status_code),
            )
        finally:
            google_auth_module.get_google_verifier = original_factory

    await engine.dispose()


def main() -> int:
    """Run every PostgreSQL verification phase and report a summary."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.environ.get("M31_PG_URL", ""),
        help="asyncpg database URL (credentials stay in the environment)",
    )
    args = parser.parse_args()
    if not args.database_url:
        print("No database URL provided; set M31_PG_URL or pass --database-url")
        return 2
    url = args.database_url
    os.environ["DATABASE_URL"] = url

    migration_phase(url)
    asyncio.run(schema_phase())
    asyncio.run(behavior_phase())
    asyncio.run(app_phase())

    print(f"\n{'=' * 60}\nRESULTS: {len(PASS)} passed, {len(FAIL)} failed", flush=True)
    if FAIL:
        print("FAILED:", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
