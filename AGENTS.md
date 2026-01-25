# AGENTS.md

Four-phase pipeline, 7 research tools, compare mode.

```
research (7 tools) → write → review → report.md
         ↓
   [compare mode]
         ↓
research A → research B → compare → report.md
```

## 1. Researcher

Tools by scope:

| Scope | Tools |
|-------|-------|
| federal | web, academic, census, congress, federal_register, court |
| state:XX | web, academic, census, state_legislation |
| all | all 7 |
| news | web only |
| policy | congress, federal_register, court, state_legislation |

Behavior:
- MUST use ALL available tools (enforced via prompt)
- Handles parallel tool calls from Gemini
- Returns `ResearchOutput` with findings + metadata
- Tracks tool usage for --sources audit

Output: `ResearchOutput(text, results, scope_label)`

## 2. Writer

Structures into policy brief:
- Executive summary
- Background
- Key findings
- Policy options
- Recommendations
- Sources
- Appendix (optional)

## 3. Reviewer

Checks clarity, evidence, balance, structure.
Returns polished version.

## 4. Comparator (--compare mode)

Generates side-by-side analysis:
- Comparison matrix
- Jurisdiction-specific findings
- Key differences
- Common ground
- Cross-jurisdictional recommendations

## Data Structures

```python
@dataclass
class Finding:
    title: str
    snippet: str
    url: str
    date: str       # YYYY-MM-DD or YYYY
    source_type: str  # WEB, ACADEMIC, CONGRESS, etc
    citations: int    # for academic papers

@dataclass
class ResearchResults:
    findings: list[Finding]
    tool_usage: dict[str, int]

    def confidence_score() -> (level, explanation)
    def to_text() -> str      # for LLM
    def to_appendix() -> str  # for output
```

## Confidence Scoring

```
Score = (diversity × 0.4) + (recency × 0.3) + (citations × 0.3)

●●●●● HIGH   — 5+ source types, recent, cited
●●●○○ MEDIUM — 3-4 sources, some dated
●○○○○ LOW    — 1-2 sources, old data
```

## Tools

| Tool | API | Key Required | Results |
|------|-----|--------------|---------|
| web_search | Exa | Yes | 10 |
| academic_search | Semantic Scholar | No | 10 |
| census_search | US Census | No (optional) | 5 |
| congress_search | Congress.gov | Yes | 10 |
| federal_register_search | Federal Register | No | 10 |
| court_search | CourtListener | No | 10 |
| state_legislation_search | OpenStates | Yes | 10 |

## Prompts

`src/prompts.py`:
- `RESEARCHER` — tool usage, output format
- `WRITER` — brief structure
- `REVIEWER` — quality checks
- `COMPARATOR` — comparison analysis

## Code Structure

```
src/
├── cli.py (215 LOC)      # entry point
├── agents.py (265 LOC)   # gemini orchestration
├── prompts.py (131 LOC)  # system prompts
├── output.py (15 LOC)    # file output
└── tools/
    ├── models.py (96 LOC)         # Finding, ResearchResults
    ├── declarations.py (95 LOC)   # Gemini function specs
    ├── implementations.py (246 LOC)  # 7 tool classes
    ├── registry.py (43 LOC)       # ToolRegistry
    └── base.py (38 LOC)           # BaseTool class
```

All files < 300 LOC per project guidelines.
