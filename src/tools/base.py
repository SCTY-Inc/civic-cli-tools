"""Base tool class and common utilities."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path

import httpx

from .models import Finding, ToolResult

JsonPrimitive = None | bool | int | float | str
JsonValue = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]

RESULTS_LIMIT = 25  # module-level default; override via set_results_limit()
TIMEOUT = 30
MAX_RETRIES = 3
CACHE_TTL = 86400  # 24 hours
CACHE_DIR = Path.home() / ".cache" / "civic"
_DB_PATH = CACHE_DIR / "cache.db"


def set_results_limit(n: int) -> None:
    """Override the per-tool results limit (default 25)."""
    global RESULTS_LIMIT
    if n is not None and n > 0:
        RESULTS_LIMIT = int(n)


def _get_cache_db() -> sqlite3.Connection:
    """Get or create cache database with WAL mode."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(
        "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, ts REAL)"
    )
    return db


def _cache_key(url: str, params: Mapping[str, object] | None) -> str:
    """Generate cache key from request parameters."""
    raw = json.dumps({"url": url, "params": dict(params or {})}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _read_cached_json(key: str) -> JsonValue | None:
    """Return a cached JSON value when present and fresh."""
    try:
        with closing(_get_cache_db()) as db:
            row = db.execute(
                "SELECT value, ts FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row or (time.time() - row[1]) >= CACHE_TTL:
        return None
    return json.loads(row[0])


def _write_cached_json(key: str, value: JsonValue) -> None:
    """Best-effort cache write; cache failures should not fail the request."""
    try:
        with closing(_get_cache_db()) as db:
            db.execute(
                "INSERT OR REPLACE INTO cache (key, value, ts) VALUES (?, ?, ?)",
                (key, json.dumps(value), time.time()),
            )
            db.commit()
    except sqlite3.Error:
        return


def get_cache_stats() -> dict | None:
    """Return cache stats or None if no cache exists."""
    if not _DB_PATH.exists():
        return None
    with closing(_get_cache_db()) as db:
        count = db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        oldest = db.execute("SELECT MIN(ts) FROM cache").fetchone()[0]
        newest = db.execute("SELECT MAX(ts) FROM cache").fetchone()[0]
    return {
        "entries": count,
        "size_kb": _DB_PATH.stat().st_size / 1024,
        "oldest": oldest,
        "newest": newest,
    }


def clear_cache() -> bool:
    """Delete cache database. Returns True if cache existed."""
    if _DB_PATH.exists():
        _DB_PATH.unlink()
        return True
    return False


class BaseTool(ABC):
    """Base class for all research tools."""

    SOURCE_TYPE: str = "UNKNOWN"

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool and return findings plus any provider errors."""

    def _ok(self, findings: list[Finding]) -> ToolResult:
        """Return a successful tool result."""
        return ToolResult(findings=findings)

    def _error(self, message: str) -> ToolResult:
        """Return a tool error without fabricating fake findings."""
        return ToolResult(errors=[message])

    def _missing_api_key(self, name: str) -> ToolResult:
        """Return a consistent missing-key error."""
        return self._error(f"{name} not set")

    def _http_error(self, service: str, error: httpx.HTTPError) -> ToolResult:
        """Return a concise provider-boundary error message."""
        if isinstance(error, httpx.HTTPStatusError):
            return self._error(
                f"{service} API error ({error.response.status_code}): {error.response.reason_phrase}"
            )
        return self._error(f"{service} API error: {error}")

    def _parse_error(self, service: str, error: Exception) -> ToolResult:
        """Return a concise parsing/shape error message."""
        return self._error(f"Failed to parse {service} results: {error}")

    def _fetch_json(
        self,
        url: str,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> JsonValue:
        """Fetch JSON with retry, backoff, and caching."""
        key = _cache_key(url, params)
        cached = _read_cached_json(key)
        if cached is not None:
            return cached

        last_error: httpx.HTTPError | None = None
        with httpx.Client(timeout=TIMEOUT) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    _write_cached_json(key, data)
                    return data
                except httpx.HTTPStatusError as error:
                    if error.response.status_code in (429, 500, 502, 503, 504):
                        last_error = error
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(2**attempt)
                        continue
                    raise
                except (httpx.TimeoutException, httpx.ConnectError) as error:
                    last_error = error
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2**attempt)

        raise last_error or httpx.ConnectError("Max retries exceeded")
