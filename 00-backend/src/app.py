from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.seed import seed_default_team
from src.debate import DebateHub
from src.routes import agents, dashboard, sessions, system, teams

API_PREFIX = "/api/v1"


@dataclass
class AppDeps:
    """Everything the routes do not build for themselves.

    Injecting it from outside is what makes the API testable with no local
    engine running and without touching the disk.
    """

    conn: aiosqlite.Connection | None
    engines: Any
    llm_factory: Callable[[str, str], Any]
    titler: Callable[[str], Awaitable[str | None]]
    checkpointer: Any | None = None
    hub: DebateHub = field(default_factory=DebateHub)


def create_app(
    deps: AppDeps,
    *,
    seed: bool = True,
    connect: Callable[[], Awaitable[aiosqlite.Connection]] | None = None,
    checkpointer_factory: Callable[[], Any] | None = None,
    cors_origins: tuple[str, ...] = ("http://localhost:5173",),
) -> FastAPI:
    """`connect` and `checkpointer_factory` open resources at startup.

    They cannot be opened earlier: both create aiosqlite connections, which are
    bound to the event loop that creates them, and uvicorn's loop only exists
    after the app has been built.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owns_connection = connect is not None
        async with AsyncExitStack() as stack:
            if owns_connection:
                deps.conn = await connect()
                # Only close the connection it opened: an injected one belongs
                # to whoever created it.
                stack.push_async_callback(_release_connection, deps)
            if checkpointer_factory is not None:
                deps.checkpointer = await stack.enter_async_context(checkpointer_factory())
                stack.push_async_callback(_release_checkpointer, deps)
            if seed:
                await seed_default_team(deps.conn)
            yield

    app = FastAPI(title="HiveMind", version="0.1.0", lifespan=lifespan)
    app.state.deps = deps
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (
        system.router,
        dashboard.router,
        teams.router,
        agents.router,
        sessions.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    return app


async def _release_connection(deps: AppDeps) -> None:
    if deps.conn is not None:
        await deps.conn.close()
        deps.conn = None


async def _release_checkpointer(deps: AppDeps) -> None:
    deps.checkpointer = None
