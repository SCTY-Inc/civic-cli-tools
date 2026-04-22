"""Atomic per-finding signal output.

Used by `civic signals` for downstream consumers (web-pulse, etc.) that want
individual policy items rather than a Gemini-synthesized markdown brief.
Each signal is a stable JSON object — same URL across runs produces the
same `id`, so consumers can dedupe idempotently.

Schema (v1):

{
  "schema_version": 1,
  "topic": "...",
  "preset": "caregiver-federal" | null,
  "scope": "federal" | "federal + state" | "state:CA" | "compare:...",
  "fetched_at": "2026-04-22T09:15:00Z",
  "counts": { "signals": 12, "by_source_type": { "CONGRESS": 4, ... } },
  "signals": [
    {
      "id": "congress-...-slug",
      "source_tool": "congress_search",
      "source_type": "CONGRESS",
      "source_system": "congress.gov",
      "title": "...",
      "url": "...",
      "summary": "...",
      "published_at": "2024-04-12",
      "identifier": "HR 2406",          # optional, per source type
      "status": "...",                  # optional, per source type
      "congress": "118",                # optional, Congress only
      "jurisdiction": "federal" | "state:CA",  # optional
      "citations": 0                    # ACADEMIC only
    }
  ]
}
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from tools.models import Finding, ResearchResults

SCHEMA_VERSION = 1

SOURCE_SYSTEMS = {
    "WEB": "web",
    "ACADEMIC": "semanticscholar.org",
    "CONGRESS": "congress.gov",
    "FED_REGISTER": "federalregister.gov",
    "REGULATIONS": "regulations.gov",
    "COURT": "courtlistener.com",
    "CENSUS": "data.census.gov",
    "STATE_LEG": "openstates.org",
    "LEGISCAN": "legiscan.com",
}

SOURCE_TO_TOOL = {
    "WEB": "web_search",
    "ACADEMIC": "academic_search",
    "CONGRESS": "congress_search",
    "FED_REGISTER": "federal_register_search",
    "REGULATIONS": "regulations_search",
    "COURT": "court_search",
    "CENSUS": "census_search",
    "STATE_LEG": "state_legislation_search",
    "LEGISCAN": "state_legislation_search",
}


def _extract_congress(title: str, snippet: str) -> dict:
    """CongressSearch formats: title='HR2406: Act name', snippet='Congress N | Status: X'."""
    out: dict = {"jurisdiction": "federal"}
    m = re.match(r"^([A-Z]+)\s*(\d+):\s*(.*)$", title or "")
    if m:
        out["identifier"] = f"{m.group(1)} {m.group(2)}"
        out["title"] = m.group(3).strip() or title
    status_m = re.search(r"Status:\s*(.+?)(?:\s*\||$)", snippet or "")
    if status_m:
        out["status"] = status_m.group(1).strip()
    congress_m = re.search(r"Congress\s+(\d+)", snippet or "")
    if congress_m:
        out["congress"] = congress_m.group(1)
    return out


def _extract_fed_register(url: str) -> dict:
    """FR URLs: /documents/YYYY/MM/DD/DOCUMENT-ID/slug."""
    out: dict = {"jurisdiction": "federal"}
    m = re.search(r"/documents/\d{4}/\d{2}/\d{2}/([^/]+)", url or "")
    if m:
        out["identifier"] = m.group(1)
    return out


def _extract_regulations(url: str) -> dict:
    out: dict = {"jurisdiction": "federal"}
    m = re.search(r"/document/([^/?#]+)", url or "")
    if m:
        out["identifier"] = m.group(1)
    return out


def _extract_state_leg(_title: str, _snippet: str, url: str) -> dict:
    """OpenStates URLs: /{ST}/bills/{session}/{bill-id}/."""
    out: dict = {}
    m = re.search(r"/([A-Z]{2})/bills?/[^/]+/([^/?#]+)", url or "")
    if m:
        out["jurisdiction"] = f"state:{m.group(1)}"
        out["identifier"] = m.group(2)
    else:
        out["jurisdiction"] = "state"
    return out


def _extract_legiscan(url: str) -> dict:
    out: dict = {}
    m = re.search(r"legiscan\.com/([A-Z]{2})/bill/([^/?#]+)", url or "")
    if m:
        out["jurisdiction"] = f"state:{m.group(1)}"
        out["identifier"] = m.group(2)
    else:
        out["jurisdiction"] = "state"
    return out


EXTRACTORS = {
    "CONGRESS": lambda f: _extract_congress(f.title, f.snippet),
    "FED_REGISTER": lambda f: _extract_fed_register(f.url),
    "REGULATIONS": lambda f: _extract_regulations(f.url),
    "STATE_LEG": lambda f: _extract_state_leg(f.title, f.snippet, f.url),
    "LEGISCAN": lambda f: _extract_legiscan(f.url),
}


def _stable_id(source_type: str, url: str, title: str) -> str:
    """Deterministic ID — URL-keyed where available, title fallback."""
    base = url or title or ""
    base = re.sub(r"^https?://(www\.)?", "", base.lower())
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return f"{source_type.lower()}-{base}"[:150]


def signal_from_finding(finding: Finding) -> dict:
    extracted = EXTRACTORS.get(finding.source_type, lambda _f: {})(finding)
    signal = {
        "id": _stable_id(finding.source_type, finding.url, finding.title),
        "source_tool": SOURCE_TO_TOOL.get(finding.source_type, "unknown"),
        "source_type": finding.source_type,
        "source_system": SOURCE_SYSTEMS.get(
            finding.source_type, finding.source_type.lower()
        ),
        "title": extracted.get("title") or finding.title,
        "url": finding.url,
        "summary": finding.snippet,
        "published_at": finding.date,
    }
    if finding.citations:
        signal["citations"] = finding.citations
    for key in ("identifier", "status", "congress", "jurisdiction"):
        val = extracted.get(key)
        if val:
            signal[key] = val
    return signal


def emit_signals(
    topic: str,
    preset: str | None,
    scope_label: str,
    results: ResearchResults,
) -> str:
    """Build the atomic signals JSON envelope. Dedupes by URL."""
    seen: set[str] = set()
    signals: list[dict] = []
    for f in results.findings:
        key = f.url or f.title
        if not key or key in seen:
            continue
        seen.add(key)
        signals.append(signal_from_finding(f))

    envelope = {
        "schema_version": SCHEMA_VERSION,
        "topic": topic,
        "preset": preset,
        "scope": scope_label,
        "fetched_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "counts": {
            "signals": len(signals),
            "by_source_type": _counts_by_source(signals),
        },
        "signals": signals,
    }
    return json.dumps(envelope, indent=2, ensure_ascii=False)


def _counts_by_source(signals: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in signals:
        out[s["source_type"]] = out.get(s["source_type"], 0) + 1
    return out
