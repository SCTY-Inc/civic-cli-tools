"""Base tool class and common utilities."""

import hashlib
import json
import os
import random
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from .models import Finding

RESULTS_LIMIT = 25
TIMEOUT = 30
MAX_RETRIES = 3
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
CACHE_TTL = 86400
CACHE_DIR = Path.home() / ".cache" / "civic"
_DB_PATH = CACHE_DIR / "cache.db"


def set_results_limit(n: int) -> None:
    """Override the per-tool results limit (default 25)."""
    global RESULTS_LIMIT
    if n and n > 0:
        RESULTS_LIMIT = int(n)


def _get_cache_db() -> sqlite3.Connection:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, ts REAL)")
    return db


def _cache_key(url: str, params: dict | None) -> str:
    raw = json.dumps({"url": url, "params": params or {}}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cache_stats() -> dict | None:
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

    def _error(self, message: str) -> list[Finding]:
        return [
            Finding(
                title="Error",
                snippet=message,
                url="",
                source_type=self.SOURCE_TYPE,
                is_error=True,
            )
        ]

    def _fetch_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
        """Fetch JSON with retry, backoff, and SQLite caching."""
        key = _cache_key(url, params)
        db: sqlite3.Connection | None = None

        try:
            db = _get_cache_db()
            row = db.execute("SELECT value, ts FROM cache WHERE key = ?", (key,)).fetchone()
            if row and (time.time() - row[1]) < CACHE_TTL:
                cached = json.loads(row[0])
                db.close()
                return cached
        except sqlite3.Error:
            if db:
                db.close()
            db = None

        last_error: Exception | None = None
        with httpx.Client(timeout=TIMEOUT) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()
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
                            db = None
                    return data
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code if exc.response else 0
                    if status not in RETRYABLE_STATUS or attempt == MAX_RETRIES - 1:
                        if status == 429:
                            raise RuntimeError("Rate limited by upstream API") from exc
                        raise RuntimeError(f"HTTP error ({status})") from exc
                    last_error = RuntimeError(f"Transient upstream error ({status})")
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_error = RuntimeError(f"Network error: {exc}")
                    if attempt == MAX_RETRIES - 1:
                        raise last_error from exc

                time.sleep((0.25 * (2**attempt)) + random.uniform(0, 0.1))

        if db:
            db.close()
        raise last_error or RuntimeError("Request failed")


def get_env_key(name: str) -> str | None:
    return os.getenv(name)
