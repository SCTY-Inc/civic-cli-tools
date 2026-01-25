# AGENTS.md

Three-phase pipeline:

```
research (tools) → write → review → output
```

## 1. Researcher

- Uses web_search tool (Exa)
- Gathers: legislation, stakeholders, data, counterarguments
- Output: bullet points + sources

## 2. Writer

- Structures into policy brief
- Sections: summary, background, findings, options, recommendations
- No tools

## 3. Reviewer

- Checks clarity, evidence, balance
- Returns polished final version
- No tools

## Tool: web_search

Exa API with `search_and_contents()`, autoprompt, summaries.

## Prompts

`src/prompts.py` — RESEARCHER, WRITER, REVIEWER constants.
