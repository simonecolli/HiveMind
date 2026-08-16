"""Stopping a debate while it runs."""

import pytest

from src.db.sessions import SessionsRepository
from src.graph.builder import build_graph, initial_state
from src.graph.errors import DebateStopped
from tests.support import (
    InMemoryRecorder,
    RecordingEmitter,
    agent,
    echo_llm_factory,
    make_deps,
    stop_after,
    team,
)


async def _run(deps, agents=None, *, max_rounds=1):
    graph = build_graph(team(), agents or [agent(1, "Advocate", 0)], deps)
    await graph.ainvoke(initial_state("s1", "an idea", max_rounds))


async def test_a_stop_ends_the_debate_with_its_own_error():
    deps = make_deps(should_stop=stop_after(0))

    with pytest.raises(DebateStopped):
        await _run(deps)


async def test_nothing_runs_when_the_stop_is_already_set():
    recorder = InMemoryRecorder()
    deps = make_deps(should_stop=stop_after(0), recorder=recorder)

    with pytest.raises(DebateStopped):
        await _run(deps)

    assert recorder.started == []


async def test_the_turn_being_written_keeps_its_partial_text():
    """The words already on screen must not vanish when you press stop."""
    recorder = InMemoryRecorder()
    deps = make_deps(
        llm_factory=echo_llm_factory({"m": "hello there"}),
        recorder=recorder,
        # entry check, then two tokens, then stop
        should_stop=stop_after(3),
    )

    with pytest.raises(DebateStopped):
        await _run(deps)

    assert len(recorder.finished) == 1
    assert recorder.finished[0]["text"] == "he"


async def test_a_turn_stopped_before_its_first_token_is_discarded():
    """An empty bubble in the transcript reads as a bug, and there is nothing
    to preserve when no word was produced."""
    recorder = InMemoryRecorder()
    deps = make_deps(recorder=recorder, should_stop=stop_after(1))

    with pytest.raises(DebateStopped):
        await _run(deps)

    assert recorder.discarded == [1]
    assert recorder.finished == []


async def test_the_stopped_turn_is_still_closed_for_the_reader():
    emitter = RecordingEmitter()
    deps = make_deps(emitter=emitter, should_stop=stop_after(3))

    with pytest.raises(DebateStopped):
        await _run(deps)

    assert "turn.end" in emitter.names()


async def test_the_agents_after_the_stop_never_speak():
    recorder = InMemoryRecorder()
    agents = [agent(1, "First", 0), agent(2, "Second", 1)]
    # The first agent spends three checks (entry plus two tokens); the fourth is
    # the second agent's entry, and that is where the stop lands.
    deps = make_deps(
        llm_factory=echo_llm_factory({"m": "ab"}), recorder=recorder, should_stop=stop_after(3)
    )

    with pytest.raises(DebateStopped):
        await _run(deps, agents)

    assert [t["agent_name"] for t in recorder.started] == ["First"]


async def test_stopping_an_unknown_session_gives_404(client):
    response = await client.post("/api/v1/sessions/does-not-exist/stop")

    assert response.status_code == 404


async def test_stopping_a_finished_session_gives_409(client):
    session_id = await _finished_session(client)

    response = await client.post(f"/api/v1/sessions/{session_id}/stop")

    assert response.status_code == 409


async def test_a_session_orphaned_by_a_restart_can_still_be_closed(client, conn, app_deps):
    """The debate task is gone with the process, but the row still says running."""
    session_id = await _finished_session(client)
    await SessionsRepository(conn).mark_running(session_id)
    app_deps.hub.discard(session_id)

    response = await client.post(f"/api/v1/sessions/{session_id}/stop")

    assert response.status_code == 204
    assert (await SessionsRepository(conn).get(session_id)).status == "stopped"


async def test_a_stopped_session_still_accepts_a_follow_up(client, conn):
    session_id = await _finished_session(client)
    await SessionsRepository(conn).finish(session_id, status="stopped")

    response = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"text": "let us try again"}
    )

    assert response.status_code == 201


async def _finished_session(client) -> str:
    from tests.support import collect_events

    team_payload = (
        await client.post(
            "/api/v1/teams",
            json={"name": "Board", "synthesis_prompt": "x", "default_max_rounds": 1},
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
    await collect_events(client, session_id)
    return session_id
