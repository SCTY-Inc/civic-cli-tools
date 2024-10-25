from dotenv import load_dotenv
from crewai import Crew, Agent, Task
from tools.search_tools import basic_search, search_internet, perplexity_search, tavily_search
from tools.exa_search_tools import ExaSearchAndContentsTool, ExaRecentNewsTool
from tools.you_search_tools import you_search_wrapper, you_summarize, you_fetch_raw, you_search, you_llm_search, you_news_search

# Define a query
query = "Ranked choice voting barriers to the adoption of ranked choice voting in Michigan"

# Map of tool names to their functions and descriptions
tool_map = {
    #'Basic Search': basic_search,
    #'Internet Search': search_internet,
    #'Perplexity Search': perplexity_search,
    #'Tavily Search': tavily_search,
    #'Exa Search': exa_search,
    'Exa Recent News': ExaRecentNewsTool(),
    #'Exa Search and Contents': ExaSearchAndContentsTool(),
    #'Exa Find Similar': exa_find_similar,
    #'Exa Get Contents': exa_get_contents,
    #'You Search': you_search_wrapper,
    #'You Summarize': you_summarize,
    #'You Fetch Raw': you_fetch_raw,
    #'You Search': you_search,
    #'You LLM Search': you_llm_search,
    #'You News Search': you_news_search,
}

# Function to create an agent and task dynamically
def create_agent_and_task(tool_name, tool_function):
    agent = Agent(
        role=f'{tool_name}',
        goal=f'Perform a {tool_name.lower()}',
        tools=[tool_function],
        allow_delegation=False,
        backstory='Responsible for conducting recent and relevant searches to gather information.',
        verbose=True
    )
    task = Task(
        description=f"Conduct an extensive search on \"{query}\". The goal is to cover a wide array of sources to find comprehensive information and perspectives related to the query.",
        expected_output="A detailed report of findings from the internet search, highlighting significant discoveries, data points, and analysis related to the query.",
        agent=agent,
        output_file=f"test/{tool_name.lower().replace(' ', '_')}_output.md",
    )
    return agent, task

agents = []
tasks = []

# Iterate over tool_map to create agents and tasks dynamically
for tool_name, tool_function in tool_map.items():
    agent, task = create_agent_and_task(tool_name, tool_function)
    agents.append(agent)
    tasks.append(task)

# Initialize Crew with dynamic agents and tasks
crew = Crew(agents=agents, tasks=tasks)

# Kickoff Crew and capture results
results = crew.kickoff()
print(results)
