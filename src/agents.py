"""Policy research agents using Gemini."""

import os

from google import genai
from google.genai import types
from rich.console import Console

from prompts import RESEARCHER, WRITER, REVIEWER
from tools import get_tool_declarations, ToolRegistry

console = Console()

MODEL = "gemini-3-flash-preview"


def _get_client() -> genai.Client:
    """Get configured Gemini client."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set in environment")
    return genai.Client(api_key=api_key)


def _extract_text(response) -> str:
    """Extract text content from Gemini response."""
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
) -> str:
    """Research phase with multiple tools based on scope.

    Args:
        topic: Policy topic to research
        questions: Optional specific research questions
        scope: Research scope dict with 'type' and 'states' keys
        verbose: Print tool calls as they execute

    Returns:
        Synthesized research findings
    """
    client = _get_client()
    scope = scope or {"type": "all", "states": []}

    # Build context
    context = f"Research this policy topic: {topic}"
    if questions:
        context += "\n\nSpecific questions to address:\n"
        context += "\n".join(f"- {q}" for q in questions)

    # Add scope context
    if scope["type"] == "federal":
        context += "\n\nFocus on FEDERAL policy only (Congress, federal agencies)."
    elif scope["type"] == "state":
        states = ", ".join(scope["states"])
        context += f"\n\nFocus on STATE policy only for: {states}"
    else:
        context += "\n\nSearch BOTH federal and state policy sources."

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
            return _extract_text(response)

        # Execute all tools and collect responses
        function_responses = []
        for func_call in func_calls:
            tool_name = func_call.name
            tool_args = dict(func_call.args) if func_call.args else {}

            if verbose:
                console.print(f"  [dim]{tool_name}: {tool_args.get('query', '')}[/]")

            result = tool_registry.execute(tool_name, tool_args)
            function_responses.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=func_call.name,
                        response={"result": result},
                    )
                )
            )

        # Add assistant response and all tool results
        contents.append(response.candidates[0].content)
        contents.append(types.Content(role="user", parts=function_responses))

    return _extract_text(response)


def write_brief(topic: str, research_findings: str) -> str:
    """Write policy brief from research findings.

    Args:
        topic: Policy topic
        research_findings: Output from research phase

    Returns:
        Draft policy brief
    """
    client = _get_client()

    prompt = f"""Write a policy brief on: {topic}

Based on this research:

{research_findings}"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=WRITER,
            max_output_tokens=8192,
        ),
    )

    return _extract_text(response)


def review(draft: str) -> str:
    """Review and refine the policy brief.

    Args:
        draft: Draft policy brief

    Returns:
        Refined final brief
    """
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
