# CLAUDE.md

civic-cli-tools — policy research CLI. Gemini + 5 data sources.

## Commands

```bash
uv sync                          # install
uv run civic "topic"             # all sources
uv run civic "topic" -s federal  # federal only
uv run civic "topic" -s state:CA # state only
uv run civic "topic" -v          # verbose
```

## Files

```
src/
├── cli.py      # entry, scope parsing
├── agents.py   # gemini, multi-tool loop
├── tools.py    # 5 tools + registry
├── prompts.py  # system prompts
└── output.py   # markdown output
```

## Tools

| Tool | API | Key |
|------|-----|-----|
| web_search | Exa | EXA_API_KEY |
| academic_search | Semantic Scholar | — |
| congress_search | Congress.gov | CONGRESS_GOV_API_KEY |
| federal_register_search | Federal Register | — |
| state_legislation_search | OpenStates | OPENSTATES_API_KEY |

## Scope

- `federal` → web, academic, congress, federal_register
- `state:XX` → web, academic, state_legislation
- `all` → all 5 tools

## Model

`gemini-3-flash-preview` in `src/agents.py:MODEL`
