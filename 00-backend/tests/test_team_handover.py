"""Handing a running session over to a different team.

A follow-up may name another team: the session keeps its thread, its canvas and
its summaries, but the next pass is argued by someone else. That is how a panel
of personas feeds a desk of professionals without copying text by hand.
"""

import httpx
import pytest_asyncio

from src.app import AppDeps, create_app
from tests.support import StubEngines, collect_events, fixed_titler, recording_llm_factory


@pytest_asyncio.fixture
async def recording(conn):
    """A client whose models all answer the same recognisable line."""
    sink: list[list] = []
    app = create_app(
        AppDeps(
            conn=conn,
            engines=StubEngines(),
            llm_factory=recording_llm_factory(sink, "PANEL VERDICT"),
            titler=fixed_titler,
        ),
        seed=False,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, sink


async def _team(client, name: str, *, protocol="relay", rounds=1, agents=None, model="m") -> int:
    team = (
        await client.post(
            "/api/v1/teams",
            json={
                "name": name,
                "synthesis_prompt": "x",
                "protocol": protocol,
                "default_max_rounds": rounds,
            },
        )
    ).json()
    for agent_name in agents or [f"{name} agent"]:
        await client.post(
            f"/api/v1/teams/{team['id']}/agents",
            json={"name": agent_name, "system_prompt": "speak", "model": model},
        )
    return team["id"]


async def _session(client, team_id: int) -> str:
    session_id = (
        await client.post("/api/v1/sessions", json={"idea": "an idea", "team_id": team_id})
    ).json()["session_id"]
    await collect_events(client, session_id)
    return session_id


async def _detail(client, session_id) -> dict:
    return (await client.get(f"/api/v1/sessions/{session_id}")).json()


async def _names(client, session_id, pass_no: int) -> list[str]:
    turns = (await _detail(client, session_id))["turns"]
    return [t["agent_name"] for t in turns if t["pass_no"] == pass_no]


async def _hand_over(client, session_id, team_id, **extra):
    return await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"text": "over to you", "team_id": team_id, **extra},
    )


async def test_a_follow_up_can_hand_the_session_to_another_team(client):
    panel = await _team(client, "Panel", agents=["Persona"])
    desk = await _team(client, "Desk", agents=["Strategist"])
    session_id = await _session(client, panel)

    response = await _hand_over(client, session_id, desk)
    await collect_events(client, session_id)

    assert response.status_code == 201
    assert await _names(client, session_id, 1) == ["Persona", "Synthesis"]
    assert await _names(client, session_id, 2) == ["You", "Strategist", "Synthesis"]


async def test_a_later_pass_stays_with_the_team_that_took_over(client):
    """A follow-up that names nobody continues with whoever holds the floor."""
    panel = await _team(client, "Panel", agents=["Persona"])
    desk = await _team(client, "Desk", agents=["Strategist"])
    session_id = await _session(client, panel)
    await _hand_over(client, session_id, desk)
    await collect_events(client, session_id)

    await client.post(f"/api/v1/sessions/{session_id}/messages", json={"text": "go on"})
    await collect_events(client, session_id)

    assert await _names(client, session_id, 3) == ["You", "Strategist", "Synthesis"]


async def test_the_incoming_team_brings_its_own_round_count(client):
    """The desk was configured for two rounds; the panel session ran one."""
    panel = await _team(client, "Panel", rounds=1, agents=["Persona"])
    desk = await _team(client, "Desk", rounds=2, agents=["Strategist"])
    session_id = await _session(client, panel)

    await _hand_over(client, session_id, desk)
    await collect_events(client, session_id)

    turns = (await _detail(client, session_id))["turns"]
    rounds = [t["round"] for t in turns if t["pass_no"] == 2 and t["kind"] == "agent"]
    assert rounds == [1, 2]


async def test_an_explicit_round_count_still_wins(client):
    panel = await _team(client, "Panel", rounds=1, agents=["Persona"])
    desk = await _team(client, "Desk", rounds=2, agents=["Strategist"])
    session_id = await _session(client, panel)

    await _hand_over(client, session_id, desk, max_rounds=3)
    await collect_events(client, session_id)

    turns = (await _detail(client, session_id))["turns"]
    rounds = [t["round"] for t in turns if t["pass_no"] == 2 and t["kind"] == "agent"]
    assert rounds == [1, 2, 3]


async def test_the_incoming_team_reads_what_the_previous_one_concluded(recording):
    """The whole point of the handover, and the one thing that must not break.

    The desk never sees the panel's transcript - only its summary, which is why
    that summary is an interface rather than a piece of prose for the reader.
    """
    client, sink = recording
    panel = await _team(client, "Panel", agents=["Persona"])
    desk = await _team(client, "Desk", agents=["Strategist"])
    session_id = await _session(client, panel)
    sink.clear()

    await _hand_over(client, session_id, desk)
    await collect_events(client, session_id)

    # The first call of pass 2 is the incoming team's own agent.
    strategist_read = str(sink[0][-1].content)
    assert "SUMMARIES OF THE EARLIER PASSES" in strategist_read
    assert "PANEL VERDICT" in strategist_read


async def test_the_canvas_draws_each_half_with_its_own_protocol(client):
    panel = await _team(client, "Panel", protocol="swarm", agents=["One", "Two"])
    desk = await _team(client, "Desk", protocol="relay", agents=["Lead", "Second"])
    session_id = await _session(client, panel)

    await _hand_over(client, session_id, desk)
    await collect_events(client, session_id)

    canvas = (await _detail(client, session_id))["canvas"]
    by_id = {n["id"]: n["data"]["agent_name"] for n in canvas["nodes"] if n["id"] != "idea"}
    pairs = {(by_id.get(e["source"], e["source"]), by_id.get(e["target"], e["target"]))
             for e in canvas["edges"]}
    # The panel fanned out of the idea and never talked to itself.
    assert ("idea", "One") in pairs and ("idea", "Two") in pairs
    assert ("One", "Two") not in pairs
    # The desk ran as a thread.
    assert ("Lead", "Second") in pairs


async def test_the_session_records_who_ran_each_pass(client):
    panel = await _team(client, "Panel", protocol="swarm", agents=["Persona"])
    desk = await _team(client, "Desk", protocol="relay", agents=["Strategist"])
    session_id = await _session(client, panel)

    await _hand_over(client, session_id, desk)
    await collect_events(client, session_id)

    passes = (await _detail(client, session_id))["passes"]
    assert [(p["pass_no"], p["team_name"], p["protocol"]) for p in passes] == [
        (1, "Panel", "swarm"),
        (2, "Desk", "relay"),
    ]


async def test_the_handover_survives_the_incoming_team_being_deleted(client):
    """The incoming team is snapshotted too, exactly like the first one."""
    panel = await _team(client, "Panel", agents=["Persona"])
    desk = await _team(client, "Desk", agents=["Strategist"])
    session_id = await _session(client, panel)
    await _hand_over(client, session_id, desk)
    await collect_events(client, session_id)

    await client.delete(f"/api/v1/teams/{desk}")
    response = await client.post(
        f"/api/v1/sessions/{session_id}/messages", json={"text": "still here?"}
    )
    await collect_events(client, session_id)

    assert response.status_code == 201
    assert await _names(client, session_id, 3) == ["You", "Strategist", "Synthesis"]


async def test_handing_over_to_an_unknown_team_gives_404(client):
    panel = await _team(client, "Panel", agents=["Persona"])
    session_id = await _session(client, panel)

    response = await _hand_over(client, session_id, 9999)

    assert response.status_code == 404


async def test_handing_over_to_a_team_with_no_enabled_agents_gives_422(client):
    panel = await _team(client, "Panel", agents=["Persona"])
    empty = (
        await client.post(
            "/api/v1/teams", json={"name": "Empty", "synthesis_prompt": "x"}
        )
    ).json()["id"]
    session_id = await _session(client, panel)

    response = await _hand_over(client, session_id, empty)

    assert response.status_code == 422


async def test_the_incoming_team_is_the_one_checked_against_the_engines(client):
    """The panel's models are installed; the desk asks for one that is not."""
    panel = await _team(client, "Panel", agents=["Persona"])
    desk = await _team(client, "Desk", agents=["Strategist"], model="not-installed")
    session_id = await _session(client, panel)

    response = await _hand_over(client, session_id, desk)

    assert response.status_code == 422
    assert "not-installed" in response.json()["detail"]
