# -*- coding: utf-8 -*-
"""
Agent definitions for the materials science research crew.

This module defines four specialized agents:
1. MinerAgent - Literature mining from academic databases
2. GeneratorAgent - Research hypothesis generation
3. ValidatorAgent - Data validation against known results
4. ReporterAgent - Structured report generation
"""

from crewai import Agent
from litellm import completion
import yaml
import os
from typing import Optional, Dict, Any


def load_litellm_config() -> Dict[str, Any]:
    """Load LiteLLM configuration from gateway/config.yaml."""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "gateway", "config.yaml"
    )
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {"model_list": []}


def get_litellm_model(model_name: str = "main") -> str:
    """Get the model identifier for LiteLLM routing.
    
    Args:
        model_name: Name of the model configuration ('main', 'fast', or 'local')
        
    Returns:
        Full model string for LiteLLM (e.g., 'deepseek/deepseek-v4-pro')
    """
    config = load_litellm_config()
    for model in config.get("model_list", []):
        if model.get("model_name") == model_name:
            litellm_params = model.get("litellm_params", {})
            return litellm_params.get("model", "gpt-4")
    # Fallback to default
    return "deepseek/deepseek-v4-pro"


class AgentBase:
    """Base class for all agents with common LiteLLM configuration."""
    
    def __init__(self, role: str, goal: str, backstory: str, model_name: str = "main"):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.model_name = model_name
        self.full_model = get_litellm_model(model_name)
    
    def llm_call(self, prompt: str, **kwargs) -> str:
        """Make an LLM call through LiteLLM.
        
        Args:
            prompt: The prompt to send to the LLM
            **kwargs: Additional arguments for litellm.completion
            
        Returns:
            The LLM response text
        """
        try:
            response = completion(
                model=self.full_model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback for demo mode without API keys
            return self._demo_response(prompt)
    
    def _demo_response(self, prompt: str) -> str:
        """Generate a demo response when API is unavailable."""
        return f"[DEMO MODE] Processed: {prompt[:100]}..."


# ============================================================================
# Agent Definitions
# ============================================================================

def create_miner_agent() -> Agent:
    """Create the Miner Agent for literature mining.
    
    The Miner Agent is responsible for:
    - Searching academic databases for relevant literature
    - Extracting key findings, methodologies, and conclusions
    - Synthesizing information from multiple sources
    - Identifying knowledge gaps in the literature
    """
    return Agent(
        role="Literature Miner",
        goal="Extract and synthesize relevant scientific literature on materials science topics",
        backstory="""You are an expert research librarian specializing in materials science. 
        You have extensive experience searching academic databases, understanding scientific 
        nomenclature, and identifying high-impact publications. Your goal is to provide 
        comprehensive and relevant literature summaries that form the foundation for 
        research hypothesis generation.""",
        verbose=True,
        allow_delegation=False,
    )


def create_generator_agent() -> Agent:
    """Create the Generator Agent for hypothesis generation.
    
    The Generator Agent is responsible for:
    - Analyzing literature findings to identify patterns
    - Formulating novel research hypotheses
    - Proposing experimental approaches to test hypotheses
    - Identifying potential applications of findings
    """
    return Agent(
        role="Research Hypothesis Generator",
        goal="Formulate novel and testable research hypotheses based on literature findings",
        backstory="""You are a distinguished materials science researcher with expertise in 
        theoretical modeling, computational chemistry, and experimental design. You have 
        published numerous papers on topics ranging from cement chemistry to battery materials. 
        Your strength lies in identifying connections between disparate findings and 
        formulating innovative hypotheses that push the boundaries of current knowledge.""",
        verbose=True,
        allow_delegation=False,
    )


def create_validator_agent() -> Agent:
    """Create the Validator Agent for data validation.
    
    The Validator Agent is responsible for:
    - Cross-referencing hypotheses with known experimental data
    - Assessing the feasibility of proposed experiments
    - Identifying potential confounding factors
    - Assigning confidence scores to hypotheses
    """
    return Agent(
        role="Data Validator",
        goal="Validate research hypotheses against known experimental data and literature",
        backstory="""You are a rigorous data scientist with a background in materials 
        characterization and statistical analysis. You have extensive experience with 
        peer review and understand the importance of reproducibility in scientific research. 
        Your role is to critically evaluate hypotheses and identify potential weaknesses 
        before resources are invested in experimental validation.""",
        verbose=True,
        allow_delegation=False,
    )


def create_reporter_agent() -> Agent:
    """Create the Reporter Agent for report generation.
    
    The Reporter Agent is responsible for:
    - Compiling all findings into structured reports
    - Ensuring proper scientific writing conventions
    - Creating visualizations of key findings
    - Generating reproducible research summaries
    """
    return Agent(
        role="Research Reporter",
        goal="Compile all research findings into comprehensive, well-structured reports",
        backstory="""You are an experienced scientific writer and editor with publications 
        in top-tier journals including Nature Materials, Advanced Materials, and JACS. 
        You excel at translating complex scientific concepts into clear, accessible 
        narratives. Your reports are known for their clarity, completeness, and adherence 
        to scientific writing standards.""",
        verbose=True,
        allow_delegation=False,
    )


# Export agent factory functions
MinerAgent = create_miner_agent
GeneratorAgent = create_generator_agent
ValidatorAgent = create_validator_agent
ReporterAgent = create_reporter_agent
