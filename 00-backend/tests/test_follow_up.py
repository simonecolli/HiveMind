"""A second pass over the same team, carrying the previous syntheses."""

from src.db.sessions import SessionsRepository
from tests.support import collect_events


async def _finished_session(client, *, rounds: int = 1) -> str:
    team = (
        await client.post(
            "/api/v1/teams",
            json={"name": "Board", "synthesis_prompt": "x", "default_max_rounds": rounds},
        )
    ).json()
    await client.post(
        f"/api/v1/teams/{team['id']}/agents",
        json={"name": "Advocate", "system_prompt": "push back", "model": "m"},
    )
    session_id = (
        await client.post("/api/v1/sessions", json={"idea": "an idea", "team_id": team["id"]})
    ).json()["session_id"]
    await collect_events(client, session_id)
    return session_id


async def _turns(client, session_id) -> list[dict]:
    return (await client.get(f"/api/v1/sessions/{session_id}")).json()["turns"]


async def test_a_message_starts_a_second_pass(client):
    session_id = await _finished_session(client)

    response = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"text": "and if we did it outdoors?"}
    )
    await collect_events(client, session_id)

    assert response.status_code == 201
    assert {t["pass_no"] for t in await _turns(client, session_id)} == {1, 2}


async def test_the_message_is_stored_as_a_turn_of_its_own_kind(client):
    session_id = await _finished_session(client)

    await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"text": "and if we did it outdoors?"}
    )
    await collect_events(client, session_id)

    message = next(t for t in await _turns(client, session_id) if t["kind"] == "message")
    assert message["text"] == "and if we did it outdoors?"
    assert message["pass_no"] == 2


async def test_seq_keeps_counting_across_passes(client):
    session_id = await _finished_session(client)

    await client.post(f"/api/v1/sessions/{session_id}/messages", json={"text": "more"})
    await collect_events(client, session_id)

    turns = await _turns(client, session_id)
    assert [t["seq"] for t in turns] == list(range(len(turns)))


async def test_the_second_pass_runs_the_same_agents(client):
    session_id = await _finished_session(client)

    await client.post(f"/api/v1/sessions/{session_id}/messages", json={"text": "more"})
    await collect_events(client, session_id)

    second = [t for t in await _turns(client, session_id) if t["pass_no"] == 2]
    assert [t["agent_name"] for t in second] == ["You", "Advocate", "Synthesis"]


async def test_the_rounds_can_be_overridden_for_a_single_message(client):
    session_id = await _finished_session(client, rounds=1)

    await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"text": "dig deeper", "max_rounds": 3}
    )
    await collect_events(client, session_id)

    second = [t for t in await _turns(client, session_id) if t["pass_no"] == 2]
    assert [t["round"] for t in second if t["kind"] == "agent"] == [1, 2, 3]


async def test_without_an_override_the_session_rounds_are_reused(client):
    session_id = await _finished_session(client, rounds=2)

    await client.post(f"/api/v1/sessions/{session_id}/messages", json={"text": "more"})
    await collect_events(client, session_id)

    second = [t for t in await _turns(client, session_id) if t["pass_no"] == 2]
    assert [t["round"] for t in second if t["kind"] == "agent"] == [1, 2]


async def test_the_follow_up_survives_the_team_being_deleted(client):
    """The frozen snapshot is what keeps a thread coherent to the end."""
    session_id = await _finished_session(client)
    team_id = (await client.get("/api/v1/teams")).json()[0]["id"]
    await client.delete(f"/api/v1/teams/{team_id}")

    response = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"text": "still here?"}
    )
    await collect_events(client, session_id)

    assert response.status_code == 201
    second = [t for t in await _turns(client, session_id) if t["pass_no"] == 2]
    assert [t["agent_name"] for t in second] == ["You", "Advocate", "Synthesis"]


async def test_the_canvas_holds_both_passes(client):
    session_id = await _finished_session(client)

    await client.post(f"/api/v1/sessions/{session_id}/messages", json={"text": "more"})
    await collect_events(client, session_id)

    canvas = (await client.get(f"/api/v1/sessions/{session_id}")).json()["canvas"]
    types = [n["type"] for n in canvas["nodes"]]
    assert types == ["idea", "agent", "synthesis", "message", "agent", "synthesis"]


async def test_a_message_on_a_running_session_gives_409(client, conn):
    session_id = await _finished_session(client)
    await SessionsRepository(conn).mark_running(session_id)

    response = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"text": "too soon"}
    )

    assert response.status_code == 409


async def test_a_message_on_an_unknown_session_gives_404(client):
    response = await client.post(
        "/api/v1/sessions/does-not-exist/messages", json={"text": "hello"}
    )

    assert response.status_code == 404


async def test_an_empty_message_gives_422(client):
    session_id = await _finished_session(client)

    response = await client.post(f"/api/v1/sessions/{session_id}/messages", json={"text": "  "})

    assert response.status_code == 422
