import streamlit as st
from crewai import Crew
from tasks import PolicyTasks
from agents import PolicyAgents


def icon(emoji: str):
  """Shows an emoji as a Notion-style page icon."""
  st.write(f'<span style="font-size: 78px; line-height: 1">{emoji}</span>',
           unsafe_allow_html=True)


class PolicyCrew:

  def __init__(self, policy_topic, research_questions,
               recommendations_summary):
    self.policy_topic = policy_topic
    self.research_questions = research_questions
    self.recommendations_summary = recommendations_summary
    self.output_placeholder = st.empty()

  def run(self):
    agents = PolicyAgents()
    tasks = PolicyTasks()

    researcher_agent = agents.research_agent()
    writer_agent = agents.writer_agent()
    review_agent = agents.review_agent()

    research_policy_task = tasks.research_policy(researcher_agent,
                                                 self.policy_topic,
                                                 self.research_questions)
    analyze_policy_options_task = tasks.analyze_policy(researcher_agent,
                                                       self.policy_topic)
    draft_policy_brief_task = tasks.draft_brief(writer_agent,
                                                self.policy_topic,
                                                self.recommendations_summary)
    review_and_refine_policy_brief_task = tasks.review_brief(
        review_agent, self.policy_topic)

    crew = Crew(agents=[researcher_agent, writer_agent, review_agent],
                tasks=[
                    research_policy_task, analyze_policy_options_task,
                    draft_policy_brief_task,
                    review_and_refine_policy_brief_task
                ],
                verbose=False)

    result = crew.kickoff()
    self.output_placeholder.markdown(result)
    return result


if __name__ == "__main__":
  icon("⚖️ Policy Research")
  st.subheader("Exploring and Shaping Public Policy Initiatives",
               divider="rainbow",
               anchor=False)

  with st.sidebar:
    st.header("📜 Enter Policy Details")
    with st.form("policy_form"):
      policy_topic = st.text_input(
          "Policy area of interest:",
          placeholder="E.g., Solar energy policy in Michigan")
      research_questions = st.text_input(
          "Specific research questions:",
          placeholder=
          "E.g., What are the current barriers to solar energy adoption?")
      recommendations_summary = st.text_input(
          "Summary of policy recommendations:",
          placeholder=
          "E.g., Incentives for solar installation, streamlined permitting process"
      )
      submitted = st.form_submit_button(label='Start Research')
    st.divider()

  st.sidebar.markdown("""
        Source code on [**Github**](https://github.com/amadad/civic-agentcy)<br>
        Created by [**@amadad**](https://twitter.com/amadad)
        """,
                      unsafe_allow_html=True)

  if submitted:
    with st.status("🌐 **Policy Analysis in Progress...**",
                   state="running",
                   expanded=True) as status:
      with st.container(height=500, border=False):
        policy_crew = PolicyCrew(policy_topic, research_questions,
                                 recommendations_summary)
        result = policy_crew.run()
      status.update(label="✅ Policy Analysis Ready!",
                    state="complete",
                    expanded=False)
    st.subheader("Here is your Policy Brief", anchor=False, divider="rainbow")
    st.markdown(result)
