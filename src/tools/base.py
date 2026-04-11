"""Base tool class and common utilities."""

import hashlib
import json
import os
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from .models import Finding

RESULTS_LIMIT = 25  # module-level default; override via set_results_limit()
TIMEOUT = 30


def set_results_limit(n: int) -> None:
    """Override the per-tool results limit (default 25)."""
    global RESULTS_LIMIT
    if n is not None and n > 0:
        RESULTS_LIMIT = int(n)
MAX_RETRIES = 3
CACHE_TTL = 86400  # 24 hours
CACHE_DIR = Path.home() / ".cache" / "civic"
_DB_PATH = CACHE_DIR / "cache.db"


def _get_cache_db() -> sqlite3.Connection:
    """Get or create cache database with WAL mode."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(
        "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, ts REAL)"
    )
    return db


def _cache_key(url: str, params: dict | None) -> str:
    """Generate cache key from request parameters."""
    raw = json.dumps({"url": url, "params": params or {}}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cache_stats() -> dict | None:
    """Return cache stats or None if no cache exists."""
    if not _DB_PATH.exists():
        return None
    db = _get_cache_db()
    try:
        count = db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        oldest = db.execute("SELECT MIN(ts) FROM cache").fetchone()[0]
        newest = db.execute("SELECT MAX(ts) FROM cache").fetchone()[0]
        return {
            "entries": count,
            "size_kb": _DB_PATH.stat().st_size / 1024,
            "oldest": oldest,
            "newest": newest,
        }
    finally:
        db.close()


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
    def execute(self, **kwargs) -> list[Finding]:
        """Execute the tool and return findings."""
        pass

    def _error(self, message: str) -> list[Finding]:
        """Return error as Finding."""
        return [Finding(title="Error", snippet=message, url="", source_type=self.SOURCE_TYPE)]

    def _fetch_json(self, url: str, params: dict = None, headers: dict = None) -> dict:
        """Fetch JSON with retry, backoff, and caching."""
        key = _cache_key(url, params)

        # Single DB connection for both read and write
        try:
            db = _get_cache_db()
            row = db.execute("SELECT value, ts FROM cache WHERE key = ?", (key,)).fetchone()
            if row and (time.time() - row[1]) < CACHE_TTL:
                db.close()
                return json.loads(row[0])
        except sqlite3.Error:
            db = None

        # Fetch with retry + exponential backoff, reuse client
        last_error: Exception | None = None
        with httpx.Client(timeout=TIMEOUT) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    resp = client.get(url, params=params, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()

                    # Store in cache (reuse existing connection if available)
                    try:
                        if db is None:
                            db = _get_cache_db()
                        db.execute(
                            "INSERT OR REPLACE INTO cache (key, value, ts) VALUES (?, ?, ?)",
                            (key, json.dumps(data), time.time()),
                        )
                        db.commit()
                    except sqlite3.Error:
                        pass
                    finally:
                        if db:
                            db.close()

                    return data

                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (429, 500, 502, 503, 504):
                        last_error = e
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(2**attempt)
                        continue
                    if db:
                        db.close()
                    raise
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2**attempt)

        if db:
            db.close()
        raise last_error or httpx.ConnectError("Max retries exceeded")


def get_env_key(name: str) -> str | None:
    """Get environment variable, return None if not set."""
    return os.getenv(name)
