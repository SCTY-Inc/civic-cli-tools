"""Web search tool using Exa API."""

import os

from exa_py import Exa
from google.genai import types


def get_search_declaration() -> types.FunctionDeclaration:
    """Return Gemini function declaration for web search."""
    return types.FunctionDeclaration(
        name="web_search",
        description="Search the web for current information on policy topics, legislation, research, and news",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query": types.Schema(
                    type="STRING",
                    description="Search query - be specific and include relevant keywords",
                ),
            },
            required=["query"],
        ),
    )


class WebSearch:
    """Exa-powered web search for policy research."""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> Exa:
        """Lazy initialization of Exa client."""
        if self._client is None:
            api_key = os.getenv("EXA_API_KEY")
            if not api_key:
                raise ValueError("EXA_API_KEY not set in environment")
            self._client = Exa(api_key=api_key)
        return self._client

    def execute(self, query: str) -> str:
        """Execute search and return formatted results."""
        try:
            results = self.client.search_and_contents(
                query,
                type="auto",
                use_autoprompt=True,
                num_results=5,
                text={"max_characters": 1500},
                summary=True,
            )

            if not results.results:
                return f"No results found for: {query}"

            formatted = []
            for r in results.results:
                entry = f"**{r.title}**\n"
                if hasattr(r, "summary") and r.summary:
                    entry += f"{r.summary}\n"
                elif hasattr(r, "text") and r.text:
                    entry += f"{r.text[:1000]}...\n"
                entry += f"Source: {r.url}"
                formatted.append(entry)

            return "\n\n---\n\n".join(formatted)

        except Exception as e:
            return f"Search error: {e}"


# Module-level instance
web_search = WebSearch()
