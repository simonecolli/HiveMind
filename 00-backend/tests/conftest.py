import aiosqlite
import httpx
import pytest_asyncio

from src.app import AppDeps, create_app
from src.db.schema import apply_schema
from tests.support import StubEngines, echo_llm_factory, fixed_titler


@pytest_asyncio.fixture
async def conn():
    """In-memory SQLite connection with the schema applied."""
    async with aiosqlite.connect(":memory:") as c:
        c.row_factory = aiosqlite.Row
        await apply_schema(c)
        yield c


@pytest_asyncio.fixture
async def app_deps(conn):
    return AppDeps(
        conn=conn,
        engines=StubEngines(),
        llm_factory=echo_llm_factory(),
        titler=fixed_titler,
    )


@pytest_asyncio.fixture
async def client(app_deps):
    app = create_app(app_deps, seed=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
