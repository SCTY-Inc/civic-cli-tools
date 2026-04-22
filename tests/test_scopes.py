"""Tests for shared scope helpers."""

from scopes import compare_target_scope, scope_label


def test_compare_target_scope_for_special_target():
    assert compare_target_scope("policy") == {"type": "policy", "states": []}


def test_scope_label_for_state_scope():
    assert scope_label({"type": "state", "states": ["CA", "NY"]}) == "state:CA,NY"
