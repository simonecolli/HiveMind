"""What an agent actually sees when it takes its turn."""

from src.graph.state import initial_state, render_context
from src.models import Turn


def _turn(**kwargs) -> Turn:
    base = dict(
        id=1,
        agent_id=1,
        agent_name="Advocate",
        agent_position=0,
        pass_no=1,
        round=1,
        seq=0,
        kind="agent",
        title=None,
        text="the costs are underestimated",
    )
    return Turn(**{**base, **kwargs})


def test_the_first_agent_of_the_first_pass_sees_only_the_idea():
    context = render_context(initial_state("s1", "an installation", 2))

    assert "an installation" in context
    assert "first to speak" in context


def test_the_context_carries_the_turns_of_the_current_pass():
    state = initial_state("s1", "an installation", 2)
    state["turns"] = [_turn()]

    context = render_context(state)

    assert "the costs are underestimated" in context


def test_a_follow_up_shows_the_message_instead_of_the_original_idea():
    state = initial_state(
        "s1", "an installation", 1, prompt="and if we did it outdoors?", pass_no=2
    )

    context = render_context(state)

    assert "and if we did it outdoors?" in context


def test_a_follow_up_still_shows_the_original_idea_for_reference():
    state = initial_state("s1", "an installation", 1, prompt="outdoors?", pass_no=2)

    assert "an installation" in render_context(state)


def test_the_previous_syntheses_reach_the_agents_in_order():
    state = initial_state(
        "s1",
        "an installation",
        1,
        prompt="outdoors?",
        pass_no=3,
        previous_syntheses=["first summary", "second summary"],
    )

    context = render_context(state)

    assert context.index("first summary") < context.index("second summary")


def test_the_previous_transcript_is_not_carried_over():
    """Only the syntheses travel: full transcripts would drown a local model."""
    state = initial_state(
        "s1",
        "an installation",
        1,
        prompt="outdoors?",
        pass_no=2,
        previous_syntheses=["first summary"],
    )

    assert "a very long earlier speech" not in render_context(state)
