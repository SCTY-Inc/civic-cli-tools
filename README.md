# civic-cli-tools

Policy research CLI. Generates evidence-based briefs from 8 government and academic sources.

```
topic → research (8 APIs) → write → review → report.md
                                           → stdout (JSON)
```

## Install

```bash
uv sync
cp .env.example .env  # add API keys
```

## API Keys

| Key | When Needed | Get It | Cost |
|-----|-------------|--------|------|
| GOOGLE_API_KEY | Always | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Free |
| EXA_API_KEY | Always | [dashboard.exa.ai](https://dashboard.exa.ai/api-keys) | Free tier |
| CONGRESS_GOV_API_KEY | federal or policy research (`--scope federal`, `--compare federal,news`, `--compare policy,...`) | [api.congress.gov/sign-up](https://api.congress.gov/sign-up) | Free |
| OPENSTATES_API_KEY | state or policy research (`--scope state:XX`, `--compare CA,NY`, `--compare policy,...`) | [openstates.org/accounts/register](https://openstates.org/accounts/register/) | Free |
| REGULATIONS_GOV_API_KEY | `--scope federal` | [api.data.gov/signup](https://api.data.gov/signup/) | Free |
| CENSUS_API_KEY | Optional | [api.census.gov/data/key_signup](https://api.census.gov/data/key_signup.html) | Free |

No key needed: Semantic Scholar, Federal Register, CourtListener.

## Usage

```bash
civic "Solar energy policy"                    # all sources
civic "AI regulation" -s federal               # federal only
civic "Rent control" -s state:CA,NY            # specific states
civic "Housing" -q "Impact of zoning reform?"  # with questions
civic "Climate policy" -v                      # verbose
civic "Healthcare" --sources                   # show confidence + source audit
civic "AI regulation" --limit 10               # cap per-tool results (default 25)
echo "Paid leave" | civic -                    # read topic from stdin
```

### Environment Check

```bash
civic doctor                                   # validate required + optional API keys
```

Required: `GOOGLE_API_KEY`, `EXA_API_KEY` (fail the run if missing).
Optional (advisory only): `CONGRESS_GOV_API_KEY`, `OPENSTATES_API_KEY`, `REGULATIONS_GOV_API_KEY`, `CENSUS_API_KEY` — each gates a specific source and prints a signup URL when missing.

### Fetch URL

```bash
civic get https://example.com/bill.pdf         # raw body to stdout
civic get https://example.com -f json          # JSON envelope (status, headers, content)
```

### JSON Output (for agents)

```bash
civic "AI regulation" -s federal -f json       # structured JSON to stdout
civic "Caregiver policy" -f json | jq '.findings | length'
```

JSON schema:
```json
{
  "topic": "...",
  "scope": "...",
  "timestamp": "ISO8601",
  "confidence": { "level": "HIGH", "detail": "..." },
  "findings": [{ "title", "snippet", "url", "date", "source_type", "citations", "is_error" }],
  "tool_usage": { "congress_search": 1, ... },
  "errors": [{ "title", "snippet", "source_type", "is_error" }]
}
```

`tool_usage` counts tool invocations, not individual findings.

### Compare Mode

Special compare targets are `federal`, `news`, and `policy`.

```bash
civic "Paid leave" --compare CA,NY             # state vs state
civic "Healthcare" --compare federal,CA        # federal vs state
civic "Immigration" --compare policy,news      # legislation vs media
civic "Cannabis" --compare CA,CO,NY            # multi-state
```

### Topic Presets

```bash
civic topics                                   # list presets
civic run caregiver-federal                    # run named preset
civic run ai-regulation-federal -f json        # preset with JSON output
```

## Options

```
-s, --scope SCOPE      federal | state:XX | all (default)
-c, --compare A,B      compare targets: CA,NY or federal,CA or policy,news
-f, --format FMT       markdown (file) | json (stdout)
-o, --output FILE      default: outputs/report.md
-q, --questions Q      research questions
-v, --verbose          show tool calls
--sources              show confidence score + tool-call usage
--no-appendix          exclude source appendix from output
--limit N              per-tool results cap (default: 25)
-V, --version
```

Pass `-` as the topic to read it from stdin. Rich output respects `NO_COLOR` and auto-disables when stdout is not a TTY.

### Cache Management

```bash
civic cache stats                              # show cache size + entries
civic cache clear                              # purge all cached responses
```

## Output Features

- **Confidence scoring**: HIGH/MEDIUM/LOW based on successful-source diversity, recency, and citations
- **Source appendix**: Raw findings with dates and URLs for verification, plus a separate tool-error section
- **Comparison matrix**: Side-by-side analysis for --compare mode
- **Response caching**: 24h SQLite cache at `~/.cache/civic/` — repeat queries are instant

## Tools

| Tool | Source | Data |
|------|--------|------|
| web_search | Exa | news, articles |
| academic_search | Semantic Scholar | 200M+ papers |
| census_search | US Census | demographics, income, housing (18 variables) |
| congress_search | Congress.gov | federal bills |
| federal_register_search | Federal Register | rules, notices |
| regulations_search | Regulations.gov | dockets, comments, rulemaking |
| court_search | CourtListener | federal case law |
| state_legislation_search | OpenStates | 50 state bills |

## Configuration

| Env Var | Default | Purpose |
|---------|---------|---------|
| CIVIC_MODEL | gemini-2.5-flash | Gemini model for all phases |
| CIVIC_MAX_ITERATIONS | 15 | Max tool calls per research phase |

## Structure

```
src/
├── cli.py               # entry, scope/compare parsing, --format json, doctor/get
├── _agent_cli.py        # agent-friendly CLI helpers (DoctorCheck, doctor_runner)
├── agents.py            # gemini orchestration, scoped compare execution
├── prompts.py           # RESEARCHER, WRITER, REVIEWER, COMPARATOR
├── output.py            # markdown + JSON output
└── tools/
    ├── models.py        # Finding, ResearchResults
    ├── declarations.py  # Gemini function specs
    ├── implementations.py  # 8 tool classes
    ├── registry.py      # ToolRegistry + scope-aware defaults
    └── base.py          # BaseTool, retry, caching, set_results_limit (default 25)
tests/
├── test_cli.py          # scope parsing, env checks, appendix ordering
├── test_models.py       # Finding, ResearchResults, confidence, error handling
└── test_tools.py        # all 8 tools with mocked HTTP + scope defaults
```

## Changelog

| Date | Change |
|------|--------|
| **2026-04-09** | **v0.6** — 8th source (Regulations.gov), `--format json`, parallel execution, retry/caching, 18 Census variables, 41 tests |
| **2026-01-28** | **v0.5** — topics.toml presets, `run`/`topics` subcommands, gemini-2.0-flash |
| **2026-01-25** | **v0.4** — Compare mode (`--compare CA,NY`), confidence scoring, source appendix, refactored tools/ package |
| **2026-01-25** | **v0.3** — 7 API tools: Exa, Semantic Scholar, Congress.gov, Federal Register, CourtListener, Census, OpenStates |
| **2026-01-25** | **v0.2** — Rewrite: CrewAI → vanilla Python + Gemini. Streamlit UI → CLI. 50+ deps → 5 deps |
| **2023-12-27** | **v0.1** — Initial commit: CrewAI trip planning demo |

**Key metrics:**
- Dependencies: 50+ → 5
- Install size: 918MB → ~50MB
- Data sources: 1 (web) → 8 (gov + academic APIs)
- Tests: 0 → 41

## License

MIT
