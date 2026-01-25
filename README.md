# civic-cli-tools

Policy research CLI. Generates evidence-based briefs from multiple sources.

```
topic → research (5 tools) → write → review → report.md
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
| CONGRESS_GOV_API_KEY | `--scope federal` or `all` | [api.congress.gov/sign-up](https://api.congress.gov/sign-up) | Free |
| OPENSTATES_API_KEY | `--scope state:XX` or `all` | [openstates.org/accounts/register](https://openstates.org/accounts/register/) | Free |

Semantic Scholar and Federal Register APIs don't require keys.

## Usage

```bash
civic "Solar energy policy"                    # all sources
civic "AI regulation" -s federal               # federal only
civic "Rent control" -s state:CA,NY            # specific states
civic "Housing" -q "Impact of zoning reform?"  # with questions
civic "Climate policy" -v                      # verbose
```

## Options

```
-s, --scope SCOPE    federal | state:XX | all (default)
-o, --output FILE    default: report.md
-q, --questions Q    research questions
-v, --verbose        show tool calls
-V, --version
```

## Tools

| Tool | Source | Data |
|------|--------|------|
| web_search | Exa | news, articles |
| academic_search | Semantic Scholar | 200M+ papers |
| congress_search | Congress.gov | federal bills |
| federal_register_search | Federal Register | rules, notices |
| state_legislation_search | OpenStates | 50 state bills |

## Structure

```
src/
├── cli.py       # entry, scope parsing
├── agents.py    # gemini, tool loop
├── tools.py     # 5 tools + registry
├── prompts.py   # system prompts
└── output.py    # markdown output
```

## License

MIT
