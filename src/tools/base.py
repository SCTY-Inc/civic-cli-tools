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

RESULTS_LIMIT = 10
TIMEOUT = 30
MAX_RETRIES = 3
CACHE_TTL = 86400  # 24 hours
CACHE_DIR = Path.home() / ".cache" / "civic"


def _get_cache_db() -> sqlite3.Connection:
    """Get or create cache database."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(CACHE_DIR / "cache.db"))
    db.execute(
        "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, ts REAL)"
    )
    return db


def _cache_key(url: str, params: dict | None, headers: dict | None) -> str:
    """Generate cache key from request parameters."""
    raw = json.dumps(
        {"url": url, "params": params or {}},
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


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
        key = _cache_key(url, params, headers)

        # Check cache
        try:
            db = _get_cache_db()
            row = db.execute("SELECT value, ts FROM cache WHERE key = ?", (key,)).fetchone()
            if row and (time.time() - row[1]) < CACHE_TTL:
                db.close()
                return json.loads(row[0])
            db.close()
        except sqlite3.Error:
            pass

        # Fetch with retry + exponential backoff
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=TIMEOUT) as client:
                    resp = client.get(url, params=params, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()

                # Store in cache
                try:
                    db = _get_cache_db()
                    db.execute(
                        "INSERT OR REPLACE INTO cache (key, value, ts) VALUES (?, ?, ?)",
                        (key, json.dumps(data), time.time()),
                    )
                    db.commit()
                    db.close()
                except sqlite3.Error:
                    pass

                return data

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503, 504):
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2**attempt)
                    continue
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2**attempt)

        raise last_error or httpx.ConnectError("Max retries exceeded")


def get_env_key(name: str) -> str | None:
    """Get environment variable, return None if not set."""
    return os.getenv(name)
