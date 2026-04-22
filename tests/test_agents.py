"""Tests for research-scope helpers."""

from agents import _scope_context


def test_scope_context_for_news():
    prompt, label = _scope_context({"type": "news", "states": []})
    assert "current news" in prompt.lower()
    assert label == "news"


def test_scope_context_for_policy():
    prompt, label = _scope_context({"type": "policy", "states": []})
    assert "legislation" in prompt.lower()
    assert label == "policy"
