# -*- coding: utf-8 -*-
"""
Task definitions for the materials science research crew.

This module defines four tasks corresponding to the four agents:
1. Literature Mining - Search and summarize relevant literature
2. Hypothesis Generation - Formulate research hypotheses from findings
3. Validation - Cross-validate hypotheses against known data
4. Report Generation - Compile results into structured reports
"""

from crewai import Task
from typing import Optional, Dict, Any


def create_literature_mining_task(
    agent, 
    topic: str,
    context: Optional[Dict[str, Any]] = None
) -> Task:
    """Create the literature mining task.
    
    This task instructs the Miner Agent to:
    - Search for literature on the given topic
    - Extract key findings, authors, and methodologies
    - Provide a structured summary of relevant papers
    - Identify gaps or contradictions in the literature
    
    Args:
        agent: The CrewAI agent to execute this task
        topic: The materials science topic to search for
        context: Optional context dictionary
        
    Returns:
        A CrewAI Task object for literature mining
    """
    return Task(
        description=f"""Conduct a comprehensive literature search on the topic: "{topic}"
        
        Your task:
        1. Identify 5-10 most relevant scientific papers on this topic
        2. For each paper, extract:
           - Title, authors, and publication year
           - Key findings and contributions
           - Methodology used
           - Limitations or concerns
        3. Synthesize the common themes and trends
        4. Identify knowledge gaps or unresolved questions
        
        Output format:
        ## Literature Summary: {topic}
        
        ### Key Papers
        [List of papers with details]
        
        ### Common Findings
        [Synthesis of main themes]
        
        ### Research Gaps
        [Identified gaps for future research]
        """,
        agent=agent,
        expected_output="A comprehensive literature summary with key papers, findings, and research gaps"
    )


def create_hypothesis_generation_task(
    agent,
    topic: str,
    context: Optional[Dict[str, Any]] = None
) -> Task:
    """Create the hypothesis generation task.
    
    This task instructs the Generator Agent to:
    - Review the literature findings
    - Identify patterns and connections
    - Formulate novel, testable hypotheses
    - Propose experimental approaches
    
    Args:
        agent: The CrewAI agent to execute this task
        topic: The research topic
        context: Contains literature_mining_results from previous task
        
    Returns:
        A CrewAI Task object for hypothesis generation
    """
    literature_context = context.get("literature_results", "No literature data available") if context else "No literature data available"
    
    return Task(
        description=f"""Based on the following literature findings, generate novel research hypotheses:

        Literature Data:
        {literature_context}
        
        Your task:
        1. Analyze the literature to identify patterns and trends
        2. Formulate 3-5 specific, testable research hypotheses
        3. For each hypothesis, provide:
           - A clear statement of the hypothesis
           - Theoretical justification based on the literature
           - Proposed experimental approach to test it
           - Potential impact if validated
        4. Rank hypotheses by novelty and feasibility
        
        Output format:
        ## Research Hypotheses
        
        ### Hypothesis 1: [Title]
        - Statement: [Clear hypothesis statement]
        - Justification: [Theoretical basis]
        - Experimental Approach: [How to test]
        - Potential Impact: [Scientific significance]
        
        [Repeat for additional hypotheses]
        """,
        agent=agent,
        expected_output="3-5 ranked research hypotheses with justification and experimental approaches"
    )


def create_validation_task(
    agent,
    context: Optional[Dict[str, Any]] = None
) -> Task:
    """Create the validation task.
    
    This task instructs the Validator Agent to:
    - Cross-reference hypotheses with known data
    - Assess feasibility and potential challenges
    - Assign confidence scores
    - Identify necessary controls
    
    Args:
        agent: The CrewAI agent to execute this task
        context: Contains hypothesis_results from previous task
        
    Returns:
        A CrewAI Task object for hypothesis validation
    """
    hypothesis_context = context.get("hypothesis_results", "No hypothesis data available") if context else "No hypothesis data available"
    
    return Task(
        description=f"""Validate the proposed research hypotheses against known experimental data.

        Hypotheses to Validate:
        {hypothesis_context}
        
        Your task:
        1. For each hypothesis, evaluate:
           - Consistency with existing experimental data
           - Potential confounding factors or alternative explanations
           - Feasibility of proposed experimental approach
           - Resource requirements (time, equipment, expertise)
        2. Assign a confidence score (1-10) to each hypothesis
        3. Identify any additional experiments or controls needed
        4. Provide recommendations for prioritization
        
        Output format:
        ## Validation Results
        
        ### Hypothesis 1: [Title]
        - Validation Status: [Supported / Partial / Contradicted]
        - Confidence Score: [1-10]
        - Supporting Evidence: [References to existing data]
        - Concerns: [Potential issues or limitations]
        - Recommended Additional Experiments: [If any]
        
        ### Overall Assessment
        [Summary and prioritization recommendations]
        """,
        agent=agent,
        expected_output="Validation results with confidence scores and recommendations"
    )


def create_report_task(
    agent,
    context: Optional[Dict[str, Any]] = None
) -> Task:
    """Create the report generation task.
    
    This task instructs the Reporter Agent to:
    - Compile all findings into a structured report
    - Ensure proper scientific writing standards
    - Include visualizations and summaries
    - Provide clear conclusions and recommendations
    
    Args:
        agent: The CrewAI agent to execute this task
        context: Contains all previous task results
        
    Returns:
        A CrewAI Task object for report generation
    """
    # Compile all context from previous tasks
    literature = context.get("literature_results", "N/A") if context else "N/A"
    hypotheses = context.get("hypothesis_results", "N/A") if context else "N/A"
    validation = context.get("validation_results", "N/A") if context else "N/A"
    
    return Task(
        description=f"""Compile all research findings into a comprehensive scientific report.

        ## Literature Summary:
        {literature}
        
        ## Research Hypotheses:
        {hypotheses}
        
        ## Validation Results:
        {validation}
        
        Your task:
        1. Create a well-structured research report with the following sections:
           - Executive Summary
           - Introduction and Background
           - Literature Review
           - Proposed Hypotheses
           - Validation Analysis
           - Conclusions and Recommendations
           - References
        2. Ensure all content is scientifically accurate and properly cited
        3. Highlight key findings and their significance
        4. Provide actionable recommendations for future research
        
        Output format:
        # Research Report: [Topic]
        
        ## Executive Summary
        [2-3 paragraph overview]
        
        [Continue with all sections above]
        """,
        agent=agent,
        expected_output="A comprehensive Markdown report with all research findings"
    )


# ============================================================================
# Task Factory Functions (for direct instantiation)
# ============================================================================

def literature_mining_task(agent, **kwargs) -> Task:
    """Factory function for literature mining task."""
    return create_literature_mining_task(agent, **kwargs)


def hypothesis_generation_task(agent, **kwargs) -> Task:
    """Factory function for hypothesis generation task."""
    return create_hypothesis_generation_task(agent, **kwargs)


def validation_task(agent, **kwargs) -> Task:
    """Factory function for validation task."""
    return create_validation_task(agent, **kwargs)


def report_task(agent, **kwargs) -> Task:
    """Factory function for report task."""
    return create_report_task(agent, **kwargs)
