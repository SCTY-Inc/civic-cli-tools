"""Policy research agents using Gemini."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from google import genai
from google.genai import types
from rich.console import Console

from prompts import COMPARATOR, RESEARCHER, REVIEWER, WRITER
from tools import ResearchResults, ToolRegistry, get_tool_declarations

console = Console()

MODEL = os.getenv("CIVIC_MODEL", "gemini-2.5-flash")
MAX_ITERATIONS = int(os.getenv("CIVIC_MAX_ITERATIONS", "15"))
MAX_PARALLEL_TOOLS = int(os.getenv("CIVIC_MAX_PARALLEL_TOOLS", "8"))

_client: genai.Client | None = None


@dataclass
class ResearchOutput:
    """Complete research output with metadata."""

    text: str
    results: ResearchResults
    scope_label: str = ""


def scope_from_target(target: str) -> dict:
    target = target.strip()
    lowered = target.lower()
    if lowered in {"federal", "news", "policy"}:
        return {"type": lowered, "states": []}
    return {"type": "state", "states": [target.upper()]}


def combine_results(outputs: list[ResearchOutput]) -> ResearchResults:
    combined = ResearchResults()
    for output in outputs:
        combined.absorb(output.results)
    return combined


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment")
        _client = genai.Client(api_key=api_key)
    return _client


def _extract_text(response) -> str:
    if not response.candidates:
        return ""
    parts = []
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            parts.append(part.text)
    return "".join(parts).strip()


def _scope_details(scope: dict) -> tuple[str, str]:
    scope_type = scope["type"]
    if scope_type == "federal":
        return "federal", "Focus on FEDERAL policy only (Congress, federal agencies, nationwide data)."
    if scope_type == "state":
        states = ", ".join(scope["states"])
        return f"state:{','.join(scope['states'])}", f"Focus on STATE policy only for: {states}."
    if scope_type == "news":
        return "news", "Focus on NEWS coverage and recent web reporting only."
    if scope_type == "policy":
        return "policy", "Focus on primary policy sources only: Congress, Federal Register, Regulations.gov, courts, and state legislation."
    return "all", "Search both federal and state policy sources."


def _tool_query(args: dict) -> str:
    return args.get("query") or args.get("topic") or ""


def _validate_research_output(output: ResearchOutput) -> None:
    if not output.results.evidence:
        raise RuntimeError(f"Research for {output.scope_label} produced no successful findings")
    if not output.text:
        raise RuntimeError(f"Researcher did not produce a written synthesis for {output.scope_label}")


def research(topic: str, questions: list[str] | None = None, scope: dict | None = None, verbose: bool = False) -> ResearchOutput:
    """Research phase: run all tools available for the selected scope."""
    client = _get_client()
    scope = scope or {"type": "all", "states": []}
    results = ResearchResults()
    scope_label, scope_instruction = _scope_details(scope)

    context = [f"Research this policy topic: {topic}"]
    if questions:
        context.append("Specific questions to address:\n" + "\n".join(f"- {question}" for question in questions))
    context.append(scope_instruction)

    contents = [types.Content(role="user", parts=[types.Part(text="\n\n".join(context))])]
    tools = [types.Tool(function_declarations=get_tool_declarations(scope))]
    tool_registry = ToolRegistry(scope)

    def _run_tool(call):
        tool_name = call.name
        tool_args = dict(call.args) if call.args else {}
        if verbose:
            console.print(f"  [dim]{tool_name}: {_tool_query(tool_args)}[/]")
        findings, formatted = tool_registry.execute(tool_name, tool_args)
        return tool_name, findings, formatted

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_TOOLS) as pool:
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
                raise RuntimeError("Researcher returned no content")

            func_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if hasattr(part, "function_call") and part.function_call
            ]
            if not func_calls:
                output = ResearchOutput(text=_extract_text(response), results=results, scope_label=scope_label)
                _validate_research_output(output)
                return output

            futures = [pool.submit(_run_tool, call) for call in func_calls]
            function_responses = []
            for future in futures:
                tool_name, findings, formatted = future.result()
                results.record_tool_call(tool_name)
                results.extend(findings)
                function_responses.append(
                    types.Part(
                        function_response=types.FunctionResponse(name=tool_name, response={"result": formatted})
                    )
                )

            contents.append(response.candidates[0].content)
            contents.append(types.Content(role="user", parts=function_responses))

    raise RuntimeError("Researcher reached the iteration limit without producing a written synthesis")


def write_brief(topic: str, research_output: ResearchOutput) -> str:
    """Write policy brief from structured findings and researcher synthesis."""
    _validate_research_output(research_output)
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=(
            f"Write a policy brief on: {topic}\n\n"
            f"Scope: {research_output.scope_label}\n\n"
            f"Structured findings:\n{research_output.results.to_text()}\n\n"
            f"Researcher synthesis:\n{research_output.text}"
        ),
        config=types.GenerateContentConfig(system_instruction=WRITER, max_output_tokens=8192),
    )
    return _extract_text(response)


def review(draft: str) -> str:
    """Review and refine the policy brief."""
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=f"Review and refine this policy brief:\n\n{draft}",
        config=types.GenerateContentConfig(system_instruction=REVIEWER, max_output_tokens=8192),
    )
    return _extract_text(response)


def compare_research(topic: str, targets: list[str], questions: list[str] | None = None, verbose: bool = False) -> list[ResearchOutput]:
    """Run research for multiple scopes/targets."""
    outputs = []
    for target in targets:
        if verbose:
            console.print(f"\n[bold]Researching: {target}[/]")
        outputs.append(research(topic, questions, scope_from_target(target), verbose))
    return outputs


def write_comparison(topic: str, outputs: list[ResearchOutput]) -> str:
    """Write comparison brief from multiple research outputs."""
    for output in outputs:
        _validate_research_output(output)

    client = _get_client()
    sections = [
        (
            f"## {output.scope_label.upper()}\n\n"
            f"### Structured findings\n{output.results.to_text()}\n\n"
            f"### Researcher synthesis\n{output.text}"
        )
        for output in outputs
    ]
    combined_sections = "\n\n---\n\n".join(sections)
    response = client.models.generate_content(
        model=MODEL,
        contents=f"Compare policy approaches on: {topic}\n\nResearch by jurisdiction:\n\n{combined_sections}",
        config=types.GenerateContentConfig(system_instruction=COMPARATOR, max_output_tokens=8192),
    )
    return _extract_text(response)
