import pytest

from src.generate import _build_prompt


def test_build_prompt_includes_abstract_and_title():
    docs = [
        {
            "id": "paper-1",
            "title": "Designing AI support for collaborative writing",
            "abstract": "We study how teams use AI tools during drafting and revision.",
        }
    ]

    prompt = _build_prompt(docs)

    assert "paper-1" in prompt
    assert "Designing AI support for collaborative writing" in prompt
    assert "We study how teams use AI tools during drafting and revision." in prompt


def test_build_prompt_raises_when_abstract_missing():
    docs = [
        {
            "id": "paper-2",
            "title": "Missing abstract",
        }
    ]

    with pytest.raises(KeyError, match="missing the required 'abstract' field"):
        _build_prompt(docs)
