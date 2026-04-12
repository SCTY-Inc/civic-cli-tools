"""Tests for CLI scope parsing and validation."""

import cli
import pytest
from agents import ResearchOutput
from cli import check_env, parse_compare, parse_scope, run_pipeline
from tools.models import Finding, ResearchResults


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

    def test_special_targets_are_case_insensitive(self):
        assert parse_compare("FEDERAL,News,ca") == ["federal", "news", "CA"]

    def test_invalid_target(self):
        with pytest.raises(ValueError, match="Invalid compare target"):
            parse_compare("federal,INVALID")

    def test_states_only(self):
        assert parse_compare("CA,NY,TX") == ["CA", "NY", "TX"]

    def test_requires_at_least_two_targets(self):
        with pytest.raises(ValueError, match="at least two targets"):
            parse_compare("CA")


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

    def test_compare_uses_compare_targets_not_default_scope(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "x")
        monkeypatch.setenv("EXA_API_KEY", "x")
        monkeypatch.delenv("CONGRESS_GOV_API_KEY", raising=False)
        monkeypatch.delenv("OPENSTATES_API_KEY", raising=False)
        assert check_env({"type": "all", "states": []}, ["CA", "NY"]) == ["OPENSTATES_API_KEY"]
        assert check_env({"type": "all", "states": []}, ["federal", "news"]) == ["CONGRESS_GOV_API_KEY"]

    def test_all_keys_present(self, monkeypatch):
        for key in ["GOOGLE_API_KEY", "EXA_API_KEY", "CONGRESS_GOV_API_KEY", "OPENSTATES_API_KEY"]:
            monkeypatch.setenv(key, "x")
        missing = check_env({"type": "all", "states": []})
        assert missing == []


class TestRunPipeline:
    def test_appendix_is_added_after_review(self, monkeypatch, tmp_path):
        for key in ["GOOGLE_API_KEY", "EXA_API_KEY", "CONGRESS_GOV_API_KEY", "OPENSTATES_API_KEY"]:
            monkeypatch.setenv(key, "x")

        results = ResearchResults(findings=[Finding(title="Source", snippet="S", url="http://x", source_type="WEB")])
        results.record_tool_call("web_search")
        output = ResearchOutput(text="synthesis", results=results, scope_label="all")
        saved = {}

        monkeypatch.setattr(cli, "research", lambda *args, **kwargs: output)
        monkeypatch.setattr(cli, "write_brief", lambda *args, **kwargs: "DRAFT")
        monkeypatch.setattr(cli, "review", lambda draft: f"REVIEWED::{draft}")
        monkeypatch.setattr(cli, "save_report", lambda content, path: saved.update(content=content, path=path))

        code = run_pipeline("topic", output_path=str(tmp_path / "report.md"))
        assert code == 0
        assert saved["content"].startswith("REVIEWED::DRAFT\n\n---\n\n## Appendix: Source Data")
