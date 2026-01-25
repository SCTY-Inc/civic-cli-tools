# AGENTS.md

Three-phase pipeline, 7 research tools.

```
research (7 tools) → write → review → report.md
```

## 1. Researcher

Tools by scope:

| Scope | Tools |
|-------|-------|
| federal | web, academic, census, congress, federal_register, court |
| state:XX | web, academic, census, state_legislation |
| all | all 7 |

Behavior:
- MUST use ALL available tools (enforced via prompt)
- Handles parallel tool calls from Gemini
- Tracks tool usage counts (returned for --sources audit)
- Tags findings by source type

Output: categorized bullets + sources + [SOURCE_TYPE] tags

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

| Tool | API | Key Required |
|------|-----|--------------|
| web_search | Exa | Yes |
| academic_search | Semantic Scholar | No |
| census_search | US Census | No (optional) |
| congress_search | Congress.gov | Yes |
| federal_register_search | Federal Register | No |
| court_search | CourtListener | No |
| state_legislation_search | OpenStates | Yes |

## Prompts

`src/prompts.py` — RESEARCHER, WRITER, REVIEWER
