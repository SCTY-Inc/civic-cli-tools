# civic-cli-tools

Policy research CLI. Generates evidence-based briefs from 7 government and academic sources.

```
topic → research (7 APIs) → write → review → report.md
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
| CONGRESS_GOV_API_KEY | `--scope federal` | [api.congress.gov/sign-up](https://api.congress.gov/sign-up) | Free |
| OPENSTATES_API_KEY | `--scope state:XX` | [openstates.org/accounts/register](https://openstates.org/accounts/register/) | Free |
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
```

## Compare Mode

Compare policy across jurisdictions:

```bash
civic "Paid leave" --compare CA,NY             # state vs state
civic "Healthcare" --compare federal,CA        # federal vs state
civic "Immigration" --compare policy,news      # legislation vs media
civic "Cannabis" --compare CA,CO,NY            # multi-state
```

## Options

```
-s, --scope SCOPE      federal | state:XX | all (default)
-c, --compare A,B      compare targets: CA,NY or federal,CA or policy,news
-o, --output FILE      default: outputs/report.md
-q, --questions Q      research questions
-v, --verbose          show tool calls
--sources              show confidence score + source usage
--no-appendix          exclude source appendix from output
-V, --version
```

## Output Features

- **Confidence scoring**: HIGH/MEDIUM/LOW based on source diversity, recency, citations
- **Source appendix**: Raw findings with dates and URLs for verification
- **Comparison matrix**: Side-by-side analysis for --compare mode

## Tools

| Tool | Source | Data |
|------|--------|------|
| web_search | Exa | news, articles |
| academic_search | Semantic Scholar | 200M+ papers |
| census_search | US Census | demographics, income, housing |
| congress_search | Congress.gov | federal bills |
| federal_register_search | Federal Register | rules, notices |
| court_search | CourtListener | federal case law |
| state_legislation_search | OpenStates | 50 state bills |

## Structure

```
src/
├── cli.py           # entry, scope/compare parsing
├── agents.py        # gemini, tool loop, compare mode
├── prompts.py       # RESEARCHER, WRITER, REVIEWER, COMPARATOR
├── output.py        # markdown output
└── tools/
    ├── models.py        # Finding, ResearchResults
    ├── declarations.py  # Gemini function specs
    ├── implementations.py  # 7 tool classes
    ├── registry.py      # ToolRegistry
    └── base.py          # BaseTool class
```

## Changelog

| Date | Change |
|------|--------|
| **2026-01-25** | **v0.4** — Compare mode (`--compare CA,NY`), confidence scoring, source appendix, refactored tools/ package |
| **2026-01-25** | **v0.3** — 7 API tools: Exa, Semantic Scholar, Congress.gov, Federal Register, CourtListener, Census, OpenStates |
| **2026-01-25** | **v0.2** — Rewrite: CrewAI → vanilla Python + Gemini. Streamlit UI → CLI. 50+ deps → 5 deps |
| 2024-08-24 | Streamlined CrewAI agents |
| 2024-04-23 | Switched LLM to Groq |
| 2024-03-27 | Added Groq + Mistral, Streamlit UI |
| 2024-02-28 | Pivoted from trip planner to policy brief generator |
| **2023-12-27** | **v0.1** — Initial commit: CrewAI trip planning demo (Poetry + OpenAI) |

### Project Evolution

```
Trip Planner (Dec 2023)
    ↓ pivoted to policy research
Policy Brief Generator (Feb 2024)
    ↓ added UI
Streamlit + CrewAI + Groq (Mar 2024)
    ↓ simplified
Vanilla Python CLI + Gemini (Jan 2026)
    ↓ added multi-source
7-API Research Tool + Compare Mode (Jan 2026)
```

**Key metrics:**
- Dependencies: 50+ → 5
- Install size: 918MB → ~50MB
- Data sources: 1 (web) → 7 (gov + academic APIs)

## License

MIT
