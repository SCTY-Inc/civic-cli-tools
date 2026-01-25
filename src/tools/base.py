"""Base tool class and common utilities."""

import os
from abc import ABC, abstractmethod

import httpx

from .models import Finding

RESULTS_LIMIT = 10
TIMEOUT = 30


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
        """Fetch JSON from URL with standard timeout."""
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()


def get_env_key(name: str) -> str | None:
    """Get environment variable, return None if not set."""
    return os.getenv(name)
