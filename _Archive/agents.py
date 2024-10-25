import os
import streamlit as st
from crewai import Agent
from tools.search_tools import basic_search, PerplexityAIChatTool
from tools.you_search_tools import AISnippetsSearchTool
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic

you_search_tool = AISnippetsSearchTool()
pplx = PerplexityAIChatTool()


def streamlit_callback(step_output):
  """Callback function to display step output in Streamlit."""
  st.markdown("---")
  for step in step_output:
    if isinstance(step, tuple) and len(step) == 2:
      action, observation = step
      if isinstance(
          action, dict
      ) and "tool" in action and "tool_input" in action and "log" in action:
        st.markdown(f"# Action")
        st.markdown(f"**Tool:** {action['tool']}")
        st.markdown(f"**Tool Input:** {action['tool_input']}")
        st.markdown(f"**Log:** {action['log']}")
        if 'Action' in action:  # Check if 'Action' key exists before using it
          st.markdown(f"**Action:** {action['Action']}")
        st.markdown(f"**Action Input:** ```json\n{action['tool_input']}\n```")
      elif isinstance(action, str):
        st.markdown(f"**Action:** {action}")
      else:
        st.markdown(f"**Action:** {str(action)}")

      st.markdown(f"**Observation**")
      if isinstance(observation, str):
        observation_lines = observation.split('\n')
        for line in observation_lines:
          st.markdown(line)
      else:
        st.markdown(str(observation))
    else:
      st.markdown(step)


class PolicyAgents():

  def __init__(self):
    self.llm = ChatGroq(  #api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.1-70b-versatile")
    #model="llama3-8b-8192")
    #anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    #self.llm = ChatAnthropic(anthropic_api_key=anthropic_api_key,
    #                         model_name="claude-3-haiku-20240307")

  def research_agent(self):
    return Agent(
        role='Policy Researcher',
        goal=
        'Investigate current policy issues, trends, and evidence through comprehensive web and database searches to gather relevant data and insights.',
        tools=[basic_search],
        backstory=
        'An expert in navigating complex policy landscapes to extract critical data and insights from a multitude of sources.',
        verbose=True,
        llm=self.llm,
        step_callback=streamlit_callback,
        allow_delegation=False,
        max_iter=3,
    )

  def writer_agent(self):
    return Agent(
        role='Policy Writer',
        goal=
        'Use insights from the Policy Researcher to create a detailed, engaging, and impactful policy brief.',
        tools=[basic_search],
        backstory=
        'Skilled in crafting impactful policy briefs that articulate insights, key trends, and evidence-based recommendations.',
        verbose=True,
        llm=self.llm,
        allow_delegation=False,
        step_callback=streamlit_callback,
        max_iter=5,
    )

  def review_agent(self):
    return Agent(
        role='Policy Brief Reviewer',
        goal=
        'Critically review the draft policy brief for coherence, alignment with policy objectives, evidence strength, and persuasive clarity. Refine content to ensure high-quality, impactful communication.',
        #tools=[basic_search],
        backstory=
        'A meticulous reviewer with a keen understanding of policy advocacy, ensuring each brief is clear, compelling, and grounded in solid evidence.',
        verbose=True,
        llm=self.llm,
        allow_delegation=False,
        step_callback=streamlit_callback,
        max_iter=5,
    )
