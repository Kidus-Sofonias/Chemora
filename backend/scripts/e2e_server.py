"""E2E backend server for critical browser flows (M31 Phase 6).

Serves the REAL Chemora FastAPI application (real routes, real session auth,
real ChemEngine) with exactly two documented seams:

1. ``--fake-google`` swaps the Google ID-token verifier for a deterministic
   stub so the login flow can be exercised without a real Google account.
   This mirrors backend/tests/conftest.py and never touches production code.
2. ``--fake-provider`` sets AI_PROVIDER=mock so tutor responses are
   deterministic. This is the default setting anyway.

Storage is SQLite here (a demo/dev profile per app/db/session.py) so the E2E
server needs no database credentials; the production PostgreSQL path is
verified separately by backend/scripts/pg_verify.py.

The server prints its base URL on stdout and shuts down on SIGINT/SIGTERM.

Usage:
    python backend/scripts/e2e_server.py --host 127.0.0.1 --port 8931
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def main() -> int:
    """Serve the real app with documented E2E seams enabled."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8931)
    parser.add_argument(
        "--fake-google",
        action="store_true",
        help="Use a deterministic Google token verifier (E2E seam).",
    )
    parser.add_argument(
        "--fake-provider",
        action="store_true",
        help="Force AI_PROVIDER=mock for deterministic tutor answers.",
    )
    args = parser.parse_args()

    os.environ.setdefault("AI_PROVIDER", "mock" if args.fake_provider else "mock")
    # SQLite file storage for the E2E run (demo profile, documented seam).
    # A per-pid filename avoids stale-handle interference between runs.
    os.environ.setdefault(
        "DATABASE_URL", f"sqlite+aiosqlite:///./e2e_chemora_{os.getpid()}.db"
    )
    # The production bundle is served by `vite preview` on 4173 during E2E;
    # allow that origin (plus the dev defaults) so the browser can call us.
    os.environ.setdefault(
        "CORS_ALLOW_ORIGINS",
        '["http://localhost:5173", "http://127.0.0.1:5173", '
        '"http://localhost:4173", "http://127.0.0.1:4173"]',
    )

    if args.fake_google:
        # Import app modules first so the patch lands on the module the
        # AuthService reads at construction time.
        from app.services import google_auth as google_auth_module

        class _StubVerifier:
            """Deterministic stand-in for Google ID-token verification."""

            def verify(self, token: str) -> object:
                from app.services.google_auth import (
                    GoogleTokenError,
                    GoogleUserInfo,
                )

                if token.startswith("e2e-cred-"):
                    suffix = token.removeprefix("e2e-cred-")
                    return GoogleUserInfo(
                        sub=f"e2e-user-{suffix}",
                        email=f"e2e-user-{suffix}@example.com",
                        email_verified=True,
                        name=f"E2E User {suffix}",
                        picture=None,
                        locale="en",
                    )
                raise GoogleTokenError("Invalid authentication credential")

        google_auth_module.get_google_verifier = lambda: _StubVerifier()
        print("E2E seam: fake Google verifier active", flush=True)

    # Seed content the same way production does (startup seeding is part of
    # the real app; this mirrors the test conftest behavior for SQLite).
    import asyncio

    from app.db.base import Base
    from app.db.session import engine
    from app.learning.seed import seed_content

    async def _prepare() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            await seed_content(session)
            await session.commit()

    asyncio.run(_prepare())
    print("E2E seam: database prepared (SQLite) + content seeded", flush=True)

    from app.main import app

    print(f"E2E server ready on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
