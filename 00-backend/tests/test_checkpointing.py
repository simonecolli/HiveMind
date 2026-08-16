import httpx
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.app import AppDeps, create_app
from src.graph.builder import build_graph, initial_state
from tests.support import (
    StubEngines,
    agent,
    echo_llm_factory,
    fixed_titler,
    make_deps,
    team,
)


async def test_the_debate_leaves_an_inspectable_state(tmp_path):
    config = {"configurable": {"thread_id": "s1"}}

    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "checkpoints.db")) as saver:
        graph = build_graph(team(), [agent(1, "Creative", 0)], make_deps(), checkpointer=saver)
        await graph.ainvoke(initial_state("s1", "an idea", 1), config=config)

        snapshot = await graph.aget_state(config)

    assert [t.agent_name for t in snapshot.values["turns"]] == ["Creative", "Synthesis"]


async def test_checkpoints_are_kept_apart_per_session(tmp_path):
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "checkpoints.db")) as saver:
        graph = build_graph(team(), [agent(1, "Creative", 0)], make_deps(), checkpointer=saver)
        await graph.ainvoke(
            initial_state("s1", "first idea", 1), config={"configurable": {"thread_id": "s1"}}
        )
        await graph.ainvoke(
            initial_state("s2", "second idea", 1), config={"configurable": {"thread_id": "s2"}}
        )

        first = await graph.aget_state({"configurable": {"thread_id": "s1"}})
        second = await graph.aget_state({"configurable": {"thread_id": "s2"}})

    assert first.values["idea"] == "first idea"
    assert second.values["idea"] == "second idea"


async def test_a_session_started_from_the_api_leaves_a_checkpoint(conn, tmp_path):
    """The checkpoint thread is `{session}:{pass}`.

    One thread per pass, because a LangGraph thread that reached END cannot be
    invoked again - a follow-up would have nowhere to run.
    """
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "checkpoints.db")) as saver:
        deps = AppDeps(
            conn=conn,
            engines=StubEngines(),
            llm_factory=echo_llm_factory(),
            titler=fixed_titler,
            checkpointer=saver,
        )
        app = create_app(deps, seed=False)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            team_payload = (
                await client.post(
                    "/api/v1/teams", json={"name": "Board", "synthesis_prompt": "x"}
                )
            ).json()
            await client.post(
                f"/api/v1/teams/{team_payload['id']}/agents",
                json={"name": "Advocate", "system_prompt": "push back", "model": "m"},
            )
            session_id = (
                await client.post(
                    "/api/v1/sessions", json={"idea": "an idea", "team_id": team_payload["id"]}
                )
            ).json()["session_id"]

            async with client.stream(
                "GET", f"/api/v1/sessions/{session_id}/stream"
            ) as response:
                async for _ in response.aiter_lines():
                    pass

        first_pass = await saver.aget_tuple(
            {"configurable": {"thread_id": f"{session_id}:1"}}
        )
        bare_session = await saver.aget_tuple({"configurable": {"thread_id": session_id}})

    assert first_pass is not None
    assert bare_session is None


async def test_the_checkpoint_file_is_separate_from_the_app_database(tmp_path):
    path = tmp_path / "checkpoints.db"

    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        graph = build_graph(team(), [agent(1, "Creative", 0)], make_deps(), checkpointer=saver)
        await graph.ainvoke(
            initial_state("s1", "an idea", 1), config={"configurable": {"thread_id": "s1"}}
        )

    assert path.exists()
