# -*- coding: utf-8 -*-
"""
demo_lit_review.py - Literature Review Automation Demo

This is the main demonstration script for the NexusFlow framework.
It showcases the complete multi-agent research pipeline from literature
mining to hypothesis validation and report generation.

Usage:
    # Run with default topic (super sulfated cement)
    python demo_lit_review.py
    
    # Run with custom topic
    python demo_lit_review.py --topic "lithium-ion battery cathode"
    
    # Run with verbose output
    python demo_lit_review.py --topic "graphene composites" --verbose
    
    # Run in demo mode (no API key required)
    python demo_lit_review.py --demo

Architecture:
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │   Miner     │───▶│ Generator   │───▶│ Validator   │───▶│ Reporter    │
    │  Agent      │    │  Agent      │    │  Agent      │    │  Agent      │
    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
"""

import argparse
import sys
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass


# ============================================================================
# Mock Data Classes (Standalone - No External Dependencies)
# ============================================================================

@dataclass
class MockPaper:
    """Mock paper for demo without external dependencies."""
    id: str
    title: str
    authors: List[str]
    year: int
    journal: str
    abstract: str
    keywords: List[str]
    citations: int = 0


# ============================================================================
# Demo Runner (Standalone - Works Without Any Dependencies)
# ============================================================================

class DemoRunner:
    """Runs the demo pipeline using mock data.
    
    This class provides a complete demo of the NexusFlow pipeline
    using pre-defined mock data, allowing users to see the full workflow
    without requiring any API configuration.
    """
    
    # Mock paper database
    MOCK_PAPERS = [
        MockPaper(
            id="ssc-001",
            title="Advanced Super Sulfated Cement: Properties and Applications",
            authors=["Zhang, Y.", "Li, H.", "Wang, J."],
            year=2023,
            journal="Cement and Concrete Research",
            abstract="This study investigates the mechanical and durability properties of "
                    "super sulfated cement (SSC) as a sustainable alternative to OPC. "
                    "Results show 40% reduction in CO2 emissions while maintaining "
                    "comparable compressive strength (42 MPa at 28 days).",
            keywords=["super sulfated cement", "sustainability", "CO2 reduction", "durability"],
            citations=45
        ),
        MockPaper(
            id="ssc-002",
            title="Microstructural Analysis of Sulfate-Activated Binders",
            authors=["Li, H.", "Wang, J."],
            year=2022,
            journal="Journal of Materials Science",
            abstract="Comprehensive microstructural analysis using TEM and 29Si NMR "
                    "reveals N/A-C-S-H formation in sulfate-activated blast furnace slag. "
                    "The hydration process produces stable ettringite and C-S-H phases.",
            keywords=["sulfate activation", "slag", "microstructure", "NMR"],
            citations=32
        ),
        MockPaper(
            id="ssc-003",
            title="Freeze-Thaw Durability of Super Sulfated Cement Concrete",
            authors=["Chen, L.", "Liu, M.", "Park, S."],
            year=2022,
            journal="Construction and Building Materials",
            abstract="ASTM C666 evaluation shows 95% durability factor after 300 "
                    "freeze-thaw cycles, demonstrating superior cold climate performance. "
                    "Reduced capillary porosity contributes to improved resistance.",
            keywords=["freeze-thaw", "durability", "SSC", "concrete"],
            citations=28
        ),
        MockPaper(
            id="ssc-004",
            title="Alkali-Silica Reaction in Low-Alkali Cement Systems",
            authors=["Wang, X.", "Brown, K."],
            year=2021,
            journal="Cement and Concrete Research",
            abstract="Low pore solution pH (~11) in SSC effectively suppresses "
                    "alkali-silica reaction expansion in mortar bar tests. "
                    "Long-term stability confirmed in exposure site monitoring.",
            keywords=["ASR", "alkali-silica", "low-alkali", "pH"],
            citations=56
        ),
        MockPaper(
            id="ssc-005",
            title="Carbonation of Super Sulfated Cement: CO2 Sequestration",
            authors=["Liu, M.", "Zhang, Y.", "Kim, J."],
            year=2023,
            journal="Applied Sciences",
            abstract="Accelerated carbonation achieves 5-10% CO2 uptake by mass, "
                    "suggesting potential for carbon-negative cement production. "
                    "Economic viability studies are ongoing.",
            keywords=["carbonation", "CO2 sequestration", "carbon curing"],
            citations=18
        ),
    ]
    
    def __init__(self, topic: str, verbose: bool = True):
        """Initialize demo runner."""
        self.topic = topic
        self.verbose = verbose
        self.start_time = datetime.now()
    
    def run(self) -> Dict[str, Any]:
        """Execute the complete demo pipeline."""
        print("\n" + "=" * 70)
        print(" NexusFlow - Literature Review Automation Demo")
        print("=" * 70)
        print(f"\nTopic: {self.topic}")
        print(f"Mode:  DEMO (standalone, no dependencies required)")
        print(f"Start: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Stage 1: Literature Mining
        print("\n" + "-" * 70)
        print("[STAGE 1/4] Miner Agent: Searching literature...")
        print("-" * 70)
        literature_results = self._run_literature_mining()
        
        # Stage 2: Hypothesis Generation
        print("\n" + "-" * 70)
        print("[STAGE 2/4] Generator Agent: Formulating hypotheses...")
        print("-" * 70)
        hypothesis_results = self._run_hypothesis_generation(literature_results)
        
        # Stage 3: Data Validation
        print("\n" + "-" * 70)
        print("[STAGE 3/4] Validator Agent: Validating data...")
        print("-" * 70)
        validation_results = self._run_validation(hypothesis_results)
        
        # Stage 4: Report Generation
        print("\n" + "-" * 70)
        print("[STAGE 4/4] Reporter Agent: Generating report...")
        print("-" * 70)
        final_report = self._run_report_generation(
            literature_results,
            hypothesis_results,
            validation_results
        )
        
        # Print final report
        print("\n" + "=" * 70)
        print(" FINAL RESEARCH REPORT")
        print("=" * 70)
        print(final_report)
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 70)
        print(" PIPELINE EXECUTION SUMMARY")
        print("=" * 70)
        print(f"  Status:        COMPLETED")
        print(f"  Duration:       {duration:.2f} seconds")
        print(f"  Papers Found:   {literature_results.get('paper_count', 0)}")
        print(f"  Hypotheses:     {hypothesis_results.get('hypothesis_count', 0)}")
        print(f"  Validations:    {validation_results.get('validation_count', 0)}")
        print(f"  Mode:           DEMO (standalone)")
        print("\n" + "=" * 70)
        
        return {
            "topic": self.topic,
            "demo_mode": True,
            "literature_results": literature_results,
            "hypothesis_results": hypothesis_results,
            "validation_results": validation_results,
            "final_report": final_report,
            "duration_seconds": duration
        }
    
    def _run_literature_mining(self) -> Dict[str, Any]:
        """Execute literature mining stage."""
        if self.verbose:
            print(f"\n  Searching for: '{self.topic}'")
            print(f"  Found {len(self.MOCK_PAPERS)} relevant papers\n")
        
        # Format results
        lines = ["## Literature Search Results\n"]
        lines.append(f"**Query:** {self.topic}")
        lines.append(f"**Papers Found:** {len(self.MOCK_PAPERS)}\n")
        
        for i, paper in enumerate(self.MOCK_PAPERS, 1):
            lines.append(f"### {i}. {paper.title}")
            lines.append(f"**Authors:** {', '.join(paper.authors)}")
            lines.append(f"**Year:** {paper.year} | **Journal:** {paper.journal}")
            lines.append(f"**Citations:** {paper.citations}")
            lines.append(f"\n**Abstract:** {paper.abstract}\n")
            lines.append(f"*Keywords:* {', '.join(paper.keywords)}")
            lines.append("---\n")
        
        # Research gaps
        lines.append("\n## Research Gaps\n")
        lines.append("Based on the literature analysis, the following gaps were identified:\n")
        lines.append("1. Long-term durability data (>10 years) is limited")
        lines.append("2. Standardization of production processes needed")
        lines.append("3. Scale-up challenges for industrial applications")
        lines.append("4. Carbon sequestration potential requires further validation")
        
        if self.verbose:
            print("\n".join(lines[:40]))
            if len(lines) > 40:
                print(f"\n  [... {len(lines) - 40} more lines ...]")
        
        return {
            "query": self.topic,
            "paper_count": len(self.MOCK_PAPERS),
            "papers": self.MOCK_PAPERS,
            "formatted_results": "\n".join(lines),
            "gaps": [
                "Long-term durability data limited",
                "Production standardization needed",
                "Scale-up challenges exist",
                "Carbon sequestration potential uncertain"
            ]
        }
    
    def _run_hypothesis_generation(self, literature_results: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hypothesis generation stage."""
        paper_count = literature_results.get("paper_count", 0)
        
        if self.verbose:
            print(f"\n  Analyzing {paper_count} papers...")
            print(f"  Identified {len(literature_results.get('gaps', []))} research gaps")
        
        # Generate hypotheses
        hypotheses = [
            {
                "id": 1,
                "title": "Enhanced Freeze-Thaw Resistance",
                "statement": "Super sulfated cement exhibits superior freeze-thaw resistance "
                            "due to its refined pore structure and reduced capillary porosity.",
                "justification": "Literature shows SSC produces a denser microstructure with "
                               "lower porosity compared to OPC, which should improve durability "
                               "in cyclic freezing conditions.",
                "experimental_approach": "ASTM C666 Procedure A with durability factor "
                                      "calculation after 300 cycles.",
                "potential_impact": "High - enables SSC use in cold climate applications.",
                "confidence": 8,
                "priority": "High"
            },
            {
                "id": 2,
                "title": "Carbon Sequestration Potential",
                "statement": "Super sulfated cement can effectively sequester industrial CO2 "
                            "emissions through accelerated carbonation curing.",
                "justification": "The calcium silicate hydrate phases in SSC are reactive and "
                               "can form calcium carbonate, achieving 5-10% CO2 uptake.",
                "experimental_approach": "Accelerated carbonation curing under controlled "
                                      "CO2 concentration (5-20%) with isotopic tracing.",
                "potential_impact": "Very High - could enable carbon-negative production.",
                "confidence": 6,
                "priority": "Medium"
            },
            {
                "id": 3,
                "title": "Alkali-Silica Reaction Suppression",
                "statement": "The low pore solution pH (~11) in SSC effectively suppresses "
                            "deleterious alkali-silica reaction in concrete.",
                "justification": "ASR expansion requires high pH (>13.2) to dissolve silica. "
                               "SSC's low-alkali nature prevents this mechanism.",
                "experimental_approach": "Mortar bar expansion testing (ASTM C1260) with "
                                      "reactive aggregates over 14 and 28 days.",
                "potential_impact": "High - enables use with ASR-prone aggregates.",
                "confidence": 9,
                "priority": "High"
            }
        ]
        
        # Format hypotheses
        lines = ["## Research Hypotheses\n"]
        for h in hypotheses:
            lines.append(f"### Hypothesis {h['id']}: {h['title']}")
            lines.append(f"\n**Statement:** {h['statement']}\n")
            lines.append(f"**Justification:** {h['justification']}\n")
            lines.append(f"**Experimental Approach:** {h['experimental_approach']}\n")
            lines.append(f"**Potential Impact:** {h['potential_impact']}\n")
            lines.append(f"**Confidence Score:** {h['confidence']}/10")
            lines.append(f"**Priority:** {h['priority']}")
            lines.append("\n---\n")
        
        if self.verbose:
            print("\n".join(lines[:50]))
            if len(lines) > 50:
                print(f"\n  [... {len(lines) - 50} more lines ...]")
        
        return {
            "hypothesis_count": len(hypotheses),
            "hypotheses": hypotheses,
            "formatted_hypotheses": "\n".join(lines)
        }
    
    def _run_validation(self, hypothesis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hypothesis validation stage."""
        hypotheses = hypothesis_results.get("hypotheses", [])
        
        if self.verbose:
            print(f"\n  Validating {len(hypotheses)} hypotheses...")
        
        # Validation results with mock property data
        validation_map = {
            1: {"status": "Supported", "evidence": "Chen et al. (2022): 95% durability factor"},
            2: {"status": "Partial", "evidence": "5-10% CO2 uptake achieved, economics uncertain"},
            3: {"status": "Supported", "evidence": "Wang & Brown (2021): pH ~11 effective for ASR"}
        }
        
        validation_results = []
        for h in hypotheses:
            v = validation_map.get(h["id"], {"status": "Unknown", "evidence": "N/A"})
            validation_results.append({
                "hypothesis_id": h["id"],
                "hypothesis_title": h["title"],
                "status": v["status"],
                "confidence": h["confidence"],
                "evidence": v["evidence"]
            })
        
        # Format validation output
        lines = ["## Validation Results\n"]
        for v in validation_results:
            lines.append(f"### Hypothesis {v['hypothesis_id']}: {v['hypothesis_title']}")
            lines.append(f"\n**Status:** {v['status']}")
            lines.append(f"**Confidence Score:** {v['confidence']}/10")
            lines.append(f"**Supporting Evidence:** {v['evidence']}\n")
            lines.append("---\n")
        
        # Summary table
        lines.append("\n## Validation Summary\n")
        lines.append("| Hypothesis | Confidence | Status |")
        lines.append("|------------|------------|--------|")
        for v in validation_results:
            lines.append(f"| {v['hypothesis_title']} | {v['confidence']}/10 | {v['status']} |")
        
        if self.verbose:
            print("\n".join(lines))
        
        return {
            "validation_count": len(validation_results),
            "validation_results": validation_results,
            "formatted_validation": "\n".join(lines)
        }
    
    def _run_report_generation(
        self,
        literature_results: Dict[str, Any],
        hypothesis_results: Dict[str, Any],
        validation_results: Dict[str, Any]
    ) -> str:
        """Execute final report generation."""
        date = datetime.now().strftime("%Y-%m-%d")
        
        report = f"""# Research Report: {self.topic}

**Generated:** {date}  
**Framework:** NexusFlow Research Pipeline

---

## Executive Summary

This report presents the findings of an automated literature review
and research hypothesis generation process. Based on analysis of
{literature_results['paper_count']} relevant publications,
{hypothesis_results['hypothesis_count']} research hypotheses were generated
and validated against existing experimental data.

Key findings include:
- Sustainable alternative to ordinary Portland cement
- Significant CO2 emission reduction potential (40-70%)
- Superior durability in specific applications
- Novel hypotheses for future research

---

## 1. Introduction

Materials science research increasingly relies on systematic
analysis of existing literature to identify research gaps and
formulate novel hypotheses. This report demonstrates an automated
multi-agent pipeline for literature mining and hypothesis generation.

---

## 2. Literature Review

{literature_results.get('formatted_results', '')}

---

## 3. Research Hypotheses

{hypothesis_results.get('formatted_hypotheses', '')}

---

## 4. Validation Analysis

{validation_results.get('formatted_validation', '')}

---

## 5. Conclusions and Recommendations

### Conclusions

1. Super sulfated cement represents a viable sustainable alternative
   to traditional cement, with demonstrated mechanical properties
   comparable to OPC in many applications.

2. The literature strongly supports three primary advantages of SSC:
   - Reduced environmental impact (40-70% lower CO2)
   - Superior chemical resistance
   - Effective ASR suppression

3. Carbon sequestration potential remains partially validated
   and requires additional research.

### Recommendations

1. **High Priority**: Conduct standardized freeze-thaw durability
   testing to validate the first hypothesis.

2. **High Priority**: Develop guidelines for ASR-prone aggregate
   applications using SSC's low-alkali properties.

3. **Medium Priority**: Investigate carbonation curing economics
   and scalability for CO2 sequestration.

4. **Long-term**: Establish long-term field performance databases
   (>10 years) for SSC structures.

---

## References

1. Zhang, Y. et al. (2023). Advanced Super Sulfated Cement: Properties and Applications. Cement and Concrete Research.
2. Li, H. & Wang, J. (2022). Microstructural Analysis of Sulfate-Activated Binders. Journal of Materials Science.
3. Chen, L. et al. (2022). Freeze-Thaw Durability of Super Sulfated Cement Concrete. Construction and Building Materials.
4. Wang, X. & Brown, K. (2021). Alkali-Silica Reaction in Low-Alkali Cement Systems. Cement and Concrete Research.
5. Liu, M. et al. (2023). Carbonation of Super Sulfated Cement. Applied Sciences.

---

*Report generated by NexusFlow Research Pipeline*  
*Date: {date}*
"""
        
        return report
    
    def save_report(self, report: str, filename: Optional[str] = None):
        """Save the final report to a file."""
        if filename is None:
            safe_topic = self.topic.lower().replace(" ", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{safe_topic}_{timestamp}.md"
        
        filepath = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            filename
        )
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"\nReport saved to: {filepath}")
        return filepath


# ============================================================================
# API Mode Runner (Requires crewai and litellm)
# ============================================================================

class APIModeRunner:
    """Runs the pipeline using actual LLM API calls."""
    
    def __init__(self, topic: str, verbose: bool = True):
        self.topic = topic
        self.verbose = verbose
    
    def run(self) -> Dict[str, Any]:
        """Execute the pipeline with real LLM calls."""
        print("\n" + "=" * 70)
        print(" NexusFlow - Literature Review Pipeline (API Mode)")
        print("=" * 70)
        
        try:
            # Try to import CrewAI components
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from crew.crew import ResearchCrew, create_crew
            
            print(f"\nTopic: {self.topic}")
            print("Mode:  API (using configured LLM endpoints)")
            
            crew = create_crew(topic=self.topic, verbose=self.verbose)
            print("\nStarting research pipeline...")
            results = crew.run_with_fallback()
            
            if results.get("demo_mode"):
                print("\n[NOTE] Fell back to demo mode (API unavailable)")
            
            return results
            
        except ImportError as e:
            print(f"\n[INFO] CrewAI not installed: {e}")
            print("[INFO] Falling back to demo mode...")
            demo = DemoRunner(topic=self.topic, verbose=self.verbose)
            return demo.run()
            
        except Exception as e:
            print(f"\n[ERROR] API execution failed: {e}")
            print("[INFO] Falling back to demo mode...")
            demo = DemoRunner(topic=self.topic, verbose=self.verbose)
            return demo.run()


# ============================================================================
# Main Entry Point
# ============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="NexusFlow Literature Review Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--topic",
        type=str,
        default="super sulfated cement",
        help="Research topic for literature review (default: 'super sulfated cement')"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output (default: True)"
    )
    
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Force demo mode (no API key required)"
    )
    
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save the final report to a Markdown file"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress detailed output"
    )
    
    return parser.parse_args()


def check_api_configuration() -> bool:
    """Check if API is properly configured."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        "..", "gateway", "config.yaml"
    )
    
    if not os.path.exists(config_path):
        return False
    
    with open(config_path, "r") as f:
        content = f.read()
    
    return "[PLACEHOLDER" not in content


def main():
    """Main entry point for the demo."""
    args = parse_args()
    
    # Determine running mode
    use_demo = args.demo or not check_api_configuration()
    
    if use_demo:
        print("\n[INFO] Running in DEMO mode (standalone, no dependencies required)")
        if not args.demo:
            print("[INFO] Set valid API keys in gateway/config.yaml for full pipeline")
        runner = DemoRunner(topic=args.topic, verbose=not args.quiet)
    else:
        print("\n[INFO] Running in API mode (using configured LLM endpoints)")
        runner = APIModeRunner(topic=args.topic, verbose=not args.quiet)
    
    # Run the pipeline
    try:
        results = runner.run()
        
        if args.save_report and "final_report" in results:
            filepath = runner.save_report(results["final_report"])
            print(f"Report saved to: {filepath}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n[INFO] Pipeline interrupted by user")
        return 130
        
    except Exception as e:
        print(f"\n[ERROR] Pipeline execution failed: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
