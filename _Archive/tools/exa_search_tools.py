import os
import textwrap
import requests
import json
from datetime import datetime, timedelta
from crewai_tools import BaseTool  # Assuming crewai_tools is the correct import for your BaseTool class
from exa_py import Exa  # Ensure exa_py is correctly installed and accessible

exa = Exa(api_key=os.environ["EXA_API_KEY"])

class ExaSearchTool(BaseTool):
    name: str = "Exa Search Tool"
    description: str = "Performs internet searches using natural language queries with Exa."

    def _run(self, query: str, include_domains: list = None, start_published_date: str = None) -> str:
        results = exa.search(
            query=query, 
            use_autoprompt=True,
            num_results=5, 
            include_domains=include_domains, 
            start_published_date=start_published_date)
        return str(results)

class ExaFindSimilarTool(BaseTool):
    name: str = "Exa Find Similar Tool"
    description: str = "Finds pages similar to a given URL using Exa."

    def _run(self, url: str, num_results: int = 5) -> str:
        similar_results = exa.find_similar(url=url, num_results=num_results)
        return str(similar_results)

class ExaGetContentsTool(BaseTool):
    name: str = "Exa Get Contents Tool"
    description: str = "Retrieves cleaned HTML content for a set of document IDs using Exa."

    def _run(self, ids: list) -> str:
        contents = exa.get_contents(ids=ids)
        return str(contents)

class ExaSearchAndContentsTool(BaseTool):
    name: str = "Exa Search and Contents Tool"
    description: str = "Searches for content with Exa and retrieves contents with specific options."
    
    def _run(self, search_query: str, highlight_query: str) -> str:
        search_response = exa.search_and_contents(
            search_query, 
            text={"include_html_tags": True, "max_characters": 1000}, 
            highlights={"highlights_per_url": 2, "num_sentences": 1, "query": highlight_query}
        )
        if hasattr(search_response, 'to_dict'):
            serializable_response = search_response.to_dict()
        else:
            serializable_response = {
                'results': [{
                    'url': result.url,
                    'title': result.title,
                    'text': result.text,
                    # Include other relevant fields
                } for result in search_response.results]
            }
        return json.dumps(serializable_response, ensure_ascii=False)