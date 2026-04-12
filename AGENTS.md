# AGENTS.md

Four-phase pipeline, 8 research tools, compare mode, JSON output.

```
research (8 tools, parallel) → write → review → report.md
         ↓                                     → stdout (JSON)
   [compare mode]
         ↓
research A → research B → compare → report.md
```

## 1. Researcher

Tools by scope:

| Scope | Tools |
|-------|-------|
| federal | web, academic, census, congress, federal_register, regulations, court |
| state:XX | web, academic, census, state_legislation |
| all | all 8 |
| news | web only |
| policy | congress, federal_register, regulations, court, state_legislation |

Behavior:
- MUST use ALL available tools (enforced via prompt)
- Parallel tool execution via ThreadPoolExecutor
- Returns `ResearchOutput` with findings + metadata
- Tracks tool calls for --sources audit
- Max iterations configurable via `CIVIC_MAX_ITERATIONS` (default: 15)

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
    date: str         # YYYY-MM-DD or YYYY
    source_type: str  # WEB, ACADEMIC, CONGRESS, REGULATIONS, etc
    citations: int    # for academic papers
    is_error: bool = False

    def to_dict() -> dict  # for JSON output

@dataclass
class ResearchResults:
    findings: list[Finding]
    tool_usage: dict[str, int]  # per tool invocation, not per finding

    def confidence_score() -> (level, explanation)
    def to_dict() -> dict   # for JSON output
    def to_text() -> str    # successful findings for LLM
    def to_appendix() -> str  # evidence + separate tool errors
```

## Confidence Scoring

```
Score = (diversity × 0.4) + (recency × 0.3) + (citations × 0.3)

●●●●● HIGH   — 5+ source types, recent, cited
●●●○○ MEDIUM — 3-4 sources, some dated
●○○○○ LOW    — 1-2 sources, old data

Errors are tracked separately and excluded from confidence/evidence totals.
```

## Tools

Per-tool result cap defaults to `RESULTS_LIMIT = 25` (set in `src/tools/base.py`).
Override at runtime with `--limit N` on `civic <topic>` or `civic run <preset>`;
this calls `set_results_limit()` before research kicks off.

| Tool | API | Key Required | Results |
|------|-----|--------------|---------|
| web_search | Exa | Yes | RESULTS_LIMIT |
| academic_search | Semantic Scholar | No | RESULTS_LIMIT |
| census_search | US Census | No (optional) | 5 |
| congress_search | Congress.gov | Yes | RESULTS_LIMIT |
| federal_register_search | Federal Register | No | RESULTS_LIMIT |
| regulations_search | Regulations.gov | Yes | RESULTS_LIMIT |
| court_search | CourtListener | No | RESULTS_LIMIT |
| state_legislation_search | OpenStates | Yes | RESULTS_LIMIT |

## Infrastructure

- **Retry**: 3 attempts with exponential backoff on timeouts, connection errors, 429/5xx
- **Cache**: SQLite at `~/.cache/civic/cache.db`, 24h TTL, keyed on URL + params
- **Parallel execution**: ThreadPoolExecutor, up to 8 concurrent tool calls per iteration
- **Input validation**: Empty queries return error Findings, don't hit APIs

## Prompts

`src/prompts.py`:
- `RESEARCHER` — tool usage, output format
- `WRITER` — brief structure
- `REVIEWER` — quality checks
- `COMPARATOR` — comparison analysis

## Agent Integration

For programmatic use by other agents:

```bash
uv run civic doctor                            # preflight: validate required API keys
uv run civic "topic" -s federal -f json        # run pipeline, JSON to stdout
uv run civic "topic" -f json --limit 50        # widen per-tool results
echo "topic" | uv run civic - -f json          # read topic from stdin
uv run civic get <url> -f json                 # fetch arbitrary URL as JSON envelope
```

Returns structured JSON to stdout with findings, confidence, tool_usage, and tool errors when present.
Exit code 0 on success, 1 on error, 130 on interrupt.
Rich formatting auto-disables when stdout is not a TTY or when `NO_COLOR` is set.
