"""What the dashboard answers: can I start, and what do I depend on.

Deliberately not a page of counters. With a handful of debates on the clock any
usage chart is an empty room; what is worth knowing on opening the app is which
teams would actually run right now, and which model would take the most of them
down with it if it went missing.
"""

from tests.support import StubEngines


async def _team(client, name, *, agents, provider="ollama", model="m"):
    team = (
        await client.post("/api/v1/teams", json={"name": name, "synthesis_prompt": "x"})
    ).json()
    for agent_name in agents:
        await client.post(
            f"/api/v1/teams/{team['id']}/agents",
            json={
                "name": agent_name,
                "system_prompt": "speak",
                "model": model,
                "provider": provider,
            },
        )
    return team["id"]


async def _dashboard(client) -> dict:
    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200
    return response.json()


async def test_a_team_whose_models_are_all_present_is_ready(client):
    await _team(client, "Board", agents=["A", "B"])

    board = (await _dashboard(client))["teams"][0]

    assert board["ready"] is True
    assert board["blockers"] == []
    assert board["agents"] == 2


async def test_a_team_is_blocked_when_its_engine_is_down(app_deps, client):
    app_deps.engines = StubEngines(
        [{"provider": "ollama", "label": "Ollama", "available": False, "models": []}]
    )
    await _team(client, "Board", agents=["A"])

    board = (await _dashboard(client))["teams"][0]

    assert board["ready"] is False
    assert "Ollama" in board["blockers"][0]


async def test_a_team_is_blocked_when_a_model_is_missing(client):
    await _team(client, "Board", agents=["A"], model="not-installed")

    board = (await _dashboard(client))["teams"][0]

    assert board["ready"] is False
    assert "not-installed" in board["blockers"][0]


async def test_every_problem_is_listed_not_only_the_first(client):
    """The session route stops at the first; here you want the whole bill."""
    team = (
        await client.post("/api/v1/teams", json={"name": "Board", "synthesis_prompt": "x"})
    ).json()
    for name, model in [("A", "missing-one"), ("B", "missing-two")]:
        await client.post(
            f"/api/v1/teams/{team['id']}/agents",
            json={"name": name, "system_prompt": "x", "model": model},
        )

    board = (await _dashboard(client))["teams"][0]

    assert len(board["blockers"]) == 2


async def test_a_team_with_no_enabled_agents_cannot_run_either(client):
    await client.post("/api/v1/teams", json={"name": "Empty", "synthesis_prompt": "x"})

    board = (await _dashboard(client))["teams"][0]

    assert board["ready"] is False
    assert board["blockers"] != []


async def test_the_models_are_ranked_by_how_much_depends_on_them(client):
    await _team(client, "Big", agents=["A", "B", "C"], model="m")
    await _team(client, "Small", agents=["D"], model="other")

    models = (await _dashboard(client))["models"]

    assert [m["model"] for m in models] == ["m", "other"]
    assert models[0]["agents"] == 3
    assert models[0]["teams"] == 1


async def test_a_model_used_by_several_teams_counts_them(client):
    await _team(client, "One", agents=["A"], model="m")
    await _team(client, "Two", agents=["B"], model="m")

    models = (await _dashboard(client))["models"]

    assert models[0]["teams"] == 2
    assert models[0]["agents"] == 2


async def test_a_model_carries_its_engine_and_whether_it_is_installed(client):
    await _team(client, "Board", agents=["A"], model="m")
    await _team(client, "Gone", agents=["B"], model="not-installed")

    models = {m["model"]: m for m in (await _dashboard(client))["models"]}

    assert models["m"]["label"] == "Ollama"
    assert models["m"]["installed"] is True
    assert models["not-installed"]["installed"] is False


async def test_the_engines_are_reported_as_they_are(client):
    engines = (await _dashboard(client))["engines"]

    assert engines[0]["provider"] == "ollama"
    assert engines[0]["available"] is True


async def test_an_empty_installation_answers_without_falling_over(client):
    dashboard = await _dashboard(client)

    assert dashboard["teams"] == []
    assert dashboard["models"] == []


# Three agents on one dead engine is one problem, not three. Repeating the same
# sentence per agent buries the single thing you have to go and fix.


async def test_agents_sharing_a_dead_engine_report_it_once(client, app_deps):
    from tests.support import StubEngines

    app_deps.engines = StubEngines(
        [{"provider": "ollama", "label": "Ollama", "available": False, "models": []}]
    )
    await _team(client, "Board", agents=["A", "B", "C"])

    board = (await _dashboard(client))["teams"][0]

    assert len(board["blockers"]) == 1
    assert "3 agents" in board["blockers"][0]
    assert "Ollama" in board["blockers"][0]


async def test_agents_sharing_a_missing_model_report_it_once(client):
    await _team(client, "Board", agents=["A", "B"], model="not-installed")

    board = (await _dashboard(client))["teams"][0]

    assert len(board["blockers"]) == 1
    assert "not-installed" in board["blockers"][0]
    assert "2 agents" in board["blockers"][0]


async def test_two_different_problems_stay_two_lines(client):
    team = (
        await client.post("/api/v1/teams", json={"name": "Mixed", "synthesis_prompt": "x"})
    ).json()
    for name, model, provider in [
        ("A", "not-installed", "ollama"),
        ("B", "also-missing", "ollama"),
    ]:
        await client.post(
            f"/api/v1/teams/{team['id']}/agents",
            json={"name": name, "system_prompt": "x", "model": model, "provider": provider},
        )

    board = (await _dashboard(client))["teams"][0]

    assert len(board["blockers"]) == 2


async def test_a_single_agent_is_not_pluralised(client):
    await _team(client, "Board", agents=["Solo"], model="not-installed")

    board = (await _dashboard(client))["teams"][0]

    assert "1 agent " in board["blockers"][0] or "1 agent," in board["blockers"][0]
    assert "1 agents" not in board["blockers"][0]


# "Can I start" is a shortlist, not a directory: it shows the teams you actually
# reach for. Ordering by use needs the count, so the endpoint carries it.


async def _run_session(client, team_id: int) -> str:
    from tests.support import collect_events

    session_id = (
        await client.post("/api/v1/sessions", json={"idea": "an idea", "team_id": team_id})
    ).json()["session_id"]
    await collect_events(client, session_id)
    return session_id


async def test_a_team_that_never_ran_counts_zero(client):
    await _team(client, "Board", agents=["A"])

    assert (await _dashboard(client))["teams"][0]["debates"] == 0


async def test_each_debate_counts_once(client):
    board = await _team(client, "Board", agents=["A"])
    await _run_session(client, board)
    await _run_session(client, board)

    assert (await _dashboard(client))["teams"][0]["debates"] == 2


async def test_the_most_used_team_comes_first(client):
    """Named so that alphabetical order would give the opposite answer."""
    await _team(client, "Alpha", agents=["A"])
    busy = await _team(client, "Zebra", agents=["B"])
    await _run_session(client, busy)

    teams = (await _dashboard(client))["teams"]

    assert [t["name"] for t in teams] == ["Zebra", "Alpha"]


async def test_teams_never_used_keep_a_stable_order(client):
    """All zeroes on a fresh install, so name decides rather than chance."""
    await _team(client, "Zebra", agents=["A"])
    await _team(client, "Alpha", agents=["B"])

    assert [t["name"] for t in (await _dashboard(client))["teams"]] == ["Alpha", "Zebra"]


async def test_a_team_handed_a_session_counts_it_too(client):
    """Arguing a pass is using the team, even if it did not open the debate."""
    opener = await _team(client, "Opener", agents=["A"])
    taker = await _team(client, "Taker", agents=["B"])
    session_id = await _run_session(client, opener)

    from tests.support import collect_events

    await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"text": "over to you", "team_id": taker},
    )
    await collect_events(client, session_id)

    counts = {t["name"]: t["debates"] for t in (await _dashboard(client))["teams"]}
    assert counts["Taker"] == 1
    assert counts["Opener"] == 1
