import aiosqlite
import httpx

from src.app import AppDeps, create_app
from src.db.schema import apply_schema
from tests.support import StubEngines, echo_llm_factory, fixed_titler


async def _connect() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_schema(conn)
    return conn


def _deps() -> AppDeps:
    return AppDeps(
        conn=None,
        engines=StubEngines(),
        llm_factory=echo_llm_factory(),
        titler=fixed_titler,
    )


class _Booted:
    """Starts the app through its lifespan, the way uvicorn would."""

    def __init__(self, app):
        self._app = app

    async def __aenter__(self):
        self._lifespan = self._app.router.lifespan_context(self._app)
        await self._lifespan.__aenter__()
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._app), base_url="http://test"
        )
        return self._client

    async def __aexit__(self, *exc):
        await self._client.aclose()
        await self._lifespan.__aexit__(*exc)


async def test_startup_opens_the_database_and_seeds_the_default_team():
    deps = _deps()

    async with _Booted(create_app(deps, connect=_connect, seed=True)) as client:
        teams = (await client.get("/api/v1/teams")).json()
        assert deps.conn is not None

    assert [t["name"] for t in teams] == ["Board of Directors"]


async def test_shutdown_closes_the_connection_the_app_opened():
    deps = _deps()

    async with _Booted(create_app(deps, connect=_connect, seed=False)):
        pass

    assert deps.conn is None


async def test_the_default_team_holds_the_three_agents_from_the_readme():
    async with _Booted(create_app(_deps(), connect=_connect, seed=True)) as client:
        team_id = (await client.get("/api/v1/teams")).json()[0]["id"]
        agents = (await client.get(f"/api/v1/teams/{team_id}")).json()["agents"]

    assert [a["name"] for a in agents] == [
        "Creative Director",
        "Devil's Advocate",
        "Software Architect",
    ]


async def test_startup_opens_the_checkpointer_and_closes_it_on_shutdown(tmp_path):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    deps = _deps()
    path = tmp_path / "checkpoints.db"
    app = create_app(
        deps,
        connect=_connect,
        seed=False,
        checkpointer_factory=lambda: AsyncSqliteSaver.from_conn_string(str(path)),
    )

    async with _Booted(app):
        assert deps.checkpointer is not None

    assert deps.checkpointer is None


async def test_seeding_does_not_duplicate_on_every_startup(tmp_path):
    """On a file, so both startups really see the same database."""
    db_path = tmp_path / "hivemind.db"

    async def connect():
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await apply_schema(conn)
        return conn

    for _ in range(2):
        async with _Booted(create_app(_deps(), connect=connect, seed=True)) as client:
            teams = (await client.get("/api/v1/teams")).json()

    assert len(teams) == 1


async def test_without_seeding_there_is_no_team_at_all():
    async with _Booted(create_app(_deps(), connect=_connect, seed=False)) as client:
        teams = (await client.get("/api/v1/teams")).json()

    assert teams == []
