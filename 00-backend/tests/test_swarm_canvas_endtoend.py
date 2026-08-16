"""The protocol has to reach the canvas, live and on reload."""

from tests.support import collect_events


async def _team(client, protocol: str) -> dict:
    team = (
        await client.post(
            "/api/v1/teams",
            json={
                "name": f"Board {protocol}",
                "synthesis_prompt": "x",
                "protocol": protocol,
                "default_max_rounds": 1,
            },
        )
    ).json()
    for name in ("A", "B"):
        await client.post(
            f"/api/v1/teams/{team['id']}/agents",
            json={"name": name, "system_prompt": "p", "model": "m"},
        )
    return team


async def _run(client, protocol: str) -> str:
    team = await _team(client, protocol)
    session_id = (
        await client.post("/api/v1/sessions", json={"idea": "x", "team_id": team["id"]})
    ).json()["session_id"]
    await collect_events(client, session_id)
    return session_id


async def test_a_swarm_session_reloads_as_a_mesh(client):
    session_id = await _run(client, "swarm")

    canvas = (await client.get(f"/api/v1/sessions/{session_id}")).json()["canvas"]
    pairs = {(e["source"], e["target"]) for e in canvas["edges"]}
    agents = [n["id"] for n in canvas["nodes"] if n["type"] == "agent"]

    # Both agents hang off the idea, and neither points at the other.
    assert all(("idea", a) in pairs for a in agents)
    assert (agents[0], agents[1]) not in pairs


async def test_a_relay_session_reloads_as_a_thread(client):
    session_id = await _run(client, "relay")

    canvas = (await client.get(f"/api/v1/sessions/{session_id}")).json()["canvas"]
    pairs = {(e["source"], e["target"]) for e in canvas["edges"]}
    agents = [n["id"] for n in canvas["nodes"] if n["type"] == "agent"]

    assert (agents[0], agents[1]) in pairs


async def test_the_live_canvas_of_a_swarm_is_already_a_mesh(client):
    """Not only on reload: the events sent during the debate carry it too."""
    team = await _team(client, "swarm")
    session_id = (
        await client.post("/api/v1/sessions", json={"idea": "x", "team_id": team["id"]})
    ).json()["session_id"]

    payloads = await _graph_payloads(client, session_id)

    last = payloads[-1]
    pairs = {(e["source"], e["target"]) for e in last["edges"]}
    agents = [n["id"] for n in last["nodes"] if n["type"] == "agent"]
    assert all(("idea", a) in pairs for a in agents)


async def _graph_payloads(client, session_id) -> list[dict]:
    import json

    payloads: list[dict] = []
    event = None
    async with client.stream("GET", f"/api/v1/sessions/{session_id}/stream") as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event == "graph":
                payloads.append(json.loads(line.split(":", 1)[1]))
    return payloads
