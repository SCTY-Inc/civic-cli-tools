import json
import os
import praw
import time
import requests
from crewai import Agent, Task
from langchain.tools import tool
from unstructured.partition.html import partition_html

from langchain_community.llms import Ollama

class BrowserTools():

  @tool("Scrape website content")
  def scrape_and_summarize_website(website):
    """Useful to scrape and summarize a website content, just pass a string with
    only the full url, no need for a final slash `/`, eg: https://google.com or https://clearbit.com/about-us"""
    url = f"https://chrome.browserless.io/content?token={os.environ['BROWSERLESS_API_KEY']}"
    payload = json.dumps({"url": website})
    headers = {'cache-control': 'no-cache', 'content-type': 'application/json'}
    response = requests.request("POST", url, headers=headers, data=payload)
    elements = partition_html(text=response.text)
    content = "\n\n".join([str(el) for el in elements])
    content = [content[i:i + 8000] for i in range(0, len(content), 8000)]
    summaries = []
    for chunk in content:
      agent = Agent(
          role='Principal Researcher',
          goal=
          'Do amazing researches and summaries based on the content you are working with',
          backstory=
          "You're a Principal Researcher at a big company and you need to do a research about a given topic.",
          llm=Ollama(model=os.environ['MODEL']),
          allow_delegation=False)
      task = Task(
          agent=agent,
          description=
          f'Analyze and make a LONG summary the content bellow, make sure to include the ALL relevant information in the summary, return only the summary nothing else.\n\nCONTENT\n----------\n{chunk}'
      )
      summary = task.execute()
      summaries.append(summary)
      content = "\n\n".join(summaries)
    return f'\nScrapped Content: {content}\n'

  @tool("Scrape reddit content")
  def scrape_reddit(max_comments_per_post=7):
    """Useful to scrape reddit content"""
    reddit = praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent=os.getenv('REDDIT_USER_AGENT'),
        username=os.getenv('REDDIT_USER_NAME'),
        password=os.getenv('REDDIT_PASSWORD'),
    )
    subreddit = reddit.subreddit("MachineLearning")
    scraped_data = []

    for post in subreddit.hot(limit=12):
        post_data = {"title": post.title, "url": post.url, "comments": []}

        try:
            post.comments.replace_more(limit=0)  # Load top-level comments only
            comments = post.comments.list()
            if max_comments_per_post is not None:
                comments = comments[:7]

            for comment in comments:
                post_data["comments"].append(comment.body)

            scraped_data.append(post_data)

        except praw.exceptions.APIException as e:
            print(f"API Exception: {e}")
            time.sleep(60)  # Sleep for 1 minute before retrying

    return scraped_data
