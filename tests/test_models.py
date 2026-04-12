"""Tests for data models and confidence scoring."""

import pytest
from tools.models import Finding, ResearchResults


class TestFinding:
    def test_defaults(self):
        f = Finding(title="T", snippet="S", url="U")
        assert f.date == ""
        assert f.source_type == ""
        assert f.citations == 0
        assert f.is_error is False

    def test_to_dict(self):
        f = Finding(title="T", snippet="S", url="U", date="2025", source_type="WEB", citations=5)
        d = f.to_dict()
        assert d == {
            "title": "T", "snippet": "S", "url": "U",
            "date": "2025", "source_type": "WEB", "citations": 5, "is_error": False,
        }


class TestResearchResults:
    def test_add(self):
        r = ResearchResults()
        f = Finding(title="T", snippet="S", url="U", source_type="WEB")
        r.add(f)
        r.record_tool_call("web_search")
        assert len(r.findings) == 1
        assert r.tool_usage["web_search"] == 1

    def test_tool_calls_are_not_counted_per_finding(self):
        r = ResearchResults()
        r.record_tool_call("web_search")
        r.extend([Finding(title="T", snippet="S", url="U", source_type="WEB") for _ in range(3)])
        assert r.tool_usage["web_search"] == 1

    def test_confidence_no_findings(self):
        r = ResearchResults()
        level, _ = r.confidence_score()
        assert level == "LOW"

    def test_confidence_high(self):
        r = ResearchResults()
        sources = ["WEB", "ACADEMIC", "CONGRESS", "FED_REGISTER", "COURT"]
        for source in sources:
            r.add(Finding(title="T", snippet="S", url="U", date="2026", source_type=source, citations=10))
        level, _ = r.confidence_score()
        assert level == "HIGH"

    def test_confidence_low_single_source(self):
        r = ResearchResults()
        r.add(Finding(title="T", snippet="S", url="U", date="2010", source_type="WEB"))
        level, _ = r.confidence_score()
        assert level == "LOW"

    def test_recent_uncited_four_sources_are_not_high(self):
        r = ResearchResults()
        for source in ["WEB", "ACADEMIC", "CENSUS", "CONGRESS"]:
            r.add(Finding(title="T", snippet="S", url="U", date="2026", source_type=source))
        level, _ = r.confidence_score()
        assert level == "MEDIUM"

    def test_errors_are_excluded_from_confidence(self):
        r = ResearchResults(findings=[Finding(title="Error", snippet="boom", url="", source_type="CENSUS", is_error=True)])
        assert r.confidence_score() == ("LOW", "No successful findings")

    def test_to_dict(self):
        r = ResearchResults()
        r.add(Finding(title="T", snippet="S", url="U", source_type="WEB"))
        r.add(Finding(title="Error", snippet="boom", url="", source_type="WEB", is_error=True))
        r.record_tool_call("web_search")
        d = r.to_dict()
        assert "confidence" in d
        assert "findings" in d
        assert "tool_usage" in d
        assert "errors" in d
        assert len(d["findings"]) == 1

    def test_to_text(self):
        r = ResearchResults()
        r.add(Finding(title="Title", snippet="Snippet", url="http://x", source_type="WEB"))
        text = r.to_text()
        assert "Title" in text
        assert "WEB" in text

    def test_to_appendix(self):
        r = ResearchResults()
        r.add(Finding(title="Title", snippet="S", url="http://x", date="2025", source_type="WEB"))
        r.add(Finding(title="Error", snippet="boom", url="", source_type="CENSUS", is_error=True))
        appendix = r.to_appendix()
        assert "Appendix" in appendix
        assert "Confidence" in appendix
        assert "http://x" in appendix
        assert "Tool errors" in appendix
