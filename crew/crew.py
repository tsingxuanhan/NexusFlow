# -*- coding: utf-8 -*-
"""
CrewAI crew orchestration for the materials science research pipeline.

This module defines the ResearchCrew class that orchestrates the four-agent pipeline:
1. Miner Agent -> 2. Generator Agent -> 3. Validator Agent -> 4. Reporter Agent

The crew executes tasks sequentially using CrewAI's Process framework.
"""

from crewai import Crew, Process
from typing import Optional, Dict, Any, List
import yaml
import os

from .agents import (
    create_miner_agent,
    create_generator_agent,
    create_validator_agent,
    create_reporter_agent,
)
from .tasks import (
    create_literature_mining_task,
    create_hypothesis_generation_task,
    create_validation_task,
    create_report_task,
)


class ResearchCrew:
    """Orchestrates the multi-agent research pipeline.
    
    This class manages the entire research workflow from literature mining
    to final report generation. It coordinates four specialized agents
    through a sequential process.
    
    Attributes:
        topic: The research topic to investigate
        agents: Dictionary of created agents
        tasks: List of tasks to execute
        crew: The CrewAI Crew instance
    """
    
    def __init__(
        self,
        topic: str,
        verbose: bool = True,
        model_config: Optional[str] = None
    ):
        """Initialize the research crew.
        
        Args:
            topic: The materials science topic to research
            verbose: Enable verbose output (default: True)
            model_config: Path to LiteLLM config file (optional)
        """
        self.topic = topic
        self.verbose = verbose
        self.model_config = model_config
        
        # Initialize agents
        self.agents = {
            "miner": create_miner_agent(),
            "generator": create_generator_agent(),
            "validator": create_validator_agent(),
            "reporter": create_reporter_agent(),
        }
        
        # Initialize empty task list
        self.tasks: List = []
        
        # Storage for task outputs (for context passing)
        self.context: Dict[str, Any] = {}
        
        # Create the crew
        self.crew = None
        
    def _build_tasks(self) -> None:
        """Build all tasks with proper context passing."""
        
        # Task 1: Literature Mining
        mining_task = create_literature_mining_task(
            agent=self.agents["miner"],
            topic=self.topic
        )
        self.tasks.append(mining_task)
        
        # Task 2: Hypothesis Generation (depends on mining task)
        hypothesis_task = create_hypothesis_generation_task(
            agent=self.agents["generator"],
            topic=self.topic,
            context={"literature_results": self.context.get("literature_results", "")}
        )
        hypothesis_task.context = {"literature_results": self.context.get("literature_results", "")}
        self.tasks.append(hypothesis_task)
        
        # Task 3: Validation (depends on hypothesis task)
        validation_task = create_validation_task(
            agent=self.agents["validator"],
            context={"hypothesis_results": self.context.get("hypothesis_results", "")}
        )
        validation_task.context = {"hypothesis_results": self.context.get("hypothesis_results", "")}
        self.tasks.append(validation_task)
        
        # Task 4: Report Generation (depends on all previous)
        report_task = create_report_task(
            agent=self.agents["reporter"],
            context={
                "literature_results": self.context.get("literature_results", ""),
                "hypothesis_results": self.context.get("hypothesis_results", ""),
                "validation_results": self.context.get("validation_results", ""),
            }
        )
        self.tasks.append(report_task)
        
    def _update_context(self, task_outputs: Dict[str, Any]) -> None:
        """Update the shared context with task outputs."""
        self.context.update(task_outputs)
        
    def build(self) -> "ResearchCrew":
        """Build the CrewAI crew with all agents and tasks.
        
        Returns:
            Self for method chaining
        """
        # Build tasks
        self._build_tasks()
        
        # Create CrewAI Crew with sequential process
        self.crew = Crew(
            agents=[
                self.agents["miner"],
                self.agents["generator"],
                self.agents["validator"],
                self.agents["reporter"],
            ],
            tasks=self.tasks,
            process=Process.sequential,  # Tasks execute one after another
            verbose=self.verbose,
        )
        
        return self
    
    def run(self) -> Dict[str, Any]:
        """Execute the research pipeline.
        
        This method runs all four agents sequentially and collects
        their outputs for the final report.
        
        Returns:
            Dictionary containing all task outputs and the final report
        """
        if self.crew is None:
            self.build()
        
        # Execute the crew
        results = self.crew.kickoff()
        
        # Process and return results
        return {
            "topic": self.topic,
            "raw_results": results,
            "context": self.context,
        }
    
    def run_with_fallback(self) -> Dict[str, Any]:
        """Execute with demo fallback if API is unavailable.
        
        This method attempts to run the full pipeline, but if API
        calls fail, it falls back to simulated demo outputs.
        
        Returns:
            Dictionary containing results or demo data
        """
        try:
            return self.run()
        except Exception as e:
            print(f"[WARNING] API call failed: {e}")
            print("[INFO] Falling back to demo mode...")
            return self._generate_demo_results()
    
    def _generate_demo_results(self) -> Dict[str, Any]:
        """Generate demo results when API is unavailable."""
        
        # Demo literature results
        demo_literature = f"""## Literature Summary: {self.topic}

### Key Papers

1. **"Advanced Super Sulfated Cement: Properties and Applications"** (2023)
   - Authors: Zhang et al.
   - Key Findings: Superior durability, 40% reduced CO2 emissions
   - Methodology: XRD, SEM, compressive strength testing

2. **"Microstructural Analysis of Sulfate-Activated Binders"** (2022)
   - Authors: Li and Wang
   - Key Findings: N/A-C-S-H formation at low temperatures
   - Methodology: TEM, 29Si NMR

### Common Findings
- All studies report excellent chemical resistance
- CO2 reduction potential confirmed by LCA studies
- Mechanical properties comparable to OPC

### Research Gaps
- Long-term durability data (>10 years) is limited
- Standardization of production processes needed"""

        # Demo hypothesis results
        demo_hypotheses = """## Research Hypotheses

### Hypothesis 1: Enhanced Freeze-Thaw Resistance
- Statement: Super sulfated cement exhibits superior freeze-thaw resistance due to reduced pore connectivity
- Justification: Literature shows lower capillary porosity compared to OPC
- Experimental Approach: ASTM C666 rapid freezing-thawing cycles
- Potential Impact: Extended service life in cold climates

### Hypothesis 2: CO2 Sequestration Potential
- Statement: SSC can sequester industrial CO2 waste as a raw material
- Justification: Gypsum and slag reactions may incorporate CO2
- Experimental Approach: Carbonation curing experiments with isotopic tracing
- Potential Impact: Carbon-negative cement production

### Hypothesis 3: Alkali-Silica Reaction Suppression
- Statement: SSC's low pH suppresses deleterious alkali-silica reaction
- Justification: Lower hydroxide concentration compared to OPC
- Experimental Approach: Mortar bar expansion tests with reactive aggregates"""

        # Demo validation results
        demo_validation = """## Validation Results

### Hypothesis 1: Enhanced Freeze-Thaw Resistance
- Validation Status: Supported
- Confidence Score: 8/10
- Supporting Evidence: Chen et al. (2022) showed 95% durability factor
- Concerns: Mix design variations may affect results
- Recommended Additional Experiments: Standardize w/c ratio testing

### Hypothesis 2: CO2 Sequestration Potential
- Validation Status: Partial
- Confidence Score: 6/10
- Supporting Evidence: Preliminary studies show 5-10% CO2 uptake
- Concerns: Process economics and scalability uncertain
- Recommended Additional Experiments: Pilot-scale carbonation trials

### Hypothesis 3: Alkali-Silica Reaction Suppression
- Validation Status: Supported
- Confidence Score: 9/10
- Supporting Evidence: Multiple studies confirm low pH (~11)
- Concerns: Long-term ASR data still limited
- Recommended Additional Experiments: 5-year exposure site monitoring

### Overall Assessment
- Recommended Priority: H1 > H3 > H2
- Most feasible: Hypothesis 3 (existing infrastructure)
- Highest impact: Hypothesis 2 (if scalable)"""

        # Update context with demo data
        self.context = {
            "literature_results": demo_literature,
            "hypothesis_results": demo_hypotheses,
            "validation_results": demo_validation,
        }
        
        return {
            "topic": self.topic,
            "demo_mode": True,
            "context": self.context,
            "literature_results": demo_literature,
            "hypothesis_results": demo_hypotheses,
            "validation_results": demo_validation,
            "final_report": self._generate_demo_report(),
        }
    
    def _generate_demo_report(self) -> str:
        """Generate the final demo report."""
        return f"""# Research Report: {self.topic}

## Executive Summary

This report presents a comprehensive literature review and hypothesis 
generation for super sulfated cement (SSC), an emerging sustainable 
binder technology. Through analysis of recent publications, three novel 
research hypotheses were formulated and validated against existing 
experimental data. The findings suggest significant potential for SSC 
in reducing cement industry carbon emissions while maintaining or 
improving material performance.

## Introduction and Background

Super sulfated cement (SSC) represents an innovative approach to 
sustainable construction materials. Composed primarily of granulated 
blast-furnace slag, calcium sulfate (gypsum), and a small amount of 
Portland cement clinker or alkali activator, SSC offers several 
environmental advantages over traditional Ordinary Portland Cement (OPC).

Key benefits include:
- 40-70% lower CO2 emissions compared to OPC
- Utilization of industrial by-products (slag, FGD gypsum)
- Superior chemical resistance in aggressive environments
- Potential for carbon sequestration during curing

## Literature Review

### Current State of Research

Recent studies have demonstrated the technical viability of SSC in 
various applications. Zhang et al. (2023) confirmed mechanical properties 
comparable to OPC at 28 days, while Li and Wang (2022) elucidated the 
microstructural mechanisms underlying SSC hydration.

### Key Findings

1. **Hydration Products**: SSC primarily forms ettringite and C-S-H gel
2. **Durability**: Excellent sulfate and acid resistance documented
3. **Environmental Impact**: Life cycle assessments show 40% lower GWP

### Research Gaps

Critical knowledge gaps remain:
- Long-term field performance data (>10 years)
- Standardized mix design guidelines
- Scale-up challenges for industrial production

## Proposed Hypotheses

Three testable hypotheses were generated based on literature analysis:

1. **Enhanced Freeze-Thaw Resistance**: SSC's refined pore structure 
   provides superior resistance to frost damage.

2. **Carbon Sequestration Potential**: Industrial CO2 can be incorporated 
   into SSC during carbonation curing.

3. **ASR Suppression**: The low-alkali environment in SSC effectively 
   suppresses deleterious alkali-silica reaction.

## Validation Analysis

Each hypothesis was evaluated against available experimental data:

| Hypothesis | Confidence | Status | Priority |
|------------|------------|--------|----------|
| Freeze-Thaw | 8/10 | Supported | High |
| ASR Suppression | 9/10 | Supported | High |
| CO2 Sequestration | 6/10 | Partial | Medium |

## Conclusions and Recommendations

Based on this analysis, the following recommendations are made:

1. **Immediate Action**: Conduct standardized freeze-thaw testing (H1)
2. **Short-term**: Develop alkali content guidelines for ASR-prone aggregates (H3)
3. **Long-term**: Pilot-scale carbonation studies to validate CO2 sequestration (H2)

The proposed research agenda will advance understanding of SSC while 
addressing critical knowledge gaps identified in this review.

## References

1. Zhang, Y. et al. (2023). Advanced Super Sulfated Cement. Cement and Concrete Research.
2. Li, H. & Wang, J. (2022). Microstructural Analysis of Sulfate-Activated Binders. J. Mater. Sci.
3. Chen, L. et al. (2022). Freeze-Thaw Durability of SSC. Construction and Building Materials.

---
*Report generated by NexusFlow Research Pipeline*
*Topic: {self.topic}*
"""


def create_crew(topic: str, verbose: bool = True) -> ResearchCrew:
    """Factory function to create and configure a research crew.
    
    Args:
        topic: The research topic
        verbose: Enable verbose output
        
    Returns:
        Configured ResearchCrew instance (not yet built)
    """
    crew = ResearchCrew(topic=topic, verbose=verbose)
    return crew


if __name__ == "__main__":
    # Quick test
    crew = create_crew("super sulfated cement")
    crew.build()
    print("Crew built successfully!")
