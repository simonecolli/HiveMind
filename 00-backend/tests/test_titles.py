"""Short titles for a turn."""

import pytest

from src.llm.titles import clean_title, make_titler
from tests.support import echo_llm_factory


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Costs underestimated", "Costs underestimated"),
        ('"Costs underestimated"', "Costs underestimated"),
        ("«Costs underestimated»", "Costs underestimated"),
        ("  Costs underestimated\n\n", "Costs underestimated"),
        ("Title: Costs underestimated", "Costs underestimated"),
        ("First line\nsecond line", "First line"),
        ("Costs underestimated.", "Costs underestimated"),
    ],
)
def test_clean_title_normalises_what_the_model_returns(raw, expected):
    assert clean_title(raw) == expected


def test_clean_title_discards_an_empty_reply():
    assert clean_title("   \n ") is None


def test_clean_title_truncates_a_rambling_reply():
    long_reply = " ".join(["word"] * 40)

    title = clean_title(long_reply)

    assert len(title) <= 80
    assert title.endswith("…")


async def test_the_titler_cleans_up_the_model_reply():
    titler = make_titler(echo_llm_factory({"m": '"Costs underestimated"'}), "ollama", "m")

    assert await titler("a long piece of text") == "Costs underestimated"


async def test_the_titler_skips_the_model_on_empty_text():
    def explode(provider, model):
        raise AssertionError("the model should not have been called")

    titler = make_titler(explode, "ollama", "m")

    assert await titler("   ") is None
