"""Gemini function declarations for tools."""

from google.genai import types

# Tool specifications - single source of truth
TOOL_SPECS = {
    "web_search": {
        "description": "Search the web for current news, articles, and general policy information",
        "params": {"query": ("STRING", "Search query")},
    },
    "academic_search": {
        "description": "Search academic papers and research studies on Semantic Scholar (200M+ papers)",
        "params": {"query": ("STRING", "Research topic or keywords")},
    },
    "census_search": {
        "description": "Search US Census data for demographics, population, housing, and economic statistics",
        "params": {
            "topic": ("STRING", "Data topic (e.g., population, income, housing, education)"),
            "geography": ("STRING", "Geographic level: us, state:XX, or county:XXXXX"),
        },
        "required": ["topic"],
    },
    "congress_search": {
        "description": "Search federal legislation on Congress.gov - bills, resolutions, amendments",
        "params": {"query": ("STRING", "Legislation search terms")},
    },
    "federal_register_search": {
        "description": "Search Federal Register for rules, proposed rules, and agency notices",
        "params": {"query": ("STRING", "Regulation search terms")},
    },
    "court_search": {
        "description": "Search federal case law and court opinions on CourtListener",
        "params": {"query": ("STRING", "Legal search terms, case names, or topics")},
    },
    "regulations_search": {
        "description": "Search Regulations.gov for public comments, proposed rules, and regulatory dockets",
        "params": {"query": ("STRING", "Regulation or docket search terms")},
    },
    "state_legislation_search": {
        "description": "Search state legislation via OpenStates",
        "params": {
            "query": ("STRING", "Legislation search terms"),
            "state": ("STRING", "State code (e.g., CA, NY)"),
        },
        "required": ["query"],
    },
}

# Tool sets by scope
SCOPE_TOOLS = {
    "news": ["web_search"],
    "policy": ["congress_search", "federal_register_search", "regulations_search", "court_search", "state_legislation_search"],
    "federal": ["web_search", "academic_search", "census_search", "congress_search", "federal_register_search", "regulations_search", "court_search"],
    "state": ["web_search", "academic_search", "census_search", "state_legislation_search"],
    "all": ["web_search", "academic_search", "census_search", "congress_search", "federal_register_search", "regulations_search", "court_search", "state_legislation_search"],
}


def _make_declaration(name: str, description_suffix: str = "") -> types.FunctionDeclaration:
    """Create a FunctionDeclaration from spec."""
    spec = TOOL_SPECS[name]
    description = spec["description"]
    if description_suffix:
        description = f"{description} ({description_suffix})"

    properties = {}
    for param_name, (param_type, param_desc) in spec["params"].items():
        properties[param_name] = types.Schema(type=param_type, description=param_desc)

    required = spec.get("required", list(spec["params"].keys())[:1])

    return types.FunctionDeclaration(
        name=name,
        description=description,
        parameters=types.Schema(type="OBJECT", properties=properties, required=required),
    )


def get_tool_declarations(scope: dict) -> list[types.FunctionDeclaration]:
    """Return Gemini function declarations based on scope."""
    scope_type = scope["type"]

    # Get tool names for this scope
    if scope_type in SCOPE_TOOLS:
        tool_names = SCOPE_TOOLS[scope_type]
    else:
        tool_names = SCOPE_TOOLS["all"]

    # Build declarations
    declarations = []
    for name in tool_names:
        suffix = ""
        if name == "state_legislation_search" and scope_type == "state":
            suffix = ", ".join(scope.get("states", []))
        elif name == "state_legislation_search" and scope_type == "all":
            suffix = "all states"
        declarations.append(_make_declaration(name, suffix))

    return declarations
