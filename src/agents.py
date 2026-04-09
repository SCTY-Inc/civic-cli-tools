"""Policy research agents using Gemini."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from google import genai
from google.genai import types
from rich.console import Console

from prompts import RESEARCHER, WRITER, REVIEWER, COMPARATOR
from tools import get_tool_declarations, ToolRegistry, ResearchResults

console = Console()

MODEL = os.getenv("CIVIC_MODEL", "gemini-2.0-flash")
MAX_ITERATIONS = int(os.getenv("CIVIC_MAX_ITERATIONS", "15"))

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
    """Research phase: runs all available tools based on scope."""
    client = _get_client()
    scope = scope or {"type": "all", "states": []}
    results = ResearchResults()

    context = f"Research this policy topic: {topic}"
    if questions:
        context += "\n\nSpecific questions to address:\n"
        context += "\n".join(f"- {q}" for q in questions)

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

    tool_declarations = get_tool_declarations(scope)
    tool_registry = ToolRegistry(scope)

    contents = [types.Content(role="user", parts=[types.Part(text=context)])]
    tools = [types.Tool(function_declarations=tool_declarations)]

    def _run_tool(fc):
        tool_args = dict(fc.args) if fc.args else {}
        if verbose:
            query = tool_args.get("query", tool_args.get("topic", ""))
            console.print(f"  [dim]{fc.name}: {query}[/]")
        return fc, tool_registry.execute(fc.name, tool_args)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for _ in range(MAX_ITERATIONS):
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=RESEARCHER,
                    tools=tools,
                    max_output_tokens=4096,
                ),
            )

            if not response.candidates or not response.candidates[0].content.parts:
                return ResearchOutput(text="", results=results, scope_label=scope_label)

            func_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if hasattr(part, "function_call") and part.function_call
            ]

            if not func_calls:
                return ResearchOutput(
                    text=_extract_text(response),
                    results=results,
                    scope_label=scope_label,
                )

            function_responses = []
            futures = [pool.submit(_run_tool, fc) for fc in func_calls]
            for future in futures:
                fc, (findings, formatted) = future.result()
                for f in findings:
                    results.add(f, fc.name)
                function_responses.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": formatted},
                        )
                    )
                )

            contents.append(response.candidates[0].content)
            contents.append(types.Content(role="user", parts=function_responses))

    return ResearchOutput(
        text=_extract_text(response),
        results=results,
        scope_label=scope_label,
    )


def write_brief(topic: str, research_output: ResearchOutput, include_appendix: bool = True) -> str:
    """Write policy brief from research findings."""
    client = _get_client()

    response = client.models.generate_content(
        model=MODEL,
        contents=f"Write a policy brief on: {topic}\n\nBased on this research:\n\n{research_output.text}",
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
    verbose: bool = False,
) -> list[ResearchOutput]:
    """Run research for multiple scopes/targets."""
    scope_map = {
        "federal": {"type": "federal", "states": []},
        "news": {"type": "news", "states": []},
        "policy": {"type": "policy", "states": []},
    }
    outputs = []
    for target in targets:
        scope = scope_map.get(target) or {"type": "state", "states": [target.upper()]}
        if verbose:
            console.print(f"\n[bold]Researching: {target}[/]")
        outputs.append(research(topic, questions, scope, verbose))
    return outputs


def write_comparison(topic: str, outputs: list[ResearchOutput]) -> str:
    """Write comparison brief from multiple research outputs."""
    client = _get_client()

    sections = [f"## {o.scope_label.upper()}\n\n{o.text}" for o in outputs]
    combined = "\n\n---\n\n".join(sections)

    response = client.models.generate_content(
        model=MODEL,
        contents=f"Compare policy approaches on: {topic}\n\nResearch by jurisdiction:\n\n{combined}",
        config=types.GenerateContentConfig(
            system_instruction=COMPARATOR,
            max_output_tokens=8192,
        ),
    )

    comparison = _extract_text(response)
    all_findings = [f for o in outputs for f in o.results.findings]
    if all_findings:
        comparison += "\n\n---\n\n" + ResearchResults(findings=all_findings).to_appendix()
    return comparison
