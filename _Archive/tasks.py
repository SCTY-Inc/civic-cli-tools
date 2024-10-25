from textwrap import dedent
from crewai import Task
from typing import List
from pydantic import BaseModel, Field


class PolicyResearch(BaseModel):
    policy_topic: str
    research_questions: List[str] = Field(
        ..., description="Specific research questions guiding the investigation")
    current_status: List[str] = Field(
        ...,
        description="Overview of the policy's current status and relevant debates"
    )
    stakeholder_perspectives: List[str] = Field(
        ...,
        description="Analysis of different stakeholders' views and opinions")
    evidence_base: List[str] = Field(
        ...,
        description="Empirical evidence supporting various positions on the policy")
    key_findings: List[str] = Field(
        ...,
        description="Summary of key insights and divergent viewpoints identified through research"
    )
    url_citation: List[str] = Field(
        ...,
        description="URLs linking to sources that provide additional information or evidence supporting the key findings"
    )


class PolicyTasks:
    def research_policy(self, agent, policy_topic: str, research_questions: List[str]):
        if isinstance(research_questions, str):
            research_questions = [research_questions]  # Encapsulate it in a list
        research_questions = [str(q).strip() for q in research_questions]

        return Task(
            description=dedent(f"""
                **Research Policy Issues**
                - **Policy Topic**: {policy_topic}
                - **Research Questions**: {', '.join(research_questions)}
                Conduct a comprehensive investigation on the current status, debates, and evidence related to the policy topic. 
                Analyze stakeholder perspectives and empirical evidence to formulate a detailed report.
            """),
            expected_output=dedent("""
                **Executive Summary**: Overview highlighting the urgency, challenges, and preliminary recommendations.
                **Current Status & Background**: Brief on the policy's present scenario and debates.
                **Stakeholder Perspectives**: Summary of key stakeholder viewpoints.
                **Evidence Base & Key Findings**: 
                - Empirical evidence points.
                - Critical insights from the research.
                - URL citation
            """),
            agent=agent,
            output_pydantic=PolicyResearch,
        )

    def analyze_policy(self, agent, policy_topic):
        return Task(
            description=dedent(f"""
                Based on the research conducted, analyze potential policy options for {policy_topic}. 
                Evaluate the pros and cons of each option, considering effectiveness, feasibility, and potential impact. 
                Develop a set of evidence-based policy recommendations that align with policy objectives and societal needs.
            """),
            expected_output=dedent("""
                - **Introduction**: Presentation of the policy options.
                - **Stats**: Key figures and stats.
                - **Analysis of Policy Options**:
                  - **Policy Option 1**: Pros and Cons.
                  - **Policy Option 2**: Pros and Cons.
                - **Recommendations**: 
                  - Bullet points of actionable recommendations with brief rationales.
                - **Citation**: 
                  - URL citation of source.
            """),
            agent=agent,
        )

    def draft_brief(self, agent, policy_topic, recommendations_summary):
        return Task(
            description=dedent(f"""
                Draft a policy brief for {policy_topic} using the research findings and policy recommendations. 
                Start with an executive summary that encapsulates the issue and recommendations, followed by a detailed discussion on the policy context, analysis, and proposed recommendations. 
                Ensure the brief is concise, engaging, and persuasive, tailored to inform and influence policy stakeholders.
                Summary of recommendations: {recommendations_summary}
            """),
            expected_output=dedent(f"""
                ## Policy Brief on {policy_topic}
                **Executive Summary**: 
                  - Highlights key points, challenges, and recommendations related to {policy_topic}.
                  - **Citations**:
                    - ["Title of Source Article," Author, Publication Date](URL)
                **Current Status**: 
                  - Information on the current legislative or policy status concerning {policy_topic}.
                  - **Citations**:
                    - ["Title of Source Article," Author, Publication Date](URL)
                **Background and Context**: 
                  - An overview of the issue underlying {policy_topic}.
                  - **Citations**:
                    - ["Title of Source Article," Author, Publication Date](URL)
                **Analysis of the Issue**: 
                - A detailed examination of the main challenges related to {policy_topic}.
                - **Citations**:
                    - ["Title of Source Article," Author, Publication Date](URL)
                **Opportunities for Improvement**: 
                - Outlines potential avenues for positive change within {policy_topic}.
                - **Citations**:
                    - ["Title of Source Article," Author, Publication Date](URL)
                **Proposed Solutions and Recommendations**: 
                - Lists detailed action plans or policy recommendations for {policy_topic}.
                - **Citations**:
                    - ["Title of Source Article," Author, Publication Date](URL)
                **Conclusion and Call to Action**: 
                - A summary urging action on {policy_topic}.
                - **Citations**:
                    - ["Title of Source Article," Author, Publication Date](URL)
                **Unanswered Questions and Likelihood of Passage**: 
                - Insights into unresolved aspects and policy success chances.
                - **Citations**:
                    - ["Title of Source Article," Author, Publication Date](URL)
                **Recent News or Events**: 
                - The latest relevant developments related to {policy_topic}.
                - **Citations**:
                    - ["Title of Source Article," Author, Publication Date](URL)
            """),
            agent=agent,
        )

    def review_brief(self, agent, policy_topic):
        return Task(
            description=dedent(f"""
                **Review and Refine Policy Brief on {policy_topic}**
                You are tasked with reviewing a draft policy brief related to {policy_topic}. This document is critical for influencing policy and must be clear, concise, and compelling. 
                **Your objectives are:**
                - Ensure the brief is coherent, presenting a logical flow of ideas.
                - Confirm the document is concise, avoiding unnecessary details while covering all critical aspects of the policy.
                - Verify the brief effectively communicates the policy analysis and recommendations.
                - Check for clarity and accuracy in the presentation of data and arguments.
                - Align the brief with policy advocacy goals, ensuring it persuades and motivates action.
                - Incorporate any necessary feedback for improvements to enhance persuasiveness and impact.
                **Your deliverables are:**
                - A final version of the policy brief, revised based on the above objectives.
            """),
            expected_output=dedent(f"""
                ## Policy Brief on {policy_topic}
                **Executive Summary**: 
                  - Highlights key points, challenges, and recommendations related to {policy_topic}.
                  - **Citations**:
                    - [Title of Source Article, Author, Publication Date](URL)
                **Current Status**: 
                  - Information on the current legislative or policy status concerning {policy_topic}.
                  - **Citations**:
                    - [Legislation on {policy_topic}, Government Department or Body](URL)
                **Background and Context**: 
                  - An overview of the issue underlying {policy_topic}.
                  - **Citations**:
                    - [Historical Context of {policy_topic}, Author, Publication](URL)
                **Analysis of the Issue**: 
                - A detailed examination of the main challenges related to {policy_topic}.
                - **Citations**:
                  - [Challenges Facing {policy_topic}, Expert Name, Think Tank or Research Institute](URL)
                **Opportunities for Improvement**: 
                - Outlines potential avenues for positive change within {policy_topic}.
                - **Citations**:
                  - [Innovations in {policy_topic}, Innovator or Researcher Name, Date](URL)
                **Proposed Solutions and Recommendations**: 
                - Lists detailed action plans or policy recommendations for {policy_topic}.
                - **Citations**:
                  - [Policy Solutions for {policy_topic}, Policy Analyst or Expert, Date](URL)
                **Conclusion and Call to Action**: 
                - A summary urging action on {policy_topic}.
                - **Citations**:
                  - [The Urgency of Action on {policy_topic}, Influential Figure or Organization](URL)
                **Unanswered Questions and Likelihood of Passage**: 
                - Insights into unresolved aspects and policy success chances.
                - **Citations**:
                  - [Forecasting Policy Outcomes for {policy_topic}, Forecaster Name, Publication Date](URL)
                **Recent News or Events**: 
                - The latest relevant developments related to {policy_topic}.
                - **Citations**:
                  - [Breaking News on {policy_topic}, News Source, Date](URL)
            """),
            agent=agent,
        )
