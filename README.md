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

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-25 | 0.4.0 | Compare mode, confidence scoring, source appendix, code refactor |
| 2026-01-25 | 0.3.0 | 7 tools (added CourtListener, Census), multi-source enforcement |
| 2026-01-25 | 0.2.0 | Migrated from CrewAI to vanilla Python + Gemini |
| 2024-10-24 | - | CrewAI cleanup |
| 2024-08-24 | - | Streamlined CrewAI agents |
| 2024-04-23 | - | Switched to Groq |
| 2024-03-27 | - | Groq + Mistral + Streamlit UI |
| 2024-03-02 | 0.1.0 | Initial release (Poetry + Streamlit + CrewAI) |

### Migration Notes

**v0.1 → v0.2**: Complete rewrite from CrewAI (50+ deps, 918MB) to vanilla Python (5 deps, ~50MB). Switched from Streamlit UI to CLI-first design.

**v0.2 → v0.3**: Added 7 government/academic APIs with scope-based filtering (federal/state/all).

**v0.3 → v0.4**: Added `--compare` mode for jurisdiction comparison, confidence scoring, source appendix. Split `tools.py` into package for maintainability.

## License

MIT
