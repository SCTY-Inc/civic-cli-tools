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
uv run civic "topic" --limit 10  # per-tool results cap (default 25)
uv run civic -                   # read topic from stdin
uv run civic run <preset>        # run named preset
uv run civic topics              # list presets
uv run civic doctor              # validate required/optional API keys
uv run civic get <url>           # fetch URL content (raw | JSON envelope)
uv run civic cache stats         # cache size + entries
uv run civic cache clear         # purge cached responses
```

Honors `NO_COLOR` and auto-disables Rich formatting when stdout is not a TTY.

## Files

```
src/
├── cli.py           # entry, scope parsing, --format json, doctor/get subcommands
├── _agent_cli.py    # agent-friendly CLI helpers (DoctorCheck, doctor_runner)
├── agents.py        # gemini, multi-tool loop, parallel execution
├── prompts.py       # system prompts
├── output.py        # markdown + JSON output
└── tools/
    ├── base.py            # BaseTool, retry, caching, set_results_limit (default 25)
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
