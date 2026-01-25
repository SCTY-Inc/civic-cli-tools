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
├── cli.py       # entry, scope/compare parsing
├── agents.py    # gemini, tool loop, compare mode
├── tools.py     # 7 tools + Finding/ResearchResults
├── prompts.py   # RESEARCHER, WRITER, REVIEWER, COMPARATOR
└── output.py    # markdown output
```

## License

MIT
