# AGENTS.md

Three-phase pipeline, 5 research tools.

```
research (5 tools) → write → review → report.md
```

## 1. Researcher

Tools by scope:

| Scope | Tools |
|-------|-------|
| federal | web, academic, congress, federal_register |
| state:XX | web, academic, state_legislation |
| all | all 5 |

Handles parallel tool calls from Gemini.

Output: categorized bullets + sources

## 2. Writer

Structures into policy brief:
- Executive summary
- Background
- Key findings
- Policy options
- Recommendations
- Sources

## 3. Reviewer

Checks clarity, evidence, balance, structure.
Returns polished version.

## Tools

| Tool | API | Rate Limit |
|------|-----|------------|
| web_search | Exa | — |
| academic_search | Semantic Scholar | 1 RPS |
| congress_search | Congress.gov | — |
| federal_register_search | Federal Register | — |
| state_legislation_search | OpenStates | — |

## Prompts

`src/prompts.py` — RESEARCHER, WRITER, REVIEWER
