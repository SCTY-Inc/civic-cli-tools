import json
import os
import requests
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from crewai_tools import tool, BaseTool
from datetime import datetime, timedelta
from langchain.chains.summarize import load_summarize_chain
from langchain_community.tools.tavily_search import TavilySearchResults
"""
List of tools available in the search_tools module:
- basic_search: Performs a basic search using Serper.
- search_internet: Searches the internet using SerpApi.
- perplexity_search: Searches the internet using Perplexity.
- you_search: Searches the internet using You Search.
- you_llm_search: Searches the internet using You Search with LLM.
- you_news_search: Searches the internet using You Search with News.
- exa_search: Searches the internet using Exa.
- exa_find_similar: Finds similar links to a given URL using Exa.
- exa_get_content: Retrieves the contents of documents using Exa.
"""
tavily_search = TavilySearchResults(api_key=os.getenv("TAVILY_API_KEY"))


class PerplexityAIChatTool(BaseTool):
  name: str = "Perplexity AI Chat Tool"
  description: str = "Interacts with Perplexity AI's chat model to get responses to user queries."

  def _run(self, user_message: str) -> str:
    """
      Sends a message to the Perplexity AI chat model and returns the model's response.

      Args:
      user_message (str): The user's message/question to send to the chat model.

      Returns:
      str: The chat model's response.
      """
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model":
        "sonar-small-chat",
        "messages": [{
            "role": "system",
            "content": "Be precise and concise."
        }, {
            "role": "user",
            "content": user_message
        }]
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization":
        f"Bearer {os.getenv('PERPLEXITY_API_KEY')}"  # Use environment variable for API key
    }

    try:
      response = requests.post(url, json=payload, headers=headers)
      response.raise_for_status()  # Raises an HTTPError for bad responses
      return response.text  # You might want to parse the JSON response and return a specific field
    except requests.RequestException as e:
      return f"Error: {str(e)}"


@tool("Search Internet with Serper")
def basic_search(query: str, n_results: int = 5) -> str:
  """
    Searches the internet with Serper about a given topic and returns relevant results.
    """
  serper_api_key = os.getenv('SERPER_API_KEY')
  if not serper_api_key:
    raise ValueError("SERPER_API_KEY environment variable not set")

  url = "https://google.serper.dev/search"
  payload = json.dumps({"q": query})
  headers = {'X-API-KEY': serper_api_key, 'content-type': 'application/json'}
  response = requests.post(url, headers=headers, data=payload)
  results = response.json()['organic']
  string = [
      f"Title: {result['title']}\nLink: {result['link']}\nSnippet: {result['snippet']}\n-----------------"
      for result in results[:n_results]
      if 'title' in result and 'link' in result and 'snippet' in result
  ]

  content = '\n'.join(string)
  return f"\nSearch result: {content}\n"


@tool("Search Internet with Serpapi")
def search_internet(query: str) -> str:
  """
    Searches the internet with Serpapi about a given topic and returns relevant results.
    """
  serpapi_api_key = os.getenv('SERPAPI_API_KEY')
  if not serpapi_api_key:
    raise ValueError("SERPAPI_API_KEY environment variable not set")

  url = "https://serpapi.com/search"
  payload = {"q": query, "api_key": serpapi_api_key, "num": 4}
  response = requests.get(url, params=payload)
  results = response.json().get('organic_results', [])

  content = [
      f"Title: {result.get('title')}\nLink: {result.get('link')}\nSnippet: {result.get('snippet')}\n-----------------"
      for result in results
      if result.get('title') and result.get('link') and result.get('snippet')
  ]

  return '\n'.join(content)


@tool("Perplexity Search Tool")
def perplexity_search(user_query: str) -> str:
  """
    Provides detailed AI-generated answers and insights from the Perplexity API.
    """
  api_key = os.getenv("PERPLEXITY_API_KEY")
  client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")

  messages = [
      {
          "role":
          "system",
          "content":
          ("You are an artificial intelligence assistant and you need to "
           "engage in a helpful, detailed, polite conversation with a user."),
      },
      {
          "role": "user",
          "content": user_query,
      },
  ]

  try:
    response = client.chat.completions.create(
        model="sonar-medium-online",
        messages=messages,
    )

    return response.choices[0].message.content
  except Exception as e:
    return f"An error occurred: {str(e)}"


@tool("Retrieve contents of documents based on a list of document IDs.")
def exa_get_content(doc_ids: str) -> str:
  """
    Retrieves the contents of documents from the Exa API based on a list of document IDs.
    """
  url = "https://api.exa.ai/contents"
  payload = {"ids": doc_ids.split(",")}
  headers = {
      "accept": "application/json",
      "content-type": "application/json",
      "x-api-key": os.getenv("EXA_API_KEY")
  }
  response = requests.post(url, json=payload, headers=headers)
  return response.text


@tool(
    "Perform a search with an Exa prompt-engineered query and summarize results."
)
def exa_search(query: str) -> list:
  """
    Performs a search with the Exa API using a prompt-engineered query, retrieves relevant results,
    and summarizes each result using an LLM.
    """
  # Setup for search query
  start_published_date = (datetime.now() +
                          timedelta(days=6 * 30)).strftime('%Y-%m-%d')
  url = "https://api.exa.ai/search"
  payload = {
      "query": query,
      "useAutoprompt": False,
      "num_results": 5,  # Adjust the number of results as needed
      "startPublishedDate": start_published_date,
  }
  headers = {
      "accept": "application/json",
      "content-type": "application/json",
      "x-api-key": os.getenv("EXA_API_KEY")
  }

  # Perform search
  response = requests.post(url, json=payload, headers=headers)
  if response.status_code == 200:
    search_results = response.json().get('results', [])

    # Initialize summarization results list
    summarized_results = []

    # Process and summarize each search result
    for result_item in search_results:
      # Replace the following lines with your actual summarization logic
      llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo-0125")
      chain = load_summarize_chain(
          llm, chain_type="stuff")  # Adjust 'chain_type' as necessary
      summarized_text = chain.run(
          result_item['text'])  # Assuming 'text' field exists and is relevant

      summarized_results.append({
          'original_text': result_item['text'],
          'summarized_text': summarized_text
      })

    return summarized_results
  else:
    return [{"error": "Failed to fetch search results"}]


@tool("Find similar links to the provided URL.")
def exa_find_similar(url: str) -> str:
  """
    Finds similar links to the provided URL using the Exa API.
    """
  api_url = "https://api.exa.ai/findSimilar"
  payload = {
      "url": url
      # Removed any date-related filtering from the payload
  }
  headers = {
      "accept": "application/json",
      "content-type": "application/json",
      "x-api-key": os.getenv("EXA_API_KEY")
  }
  response = requests.post(api_url, json=payload, headers=headers)
  return response.text


@tool("Tavily Comprehensive Search Tool")
def tavily_search_tool(query: str) -> str:
  """
    Performs a search using the Tavily API and returns a comprehensive summary of results.
    - query: The search query string.
    
    This tool encapsulates the functionality to query the Tavily search engine, tailored for AI agent use.
    """
  results = tavily_search.invoke({"query": query})
  summaries = [
      f"URL: {result['url']}\nContent: {result['content'][:150]}..."
      for result in results
  ]
  return "\n\n".join(summaries)
