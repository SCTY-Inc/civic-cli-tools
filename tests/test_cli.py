"""Tests for CLI scope parsing and validation."""

import pytest
from cli import parse_scope, parse_compare, check_env


class TestParseScope:
    def test_federal(self):
        assert parse_scope("federal") == {"type": "federal", "states": []}

    def test_all(self):
        assert parse_scope("all") == {"type": "all", "states": []}

    def test_single_state(self):
        assert parse_scope("state:CA") == {"type": "state", "states": ["CA"]}

    def test_multiple_states(self):
        result = parse_scope("state:CA,NY,TX")
        assert result["type"] == "state"
        assert set(result["states"]) == {"CA", "NY", "TX"}

    def test_lowercase_states(self):
        result = parse_scope("state:ca,ny")
        assert result["states"] == ["CA", "NY"]

    def test_invalid_state(self):
        with pytest.raises(ValueError, match="Invalid state codes"):
            parse_scope("state:ZZ")

    def test_invalid_scope(self):
        with pytest.raises(ValueError, match="Invalid scope"):
            parse_scope("bogus")

    def test_dc_and_pr(self):
        assert parse_scope("state:DC")["states"] == ["DC"]
        assert parse_scope("state:PR")["states"] == ["PR"]


class TestParseCompare:
    def test_federal_and_states(self):
        assert parse_compare("federal,CA,NY") == ["federal", "CA", "NY"]

    def test_special_targets(self):
        assert parse_compare("federal,news,policy") == ["federal", "news", "policy"]

    def test_invalid_target(self):
        with pytest.raises(ValueError, match="Invalid compare target"):
            parse_compare("federal,INVALID")

    def test_states_only(self):
        assert parse_compare("CA,NY,TX") == ["CA", "NY", "TX"]


class TestCheckEnv:
    def test_always_requires_google_and_exa(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("EXA_API_KEY", raising=False)
        missing = check_env({"type": "all", "states": []})
        assert "GOOGLE_API_KEY" in missing
        assert "EXA_API_KEY" in missing

    def test_federal_requires_congress_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "x")
        monkeypatch.setenv("EXA_API_KEY", "x")
        monkeypatch.delenv("CONGRESS_GOV_API_KEY", raising=False)
        missing = check_env({"type": "federal", "states": []})
        assert "CONGRESS_GOV_API_KEY" in missing

    def test_state_requires_openstates_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "x")
        monkeypatch.setenv("EXA_API_KEY", "x")
        monkeypatch.delenv("OPENSTATES_API_KEY", raising=False)
        missing = check_env({"type": "state", "states": ["CA"]})
        assert "OPENSTATES_API_KEY" in missing

    def test_all_keys_present(self, monkeypatch):
        for key in ["GOOGLE_API_KEY", "EXA_API_KEY", "CONGRESS_GOV_API_KEY", "OPENSTATES_API_KEY"]:
            monkeypatch.setenv(key, "x")
        missing = check_env({"type": "all", "states": []})
        assert missing == []
