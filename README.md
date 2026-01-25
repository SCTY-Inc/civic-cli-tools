# civic-cli-tools

Policy research CLI. Generates evidence-based briefs.

```
topic → research (Gemini + Exa) → write → review → report.md
```

## Install

```bash
uv sync
cp .env.example .env  # add GOOGLE_API_KEY, EXA_API_KEY
```

## Usage

```bash
civic "Solar energy policy in Michigan"
civic "Housing affordability" -q "Impact of rent control?"
civic "AI regulation" -o ai-policy.md -v
```

## Options

```
civic [topic] [options]

  -o, --output FILE    Output file (default: report.md)
  -q, --questions Q    Research questions (repeatable)
  -v, --verbose        Show search queries
  -V, --version        Show version
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error |
| 130 | Interrupted |

## Structure

```
src/
├── cli.py       # entry point
├── agents.py    # gemini calls
├── tools.py     # exa search
├── prompts.py   # system prompts
└── output.py    # file output
```

## License

MIT
