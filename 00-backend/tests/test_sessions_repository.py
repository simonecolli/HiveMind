from src.db.sessions import SessionsRepository
from src.db.turns import SqliteTurnRecorder
from src.models import SessionCreate


def _new(**kwargs) -> SessionCreate:
    base = dict(
        idea="a photographic installation",
        team_id=1,
        team_name="Board",
        max_rounds=2,
        team_snapshot={"name": "Board", "agents": [{"name": "Advocate"}]},
    )
    return SessionCreate(**{**base, **kwargs})


async def _turn(recorder, session_id, **kwargs):
    """The recorder allocates `seq` itself, in write order."""
    fields = dict(
        session_id=session_id,
        agent_id=1,
        agent_name="Advocate",
        agent_position=0,
        pass_no=1,
        round=1,
        kind="agent",
    )
    return await recorder.start(**{**fields, **kwargs})


async def test_create_assigns_an_id_and_the_initial_status(conn):
    repo = SessionsRepository(conn)

    session = await repo.create(_new())

    assert session.id
    assert session.status == "running"
    assert session.finished_at is None


async def test_the_team_snapshot_survives_the_round_trip(conn):
    repo = SessionsRepository(conn)

    created = await repo.create(_new())
    fetched = await repo.get(created.id)

    assert fetched.team_snapshot == {"name": "Board", "agents": [{"name": "Advocate"}]}


async def test_list_puts_recent_sessions_first(conn):
    repo = SessionsRepository(conn)
    first = await repo.create(_new(idea="first"))
    second = await repo.create(_new(idea="second"))

    sessions = await repo.list()

    assert [s.id for s in sessions] == [second.id, first.id]


async def test_finish_records_the_status_and_the_end_time(conn):
    repo = SessionsRepository(conn)
    session = await repo.create(_new())

    await repo.finish(session.id, status="done")

    updated = await repo.get(session.id)
    assert updated.status == "done"
    assert updated.finished_at is not None


async def test_finish_with_an_error_keeps_the_message(conn):
    repo = SessionsRepository(conn)
    session = await repo.create(_new())

    await repo.finish(session.id, status="error", error="Ollama unreachable")

    updated = await repo.get(session.id)
    assert (updated.status, updated.error) == ("error", "Ollama unreachable")


async def test_the_recorder_creates_the_row_before_the_text(conn):
    sessions = SessionsRepository(conn)
    recorder = SqliteTurnRecorder(conn)
    session = await sessions.create(_new())

    started = await _turn(recorder, session.id)

    turns = await recorder.list_by_session(session.id)
    assert [t.id for t in turns] == [started.id]
    assert turns[0].text == ""


async def test_finish_completes_text_and_title(conn):
    sessions = SessionsRepository(conn)
    recorder = SqliteTurnRecorder(conn)
    session = await sessions.create(_new())
    started = await _turn(recorder, session.id)

    await recorder.finish(started.id, "the full text", "a title")

    turn = (await recorder.list_by_session(session.id))[0]
    assert (turn.text, turn.title) == ("the full text", "a title")


async def test_the_recorder_hands_out_seq_in_write_order(conn):
    sessions = SessionsRepository(conn)
    recorder = SqliteTurnRecorder(conn)
    session = await sessions.create(_new())
    await _turn(recorder, session.id, agent_name="First")
    await _turn(recorder, session.id, agent_name="Second")

    turns = await recorder.list_by_session(session.id)

    assert [(t.agent_name, t.seq) for t in turns] == [("First", 0), ("Second", 1)]


async def test_deleting_the_session_deletes_its_turns(conn):
    sessions = SessionsRepository(conn)
    recorder = SqliteTurnRecorder(conn)
    session = await sessions.create(_new())
    await _turn(recorder, session.id)

    await sessions.delete(session.id)

    assert await recorder.list_by_session(session.id) == []


async def test_deleting_the_team_leaves_past_sessions_alone(conn):
    from src.db.teams import TeamsRepository
    from src.models import TeamCreate

    teams = TeamsRepository(conn)
    sessions = SessionsRepository(conn)
    team = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))
    session = await sessions.create(_new(team_id=team.id))

    await teams.delete(team.id)

    survived = await sessions.get(session.id)
    assert survived is not None
    assert survived.team_name == "Board"
