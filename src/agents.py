"""Policy research agents using Gemini."""

import os
from dataclasses import dataclass

from google import genai
from google.genai import types
from rich.console import Console

from prompts import RESEARCHER, WRITER, REVIEWER, COMPARATOR
from tools import get_tool_declarations, ToolRegistry, ResearchResults

console = Console()

MODEL = "gemini-3-flash-preview"

# Singleton client
_client: genai.Client | None = None


@dataclass
class ResearchOutput:
    """Complete research output with metadata."""
    text: str
    results: ResearchResults
    scope_label: str = ""


def _get_client() -> genai.Client:
    """Get or create Gemini client (singleton)."""
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment")
        _client = genai.Client(api_key=api_key)
    return _client


def _extract_text(response) -> str:
    """Extract text content from Gemini response."""
    if not response.candidates:
        return ""
    parts = []
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            parts.append(part.text)
    return "".join(parts)


def research(
    topic: str,
    questions: list[str] | None = None,
    scope: dict | None = None,
    verbose: bool = False
) -> ResearchOutput:
    """Research phase with multiple tools based on scope."""
    client = _get_client()
    scope = scope or {"type": "all", "states": []}
    results = ResearchResults()

    # Build context
    context = f"Research this policy topic: {topic}"
    if questions:
        context += "\n\nSpecific questions to address:\n"
        context += "\n".join(f"- {q}" for q in questions)

    # Add scope context
    if scope["type"] == "federal":
        context += "\n\nFocus on FEDERAL policy only (Congress, federal agencies)."
        scope_label = "federal"
    elif scope["type"] == "state":
        states = ", ".join(scope["states"])
        context += f"\n\nFocus on STATE policy only for: {states}"
        scope_label = f"state:{','.join(scope['states'])}"
    else:
        context += "\n\nSearch BOTH federal and state policy sources."
        scope_label = "federal + state"

    # Initialize tools
    tool_declarations = get_tool_declarations(scope)
    tool_registry = ToolRegistry(scope)

    contents = [types.Content(role="user", parts=[types.Part(text=context)])]
    tools = [types.Tool(function_declarations=tool_declarations)]

    max_iterations = 15
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=RESEARCHER,
                tools=tools,
                max_output_tokens=4096,
            ),
        )

        # Collect all function calls
        func_calls = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, "function_call") and part.function_call:
                func_calls.append(part.function_call)

        if not func_calls:
            return ResearchOutput(
                text=_extract_text(response),
                results=results,
                scope_label=scope_label
            )

        # Execute all tools and collect responses
        function_responses = []
        for func_call in func_calls:
            tool_name = func_call.name
            tool_args = dict(func_call.args) if func_call.args else {}

            if verbose:
                query = tool_args.get("query", tool_args.get("topic", ""))
                console.print(f"  [dim]{tool_name}: {query}[/]")

            findings, formatted = tool_registry.execute(tool_name, tool_args)

            # Store findings
            for f in findings:
                results.add(f, tool_name)

            function_responses.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=func_call.name,
                        response={"result": formatted},
                    )
                )
            )

        contents.append(response.candidates[0].content)
        contents.append(types.Content(role="user", parts=function_responses))

    return ResearchOutput(
        text=_extract_text(response),
        results=results,
        scope_label=scope_label
    )


def write_brief(topic: str, research_output: ResearchOutput, include_appendix: bool = True) -> str:
    """Write policy brief from research findings."""
    client = _get_client()

    prompt = f"""Write a policy brief on: {topic}

Based on this research:

{research_output.text}"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=WRITER,
            max_output_tokens=8192,
        ),
    )

    brief = _extract_text(response)

    if include_appendix and research_output.results.findings:
        brief += "\n\n---\n\n" + research_output.results.to_appendix()

    return brief


def review(draft: str) -> str:
    """Review and refine the policy brief."""
    client = _get_client()

    response = client.models.generate_content(
        model=MODEL,
        contents=f"Review and refine this policy brief:\n\n{draft}",
        config=types.GenerateContentConfig(
            system_instruction=REVIEWER,
            max_output_tokens=8192,
        ),
    )

    return _extract_text(response)


def compare_research(
    topic: str,
    targets: list[str],
    questions: list[str] | None = None,
    verbose: bool = False
) -> list[ResearchOutput]:
    """Run research for multiple scopes/targets."""
    outputs = []

    for target in targets:
        # Parse target into scope
        if target == "federal":
            scope = {"type": "federal", "states": []}
        elif target == "news":
            # News-only: just web search
            scope = {"type": "news", "states": []}
        elif target == "policy":
            # Policy sources only
            scope = {"type": "policy", "states": []}
        elif len(target) == 2 and target.upper() == target:
            # State code
            scope = {"type": "state", "states": [target]}
        else:
            scope = {"type": "state", "states": [target.upper()]}

        if verbose:
            console.print(f"\n[bold]Researching: {target}[/]")

        output = research(topic, questions, scope, verbose)
        outputs.append(output)

    return outputs


def write_comparison(topic: str, outputs: list[ResearchOutput]) -> str:
    """Write comparison brief from multiple research outputs."""
    client = _get_client()

    # Build comparison context
    sections = []
    for output in outputs:
        sections.append(f"## {output.scope_label.upper()}\n\n{output.text}")

    combined = "\n\n---\n\n".join(sections)

    prompt = f"""Compare and contrast policy approaches on: {topic}

Research findings by jurisdiction:

{combined}"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=COMPARATOR,
            max_output_tokens=8192,
        ),
    )

    comparison = _extract_text(response)

    # Add combined appendix
    all_findings = []
    for output in outputs:
        all_findings.extend(output.results.findings)

    if all_findings:
        combined_results = ResearchResults(findings=all_findings)
        comparison += "\n\n---\n\n" + combined_results.to_appendix()

    return comparison
