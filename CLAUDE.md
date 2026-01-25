# CLAUDE.md

civic-cli-tools — policy research CLI. Gemini + Exa.

## Commands

```bash
uv sync              # install
uv run civic "topic" # run
```

## Files

```
src/
├── cli.py      # entry, args, errors
├── agents.py   # gemini calls, tool loop
├── tools.py    # exa search
├── prompts.py  # system prompts
└── output.py   # markdown output
```

## Env

`GOOGLE_API_KEY`, `EXA_API_KEY` in `.env`

## Model

`gemini-2.5-flash-preview-05-20` — change in `src/agents.py:MODEL`
