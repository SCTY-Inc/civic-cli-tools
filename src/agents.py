"""Policy research agents using Gemini."""

import os

from google import genai
from google.genai import types
from rich.console import Console

from prompts import RESEARCHER, WRITER, REVIEWER
from tools import web_search, get_search_declaration

console = Console()

MODEL = "gemini-2.5-flash-preview-05-20"


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


def research(topic: str, questions: list[str] | None = None, verbose: bool = False) -> str:
    """Research phase with web search tool.

    Args:
        topic: Policy topic to research
        questions: Optional specific research questions
        verbose: Print search queries as they execute

    Returns:
        Synthesized research findings
    """
    client = _get_client()

    context = f"Research this policy topic: {topic}"
    if questions:
        context += f"\n\nSpecific questions to address:\n"
        context += "\n".join(f"- {q}" for q in questions)

    contents = [types.Content(role="user", parts=[types.Part(text=context)])]
    tools = [types.Tool(function_declarations=[get_search_declaration()])]

    max_iterations = 10
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

        # Check for function calls
        func_call = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, "function_call") and part.function_call:
                func_call = part.function_call
                break

        if not func_call:
            return _extract_text(response)

        # Execute search
        query = func_call.args.get("query", "")
        if verbose:
            console.print(f"  [dim]Searching: {query}[/]")

        result = web_search.execute(query)

        # Add assistant response and tool result to conversation
        contents.append(response.candidates[0].content)
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=func_call.name,
                            response={"result": result},
                        )
                    )
                ],
            )
        )

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
