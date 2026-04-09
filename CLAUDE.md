# CLAUDE.md

civic-cli-tools — policy research CLI. Gemini + 8 data sources.

## Commands

```bash
uv sync                          # install
uv run civic "topic"             # all sources
uv run civic "topic" -s federal  # federal only
uv run civic "topic" -s state:CA # state only
uv run civic "topic" -v          # verbose
uv run civic "topic" -f json     # JSON output (for agents)
uv run civic run <preset>        # run named preset
uv run civic topics              # list presets
```

## Files

```
src/
├── cli.py      # entry, scope parsing, --format json
├── agents.py   # gemini, multi-tool loop, parallel execution
├── prompts.py  # system prompts
├── output.py   # markdown + JSON output
└── tools/
    ├── base.py            # BaseTool, retry, caching
    ├── models.py          # Finding, ResearchResults
    ├── declarations.py    # Gemini function specs
    ├── registry.py        # tool name → execution
    └── implementations.py # 8 tool implementations
```

## Tools

| Tool | API | Key |
|------|-----|-----|
| web_search | Exa | EXA_API_KEY |
| academic_search | Semantic Scholar | — |
| census_search | US Census | CENSUS_API_KEY (optional) |
| congress_search | Congress.gov | CONGRESS_GOV_API_KEY |
| federal_register_search | Federal Register | — |
| regulations_search | Regulations.gov | REGULATIONS_GOV_API_KEY |
| court_search | CourtListener | — |
| state_legislation_search | OpenStates | OPENSTATES_API_KEY |

## Scope

- `federal` → web, academic, census, congress, federal_register, regulations, court
- `state:XX` → web, academic, census, state_legislation
- `all` → all 8 tools

## Model

`gemini-2.0-flash` in `src/agents.py:MODEL` (configurable via `CIVIC_MODEL` env var)
