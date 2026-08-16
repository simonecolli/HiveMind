"""HiveMind backend entrypoint.

    uv run main.py            (or: uv run uvicorn main:app --reload)
"""

import aiosqlite
import httpx
import uvicorn
from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.app import AppDeps, create_app
from src.config import Settings
from src.db.schema import apply_schema
from src.llm.provider import Engines, LMStudioProvider, OllamaProvider
from src.llm.titles import make_titler


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    http = httpx.AsyncClient(timeout=15.0)
    engines = Engines(
        [
            OllamaProvider(
                settings.ollama_url,
                http,
                max_output_tokens=settings.max_output_tokens,
                thinking=settings.ollama_thinking
            ),
            LMStudioProvider(
                settings.lmstudio_url, http, max_output_tokens=settings.max_output_tokens
            ),
        ]
    )
    deps = AppDeps(
        conn=None,
        engines=engines,
        llm_factory=engines.chat,
        titler=make_titler(engines.chat, settings.title_provider, settings.title_model),
    )

    async def connect() -> aiosqlite.Connection:
        conn = await aiosqlite.connect(settings.db_path)
        conn.row_factory = aiosqlite.Row
        # WAL: readers and the writer stop blocking each other.
        await conn.execute("PRAGMA journal_mode = WAL")
        await apply_schema(conn)
        return conn

    return create_app(
        deps,
        connect=connect,
        checkpointer_factory=lambda: AsyncSqliteSaver.from_conn_string(
            str(settings.checkpoints_path)
        ),
        cors_origins=settings.cors_origins,
    )


app = build_app()


def main() -> None:
    settings = Settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
