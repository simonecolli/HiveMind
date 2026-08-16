import httpx

from src.app import create_app
from tests.support import StubEngines, collect_events


async def _team_with_agent(client, name="Board"):
    team = (
        await client.post(
            "/api/v1/teams", json={"name": name, "synthesis_prompt": "Synthesise."}
        )
    ).json()
    await client.post(
        f"/api/v1/teams/{team['id']}/agents",
        json={"name": "Advocate", "system_prompt": "push back", "model": "m"},
    )
    return team


async def test_health_responds(client):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200


async def test_models_exposes_the_catalogue_of_each_engine(client):
    catalogue = (await client.get("/api/v1/models")).json()

    assert catalogue[0]["provider"] == "ollama"
    assert catalogue[0]["models"] == ["m"]


async def test_creating_a_team_returns_201_and_the_team(client):
    response = await client.post(
        "/api/v1/teams", json={"name": "Board", "synthesis_prompt": "Synthesise."}
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Board"
    assert response.json()["default_max_rounds"] == 2


async def test_a_duplicate_team_name_gives_409(client):
    await client.post("/api/v1/teams", json={"name": "Board", "synthesis_prompt": "x"})

    response = await client.post(
        "/api/v1/teams", json={"name": "Board", "synthesis_prompt": "y"}
    )

    assert response.status_code == 409


async def test_the_team_detail_includes_its_agents(client):
    team = await _team_with_agent(client)

    response = await client.get(f"/api/v1/teams/{team['id']}")

    assert [a["name"] for a in response.json()["agents"]] == ["Advocate"]


async def test_an_unknown_team_gives_404(client):
    assert (await client.get("/api/v1/teams/999")).status_code == 404


async def test_duplicating_a_team_creates_a_copy(client):
    team = await _team_with_agent(client)

    response = await client.post(f"/api/v1/teams/{team['id']}/duplicate")

    assert response.status_code == 201
    copy = response.json()
    assert copy["name"] == "Board (copy)"
    detail = (await client.get(f"/api/v1/teams/{copy['id']}")).json()
    assert [a["name"] for a in detail["agents"]] == ["Advocate"]


async def test_deleting_a_team_returns_204(client):
    team = await _team_with_agent(client)

    response = await client.delete(f"/api/v1/teams/{team['id']}")

    assert response.status_code == 204
    assert (await client.get(f"/api/v1/teams/{team['id']}")).status_code == 404


async def test_reordering_agents_updates_their_positions(client):
    team = await _team_with_agent(client)
    second = (
        await client.post(
            f"/api/v1/teams/{team['id']}/agents",
            json={"name": "Creative", "system_prompt": "expand", "model": "m"},
        )
    ).json()
    first = (await client.get(f"/api/v1/teams/{team['id']}")).json()["agents"][0]

    response = await client.post(
        f"/api/v1/teams/{team['id']}/agents/reorder",
        json={"ordered_ids": [second["id"], first["id"]]},
    )

    assert response.status_code == 200
    assert [a["name"] for a in response.json()] == ["Creative", "Advocate"]


async def test_an_inconsistent_reorder_gives_422(client):
    team = await _team_with_agent(client)

    response = await client.post(
        f"/api/v1/teams/{team['id']}/agents/reorder", json={"ordered_ids": [9999]}
    )

    assert response.status_code == 422


async def test_editing_an_agent_updates_its_prompt(client):
    team = await _team_with_agent(client)
    agent_id = (await client.get(f"/api/v1/teams/{team['id']}")).json()["agents"][0]["id"]

    response = await client.patch(
        f"/api/v1/agents/{agent_id}", json={"system_prompt": "push back harder"}
    )

    assert response.json()["system_prompt"] == "push back harder"


async def test_deleting_an_agent_removes_it_from_the_team(client):
    team = await _team_with_agent(client)
    agent_id = (await client.get(f"/api/v1/teams/{team['id']}")).json()["agents"][0]["id"]

    await client.delete(f"/api/v1/agents/{agent_id}")

    assert (await client.get(f"/api/v1/teams/{team['id']}")).json()["agents"] == []


async def test_exporting_a_team_returns_a_portable_payload(client):
    team = await _team_with_agent(client)

    payload = (await client.get(f"/api/v1/teams/{team['id']}/export")).json()

    assert payload["name"] == "Board"
    assert [a["name"] for a in payload["agents"]] == ["Advocate"]
    assert "id" not in payload


async def test_exporting_an_unknown_team_gives_404(client):
    assert (await client.get("/api/v1/teams/999/export")).status_code == 404


async def test_importing_a_team_returns_201_and_the_team(client):
    response = await client.post(
        "/api/v1/teams/import",
        json={
            "name": "Imported",
            "synthesis_prompt": "Sum it up.",
            "agents": [{"name": "Creative", "system_prompt": "expand", "model": "m"}],
        },
    )

    assert response.status_code == 201
    team_id = response.json()["id"]
    detail = (await client.get(f"/api/v1/teams/{team_id}")).json()
    assert [a["name"] for a in detail["agents"]] == ["Creative"]


async def test_importing_over_an_existing_name_renames_the_team(client):
    await _team_with_agent(client)

    response = await client.post(
        "/api/v1/teams/import",
        json={"name": "Board", "synthesis_prompt": "x", "agents": []},
    )

    assert response.json()["name"] == "Board (copy)"


async def test_importing_a_malformed_payload_gives_422(client):
    response = await client.post("/api/v1/teams/import", json={"agents": []})

    assert response.status_code == 422


async def test_a_team_exported_then_imported_round_trips(client):
    team = await _team_with_agent(client)
    payload = (await client.get(f"/api/v1/teams/{team['id']}/export")).json()

    imported = (await client.post("/api/v1/teams/import", json=payload)).json()

    reexported = (await client.get(f"/api/v1/teams/{imported['id']}/export")).json()
    assert reexported["agents"] == payload["agents"]


async def test_starting_a_session_returns_its_id(client):
    team = await _team_with_agent(client)

    response = await client.post(
        "/api/v1/sessions", json={"idea": "an installation", "team_id": team["id"]}
    )

    assert response.status_code == 201
    assert response.json()["session_id"]


async def test_the_session_inherits_the_rounds_from_the_team(client):
    team = (
        await client.post(
            "/api/v1/teams",
            json={"name": "Panel", "synthesis_prompt": "x", "default_max_rounds": 4},
        )
    ).json()
    await client.post(
        f"/api/v1/teams/{team['id']}/agents",
        json={"name": "Advocate", "system_prompt": "push back", "model": "m"},
    )

    session_id = (
        await client.post("/api/v1/sessions", json={"idea": "x", "team_id": team["id"]})
    ).json()["session_id"]

    assert (await client.get(f"/api/v1/sessions/{session_id}")).json()["max_rounds"] == 4


async def test_a_session_on_an_unknown_team_gives_404(client):
    response = await client.post("/api/v1/sessions", json={"idea": "x", "team_id": 999})

    assert response.status_code == 404


async def test_a_team_with_no_enabled_agents_gives_422(client):
    team = (
        await client.post("/api/v1/teams", json={"name": "Empty", "synthesis_prompt": "x"})
    ).json()

    response = await client.post(
        "/api/v1/sessions", json={"idea": "x", "team_id": team["id"]}
    )

    assert response.status_code == 422


async def test_a_stopped_local_engine_gives_503(app_deps, conn):
    app_deps.engines = StubEngines(
        [{"provider": "ollama", "label": "Ollama", "available": False, "models": []}]
    )
    app = create_app(app_deps, seed=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        team = await _team_with_agent(client)

        response = await client.post(
            "/api/v1/sessions", json={"idea": "x", "team_id": team["id"]}
        )

    assert response.status_code == 503


async def test_the_stream_emits_the_debate_events(client):
    team = await _team_with_agent(client)
    session_id = (
        await client.post("/api/v1/sessions", json={"idea": "an idea", "team_id": team["id"]})
    ).json()["session_id"]

    events = await collect_events(client, session_id)

    assert events[0] == "session.start"
    assert "turn.delta" in events
    assert events[-1] == "session.end"


async def test_the_stream_can_be_replayed_after_the_end(client):
    """The event buffer lets a client attach to a finished debate."""
    team = await _team_with_agent(client)
    session_id = (
        await client.post("/api/v1/sessions", json={"idea": "an idea", "team_id": team["id"]})
    ).json()["session_id"]
    await collect_events(client, session_id)

    second = await collect_events(client, session_id)

    assert second[-1] == "session.end"


async def test_the_session_is_closed_once_the_debate_ends(client):
    team = await _team_with_agent(client)
    session_id = (
        await client.post("/api/v1/sessions", json={"idea": "an idea", "team_id": team["id"]})
    ).json()["session_id"]
    await collect_events(client, session_id)

    detail = (await client.get(f"/api/v1/sessions/{session_id}")).json()

    assert detail["status"] == "done"
    # The default team runs two rounds, so the only agent speaks twice.
    assert [t["agent_name"] for t in detail["turns"]] == [
        "Advocate",
        "Advocate",
        "Synthesis",
    ]
    assert [t["round"] for t in detail["turns"]] == [1, 2, 2]
    assert detail["canvas"]["nodes"][0]["id"] == "idea"


async def test_the_history_lists_the_sessions(client):
    team = await _team_with_agent(client)
    await client.post("/api/v1/sessions", json={"idea": "first", "team_id": team["id"]})

    response = await client.get("/api/v1/sessions")

    assert [s["idea"] for s in response.json()] == ["first"]


async def test_streaming_an_unknown_session_gives_404(client):
    response = await client.get("/api/v1/sessions/does-not-exist/stream")

    assert response.status_code == 404
