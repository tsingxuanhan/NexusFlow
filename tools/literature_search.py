# -*- coding: utf-8 -*-
"""
Literature Search Tool.

This module provides functionality for searching academic literature
related to materials science. It supports querying academic databases
and returning structured results.

Usage:
    >>> from agent4science.tools import LiteratureSearchTool
    >>> tool = LiteratureSearchTool()
    >>> results = tool.search("super sulfated cement hydration")
    >>> print(results)
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Paper:
    """Represents a scientific paper."""
    id: str
    title: str
    authors: List[str]
    year: int
    journal: str
    abstract: str
    keywords: List[str]
    doi: Optional[str] = None
    citations: int = 0
    url: Optional[str] = None


@dataclass
class SearchResult:
    """Represents a literature search result."""
    query: str
    total_found: int
    papers: List[Paper]
    search_time: datetime


class LiteratureSearchTool:
    """Tool for searching academic literature.
    
    This tool provides a unified interface for searching materials
    science literature across multiple academic databases.
    
    Attributes:
        max_results: Maximum number of results to return
        min_year: Minimum publication year filter
        
    Example:
        >>> tool = LiteratureSearchTool(max_results=20, min_year=2020)
        >>> result = tool.search("cement hydration mechanisms")
        >>> for paper in result.papers:
        ...     print(f"{paper.title} ({paper.year})")
    """
    
    def __init__(
        self,
        max_results: int = 10,
        min_year: Optional[int] = None,
        api_key: Optional[str] = None
    ):
        """Initialize the literature search tool.
        
        Args:
            max_results: Maximum results to return (default: 10)
            min_year: Minimum publication year (default: None)
            api_key: API key for academic database access
        """
        self.max_results = max_results
        self.min_year = min_year
        self.api_key = api_key
        
        # Mock database for demo purposes
        self._mock_database = self._init_mock_database()
    
    def _init_mock_database(self) -> List[Paper]:
        """Initialize mock paper database for demonstration."""
        return [
            Paper(
                id="p001",
                title="Advanced Super Sulfated Cement: Properties and Applications",
                authors=["Zhang, Y.", "Li, H.", "Wang, J."],
                year=2023,
                journal="Cement and Concrete Research",
                abstract="This study investigates mechanical and durability properties "
                        "of super sulfated cement (SSC) as a sustainable alternative to OPC. "
                        "Results show 40% reduction in CO2 emissions.",
                keywords=["super sulfated cement", "sustainability", "CO2", "durability"],
                doi="10.1016/j.cemconres.2023.01.001",
                citations=45
            ),
            Paper(
                id="p002",
                title="Microstructural Analysis of Sulfate-Activated Binders",
                authors=["Li, H.", "Wang, J."],
                year=2022,
                journal="Journal of Materials Science",
                abstract="Comprehensive microstructural analysis using TEM and 29Si NMR "
                        "reveals N/A-C-S-H formation in sulfate-activated blast furnace slag.",
                keywords=["sulfate activation", "slag", "microstructure", "NMR"],
                doi="10.1016/j.jmatsci.2022.05.001",
                citations=32
            ),
            Paper(
                id="p003",
                title="Freeze-Thaw Durability of Super Sulfated Cement Concrete",
                authors=["Chen, L.", "Liu, M.", "Park, S."],
                year=2022,
                journal="Construction and Building Materials",
                abstract="ASTM C666 evaluation shows 95% durability factor after 300 "
                        "freeze-thaw cycles, demonstrating superior cold climate performance.",
                keywords=["freeze-thaw", "durability", "SSC", "concrete"],
                doi="10.1016/j.conbuildmat.2022.01.001",
                citations=28
            ),
            Paper(
                id="p004",
                title="Alkali-Silica Reaction in Low-Alkali Cement Systems",
                authors=["Wang, X.", "Brown, K."],
                year=2021,
                journal="Cement and Concrete Research",
                abstract="Low pore solution pH (~11) in SSC effectively suppresses "
                        "alkali-silica reaction expansion in mortar bar tests.",
                keywords=["ASR", "alkali-silica", "low-alkali", "pH"],
                doi="10.1016/j.cemconres.2021.01.001",
                citations=56
            ),
            Paper(
                id="p005",
                title="Carbonation of Super Sulfated Cement: CO2 Sequestration",
                authors=["Liu, M.", "Zhang, Y.", "Kim, J."],
                year=2023,
                journal="Applied Sciences",
                abstract="Accelerated carbonation achieves 5-10% CO2 uptake by mass, "
                        "suggesting potential for carbon-negative cement production.",
                keywords=["carbonation", "CO2 sequestration", "carbon curing"],
                doi="10.3390/app13158121",
                citations=18
            ),
            Paper(
                id="p006",
                title="Hydration Kinetics of Calcium Sulfate-Based Cements",
                authors=["Kumar, A.", "Singh, R."],
                year=2021,
                journal="Journal of the American Ceramic Society",
                abstract="Isothermal calorimetry reveals three-stage hydration mechanism "
                        "in SSC: initial dissolution, ettringite formation, and C-S-H growth.",
                keywords=["hydration", "kinetics", "calorimetry", "ettringite"],
                doi="10.1111/jace.17501",
                citations=41
            ),
        ]
    
    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        min_year: Optional[int] = None
    ) -> SearchResult:
        """Search for papers matching the query.
        
        Args:
            query: Search query string (supports boolean operators)
            max_results: Override default max results
            min_year: Override default min year
            
        Returns:
            SearchResult with matching papers
            
        Example:
            >>> result = tool.search("super sulfated cement")
            >>> print(f"Found {result.total_found} papers")
        """
        max_results = max_results or self.max_results
        min_year = min_year or self.min_year
        
        query_lower = query.lower()
        matching_papers = []
        
        for paper in self._mock_database:
            # Apply year filter
            if min_year and paper.year < min_year:
                continue
            
            # Calculate relevance score
            score = self._calculate_relevance(query_lower, paper)
            
            if score > 0:
                matching_papers.append((score, paper))
        
        # Sort by relevance score
        matching_papers.sort(key=lambda x: x[0], reverse=True)
        
        # Extract papers and limit results
        papers = [p for _, p in matching_papers[:max_results]]
        
        return SearchResult(
            query=query,
            total_found=len(matching_papers),
            papers=papers,
            search_time=datetime.now()
        )
    
    def _calculate_relevance(self, query: str, paper: Paper) -> float:
        """Calculate relevance score for a paper.
        
        Args:
            query: Lowercase query string
            paper: Paper to score
            
        Returns:
            Relevance score (0-1)
        """
        score = 0.0
        query_terms = query.split()
        
        # Check title (highest weight)
        title_lower = paper.title.lower()
        for term in query_terms:
            if term in title_lower:
                score += 0.4
        
        # Check abstract
        abstract_lower = paper.abstract.lower()
        for term in query_terms:
            if term in abstract_lower:
                score += 0.2
        
        # Check keywords (high weight)
        keywords_text = " ".join(paper.keywords).lower()
        for term in query_terms:
            if term in keywords_text:
                score += 0.3
        
        # Normalize by number of query terms
        return score / len(query_terms) if query_terms else 0
    
    def format_results(self, result: SearchResult, format: str = "markdown") -> str:
        """Format search results as a string.
        
        Args:
            result: SearchResult to format
            format: Output format ('markdown', 'plain', 'json')
            
        Returns:
            Formatted string
        """
        if format == "json":
            import json
            return json.dumps({
                "query": result.query,
                "total_found": result.total_found,
                "papers": [
                    {
                        "id": p.id,
                        "title": p.title,
                        "authors": p.authors,
                        "year": p.year,
                        "journal": p.journal,
                        "abstract": p.abstract,
                        "keywords": p.keywords,
                        "doi": p.doi,
                        "citations": p.citations
                    }
                    for p in result.papers
                ]
            }, indent=2)
        
        elif format == "plain":
            lines = [f"Search: {result.query}", f"Found: {result.total_found} papers", ""]
            for i, paper in enumerate(result.papers, 1):
                lines.append(f"{i}. {paper.title}")
                lines.append(f"   Authors: {', '.join(paper.authors)}")
                lines.append(f"   Year: {paper.year} | Journal: {paper.journal}")
                lines.append(f"   DOI: {paper.doi}")
                lines.append("")
            return "\n".join(lines)
        
        else:  # markdown
            lines = [f"## Literature Search: {result.query}", ""]
            lines.append(f"**Total Found:** {result.total_found} papers")
            lines.append("")
            
            for i, paper in enumerate(result.papers, 1):
                lines.append(f"### {i}. {paper.title}")
                lines.append("")
                lines.append(f"**Authors:** {', '.join(paper.authors)}")
                lines.append(f"**Year:** {paper.year} | **Journal:** {paper.journal}")
                lines.append(f"**Citations:** {paper.citations}")
                lines.append(f"**DOI:** [{paper.doi}](https://doi.org/{paper.doi})")
                lines.append("")
                lines.append(f"**Abstract:** {paper.abstract}")
                lines.append("")
                lines.append(f"*Keywords:* {', '.join(paper.keywords)}")
                lines.append("")
                lines.append("---")
                lines.append("")
            
            return "\n".join(lines)


# Convenience function for quick searches
def search_literature(query: str, max_results: int = 10) -> SearchResult:
    """Quick literature search.
    
    Args:
        query: Search query
        max_results: Maximum results
        
    Returns:
        SearchResult with matching papers
    """
    tool = LiteratureSearchTool(max_results=max_results)
    return tool.search(query)


if __name__ == "__main__":
    # Demo usage
    print("=" * 60)
    print("Literature Search Tool - Demo")
    print("=" * 60)
    
    tool = LiteratureSearchTool(max_results=5)
    
    # Search for papers
    result = tool.search("super sulfated cement")
    
    print(f"\nQuery: '{result.query}'")
    print(f"Found: {result.total_found} papers\n")
    
    # Print in markdown format
    print(tool.format_results(result, "markdown"))
