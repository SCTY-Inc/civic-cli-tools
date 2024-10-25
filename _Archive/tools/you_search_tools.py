import os
import requests
from langchain.tools import tool
from crewai_tools import BaseTool
from langchain_community.utilities.you import YouSearchAPIWrapper

#you_api_key = os.getenv("YOU_API_KEY")


class AISnippetsSearchTool(BaseTool):
  name: str = "AI Snippets Search Tool"
  description: str = "Searches and returns AI-generated snippets for a given query using the YDC Index API."

  def _run(self, query: str) -> str:
    """
      Executes the search query against the YDC Index API and returns the results.
      """
    # Assuming YOUR_API_KEY is stored in an environment variable for security reasons
    your_api_key = os.getenv('YOUR_API_KEY')
    headers = {"X-API-Key": your_api_key}
    params = {"query": query}
    try:
      response = requests.get(
          f"https://api.ydc-index.io/search",
          params=params,
          headers=headers,
      )
      response.raise_for_status(
      )  # Ensure we only proceed if the request was successful
      results = response.json()

      # Format the results into a string to return
      snippets = []
      for result in results.get('documents',
                                []):  # Assuming the results are in 'documents'
        title = result.get('title', 'No title')
        snippet = result.get('snippet', 'No snippet available')
        snippets.append(f"Title: {title}\nSnippet: {snippet}\n")

      return "\n".join(snippets) if snippets else "No results found."
    except requests.RequestException as e:
      return f"Error: {str(e)}"


"""
List of tools available in the you_search_tools module:
- you_search: Searches the internet using You Search.
- summarize_you_searches: Summarizes the top 'num_results' results from a You Search query.
- fetch_raw_you_com_search_results: Fetches raw search results from You.com for a given query.
- you_search_ai_snippets: Searches and returns AI-generated information for a query.
- you_llm_search: Searches the internet using You Search with LLM.
- you_news_search: Searches the internet using You Search with News.
"""


@tool("You Search API Wrapper")
def you_search_wrapper(query: str,
                       fetch_raw: bool = False,
                       num_results: int = 1) -> str:
  """
    A versatile search tool using You.com API wrapper.
    - query: The search query string.
    - fetch_raw: If True, fetches and returns raw search results.
    - num_results: Specifies the number of search results to return.
    
    Returns a string containing either raw JSON (if fetch_raw is True) or summarized results.
    """
  utility = YouSearchAPIWrapper(you_api_key, num_web_results=num_results)
  if fetch_raw:
    return str(utility.raw_results(query=query))
  else:
    results = utility.results(query=query)
    summaries = [
        f"Title: {result.metadata['title']}\nURL: {result.metadata['url']}"
        for result in results
    ]
    return "\n\n".join(summaries)


@tool("Summarize You Search Results")
def you_summarize(query: str, num_results: int) -> str:
  """
    Performs a search on You.com for a given query and summarizes the top 'num_results' results.
    Returns a string containing titles and URLs of the top results.
    """
  utility = YouSearchAPIWrapper(num_web_results=num_results)
  results = utility.results(query=query)
  summaries = [
      f"Title: {result.metadata['title']}\nURL: {result.metadata['url']}"
      for result in results
  ]
  return "\n\n".join(summaries)


@tool("Fetch You Search Results")
def you_fetch_raw(query: str) -> str:
  """
    Fetches raw search results from You.com for a given query.
    Returns the raw JSON response as a string.
    """
  utility = YouSearchAPIWrapper(
      num_web_results=10)  # Example: Fetching 10 results
  raw_results = utility.raw_results(query=query)
  return str(raw_results)


@tool("You Search AI Snippets")
def you_search(query: str) -> list:
  """
    Searches and returns AI-generated information for a query using the YDC Index API. 
    """
  you_api_key = os.getenv('YOU_API_KEY')
  headers = {"X-API-Key": you_api_key}
  try:
    response = requests.get(
        f"https://api.ydc-index.io/news",
        params={"q": query},
        headers=headers,
    )
    response.raise_for_status()  # Raises an error for bad responses
    json_response = response.json()

    # Parsing the JSON response
    results = json_response.get('news', {}).get('results', [])
    parsed_results = []

    for result in results:
      title = result.get('title')
      description = result.get('description')
      url = result.get('url')

      if title and description and url:
        parsed_results.append({
            'title': title,
            'description': description,
            'url': url
        })

    return parsed_results
  except requests.RequestException as e:
    return [{"error": str(e)}]


@tool("You Search Web RAG Snippets")
def you_llm_search(query: str) -> str:
  """
    Searches and returns the raw AI-generated information for a query using the YDC Index RAG API as a text string.
    """
  you_api_key = os.getenv('YOU_API_LLM_KEY')
  headers = {"X-API-Key": you_api_key}
  params = {"query": query, "num_web_results": "10"}

  url = "https://api.ydc-index.io/rag"
  response = requests.get(url, headers=headers, params=params)
  response.raise_for_status()  # Raises an error for bad responses

  return response.text


@tool
def you_news_search(query: str) -> str:
  """
    Searches and returns summarized AI-generated news articles for a query using the YDC Index News API.
    The articles are first fetched and then summarized to provide a concise overview.
    """
  you_api_key = os.getenv(
      'YOU_API_KEY')  # Ensure you have set this environment variable correctly
  headers = {"X-API-Key": you_api_key}
  querystring = {"q": query}  # Define the query string with the search query

  url = "https://api.ydc-index.io/news"
  response = requests.request("GET", url, headers=headers, params=querystring)
  response.raise_for_status(
  )  # This will raise an HTTPError if the response is an error status code

  search_results = response.json()['news'][
      'results']  # Adjusted to match the given schema
  summarized_results = []

  for result_item in search_results:
    # Placeholder for summarization logic. This is where you'd integrate actual summarization functionality.
    # For the purpose of this example, we're using a placeholder text.
    summarized_text = "Summarized text placeholder"  # Replace with actual summarization logic

    summarized_results.append({
        'title':
        result_item['title'],
        'original_description':
        result_item['description'],
        'summarized_text':
        summarized_text,
        'url':
        result_item['url'],
        'thumbnail':
        result_item['thumbnail']['original']
    })

  # Convert the summarized results to a string format suitable for your needs
  # Here's a simple example of formatting the output
  output = ""
  for item in summarized_results:
    output += f"Title: {item['title']}\nOriginal Description: {item['original_description']}\nSummarized: {item['summarized_text']}\nURL: {item['url']}\nThumbnail: {item['thumbnail']}\n\n"

  return output
