# -*- coding: utf-8 -*-
"""
MCP Server for Materials Science Tools.

This module implements an MCP (Model Context Protocol) server that exposes
materials science tools to AI agents. The server provides:

1. search_literature - Search academic databases for papers
2. validate_property - Validate material properties against known data
3. generate_report - Generate structured research reports

Usage:
    # As a standalone server
    python -m nexusflow.mcp_server.materials_tools
    
    # Programmatically
    from agent4science.mcp_server import MaterialsMCPServer
    server = MaterialsMCPServer()
    server.run()
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime


# ============================================================================
# MCP Tool Definitions
# ============================================================================

def create_mcp_tools() -> List[Dict[str, Any]]:
    """Define the MCP tools available for materials science.
    
    Returns:
        List of tool definitions following MCP schema
    """
    return [
        {
            "name": "search_literature",
            "description": "Search academic databases for materials science literature. "
                         "Returns relevant papers with titles, authors, abstracts, and key findings.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'super sulfated cement hydration')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    },
                    "year_from": {
                        "type": "integer",
                        "description": "Earliest publication year"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "validate_property",
            "description": "Validate material properties against known experimental data ranges. "
                         "Checks if a property value is within expected bounds.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "material": {
                        "type": "string",
                        "description": "Material name (e.g., 'super sulfated cement')"
                    },
                    "property": {
                        "type": "string",
                        "description": "Property to validate (e.g., 'compressive_strength')"
                    },
                    "value": {
                        "type": "number",
                        "description": "Value to validate"
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unit of measurement"
                    }
                },
                "required": ["material", "property", "value"]
            }
        },
        {
            "name": "generate_report",
            "description": "Generate a structured research report in Markdown format.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Report title"
                    },
                    "literature_summary": {
                        "type": "string",
                        "description": "Summary of literature findings"
                    },
                    "hypotheses": {
                        "type": "string",
                        "description": "Proposed research hypotheses"
                    },
                    "validation_results": {
                        "type": "string",
                        "description": "Validation analysis results"
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format",
                        "enum": ["markdown", "html", "json"],
                        "default": "markdown"
                    }
                },
                "required": ["title"]
            }
        }
    ]


# ============================================================================
# Tool Implementations
# ============================================================================

class LiteratureDatabase:
    """Mock literature database for demonstration.
    
    In production, this would connect to real academic APIs
    (Semantic Scholar, CrossRef, arXiv, etc.)
    """
    
    def __init__(self):
        # Mock database of papers
        self.papers = [
            {
                "id": "ssc-001",
                "title": "Advanced Super Sulfated Cement: Properties and Applications",
                "authors": ["Zhang, Y.", "Li, H.", "Wang, J."],
                "year": 2023,
                "journal": "Cement and Concrete Research",
                "abstract": "This study investigates the mechanical and durability properties of "
                           "super sulfated cement (SSC) as a sustainable alternative to ordinary "
                           "Portland cement. Results show 40% reduction in CO2 emissions while "
                           "maintaining comparable compressive strength (42 MPa at 28 days).",
                "keywords": ["super sulfated cement", "sustainability", "CO2 reduction", "durability"],
                "findings": ["Superior chemical resistance", "40% lower CO2 emissions", 
                            "Compressive strength 35-45 MPa"]
            },
            {
                "id": "ssc-002",
                "title": "Microstructural Analysis of Sulfate-Activated Binders",
                "authors": ["Li, H.", "Wang, J."],
                "year": 2022,
                "journal": "Journal of Materials Science",
                "abstract": "This paper presents a comprehensive microstructural analysis of "
                           "sulfate-activated blast furnace slag binders using advanced "
                           "characterization techniques including TEM and 29Si NMR.",
                "keywords": ["sulfate activation", " slag", " microstructure", " NMR"],
                "findings": ["N/A-C-S-H formation identified", "Low temperature hydration effective",
                            "Ettringite as primary binding phase"]
            },
            {
                "id": "ssc-003",
                "title": "Freeze-Thaw Durability of Super Sulfated Cement Concrete",
                "authors": ["Chen, L.", "Liu, M.", "Park, S."],
                "year": 2022,
                "journal": "Construction and Building Materials",
                "abstract": "This research evaluates the freeze-thaw resistance of SSC concrete "
                           "following ASTM C666 procedure A. The SSC specimens demonstrated "
                           "95% durability factor after 300 cycles.",
                "keywords": ["freeze-thaw", "durability", "SSC", "concrete"],
                "findings": ["95% durability factor at 300 cycles", "Reduced capillary porosity",
                            "Superior to OPC in cold climates"]
            },
            {
                "id": "ssc-004",
                "title": "Alkali-Silica Reaction in Low-Alkali Cement Systems",
                "authors": ["Wang, X.", "Brown, K."],
                "year": 2021,
                "journal": "Cement and Concrete Research",
                "abstract": "This study investigates alkali-silica reaction (ASR) suppression "
                           "mechanisms in low-alkali cement systems. Results confirm that SSC's "
                           "low pore solution pH effectively suppresses ASR expansion.",
                "keywords": ["ASR", "alkali-silica reaction", "low-alkali", "pH"],
                "findings": ["pH ~11 effective for ASR suppression", "Mortar bar expansion <0.05%",
                            "Long-term stability confirmed"]
            },
            {
                "id": "ssc-005",
                "title": "Carbonation of Super Sulfated Cement: A CO2 Sequestration Pathway",
                "authors": ["Liu, M.", "Zhang, Y.", "Kim, J."],
                "year": 2023,
                "journal": "Applied Sciences",
                "abstract": "This paper explores the potential for CO2 sequestration through "
                           "carbonation curing of SSC. Laboratory results show 5-10% CO2 uptake "
                           "by mass during accelerated carbonation.",
                "keywords": ["carbonation", "CO2 sequestration", "carbon curing", "sustainability"],
                "findings": ["5-10% CO2 uptake achieved", "Strength increase after carbonation",
                            "Economic viability under study"]
            }
        ]
    
    def search(self, query: str, max_results: int = 10, year_from: Optional[int] = None) -> List[Dict]:
        """Search for papers matching the query.
        
        Args:
            query: Search query string
            max_results: Maximum number of results
            year_from: Optional earliest year filter
            
        Returns:
            List of matching papers
        """
        query_lower = query.lower()
        results = []
        
        for paper in self.papers:
            # Simple relevance scoring
            score = 0
            searchable_text = (
                paper["title"].lower() + " " +
                paper["abstract"].lower() + " " +
                " ".join(paper["keywords"]).lower()
            )
            
            # Check if query terms appear
            query_terms = query_lower.split()
            for term in query_terms:
                if term in searchable_text:
                    score += 1
            
            if score > 0:
                # Apply year filter
                if year_from and paper["year"] < year_from:
                    continue
                    
                results.append({
                    **paper,
                    "relevance_score": score / len(query_terms)
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:max_results]


class MaterialPropertiesDatabase:
    """Mock material properties database.
    
    In production, this would connect to materials property databases
    or computational chemistry servers.
    """
    
    def __init__(self):
        # Known property ranges for materials
        self.properties = {
            "super sulfated cement": {
                "compressive_strength": {
                    "min": 30, "max": 55, "unit": "MPa", "age_days": 28,
                    "description": "28-day compressive strength range"
                },
                "flexural_strength": {
                    "min": 5, "max": 9, "unit": "MPa", "age_days": 28,
                    "description": "28-day flexural strength"
                },
                "ph": {
                    "min": 10.5, "max": 11.5, "unit": None,
                    "description": "Pore solution pH"
                },
                "sulfate_resistance": {
                    "min": 95, "max": 100, "unit": "%", "age_days": 90,
                    "description": "Relative durability factor"
                },
                "co2_emissions": {
                    "min": 150, "max": 250, "unit": "kg/tonne",
                    "description": "CO2 emissions per tonne of cement"
                }
            },
            "OPC": {
                "compressive_strength": {
                    "min": 35, "max": 60, "unit": "MPa", "age_days": 28,
                    "description": "28-day compressive strength"
                },
                "ph": {
                    "min": 12.5, "max": 13.5, "unit": None,
                    "description": "Pore solution pH"
                },
                "co2_emissions": {
                    "min": 800, "max": 950, "unit": "kg/tonne",
                    "description": "CO2 emissions per tonne"
                }
            },
            "blast furnace slag": {
                "activity_index": {
                    "min": 70, "max": 110, "unit": "%",
                    "description": "Relative to OPC at 28 days"
                }
            }
        }
    
    def validate(self, material: str, property_name: str, value: float) -> Dict[str, Any]:
        """Validate a property value against known ranges.
        
        Args:
            material: Material name
            property_name: Property to validate
            value: Value to check
            
        Returns:
            Validation result with status and confidence
        """
        material_lower = material.lower()
        
        # Find matching material
        material_data = None
        for key in self.properties:
            if key.lower() in material_lower or material_lower in key.lower():
                material_data = self.properties[key]
                break
        
        if material_data is None:
            return {
                "valid": None,
                "status": "unknown_material",
                "message": f"Material '{material}' not found in database",
                "confidence": 0
            }
        
        # Find matching property
        prop_data = None
        for key, data in material_data.items():
            if key.lower() == property_name.lower():
                prop_data = data
                break
        
        if prop_data is None:
            return {
                "valid": None,
                "status": "unknown_property",
                "message": f"Property '{property_name}' not found for {material}",
                "confidence": 0
            }
        
        # Validate value
        min_val = prop_data["min"]
        max_val = prop_data["max"]
        in_range = min_val <= value <= max_val
        
        # Calculate confidence based on how far from center
        center = (min_val + max_val) / 2
        range_half = (max_val - min_val) / 2
        deviation = abs(value - center) / range_half if range_half > 0 else 0
        confidence = max(0, 100 - deviation * 50)
        
        return {
            "valid": in_range,
            "status": "valid" if in_range else "out_of_range",
            "message": f"Value {value} is {'within' if in_range else 'outside'} "
                      f"expected range [{min_val}, {max_val}]",
            "expected_range": {"min": min_val, "max": max_val},
            "unit": prop_data.get("unit"),
            "confidence": confidence,
            "property_info": prop_data.get("description", "")
        }


# ============================================================================
# MCP Server Implementation
# ============================================================================

class MaterialsMCPServer:
    """MCP Server for materials science tools.
    
    This server implements the Model Context Protocol to expose
    materials science tools to AI agents.
    
    Attributes:
        tools: List of available MCP tools
        literature_db: Literature search database
        properties_db: Material properties database
    """
    
    def __init__(self):
        self.tools = create_mcp_tools()
        self.literature_db = LiteratureDatabase()
        self.properties_db = MaterialPropertiesDatabase()
    
    def handle_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an MCP request.
        
        Args:
            method: The MCP method name (e.g., 'tools/call')
            params: Method parameters
            
        Returns:
            MCP response
        """
        if method == "tools/list":
            return {
                "tools": self.tools
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            return self._execute_tool(tool_name, arguments)
        
        else:
            return {
                "error": f"Unknown method: {method}"
            }
    
    def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given arguments.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            if name == "search_literature":
                return self._search_literature(
                    query=arguments.get("query"),
                    max_results=arguments.get("max_results", 10),
                    year_from=arguments.get("year_from")
                )
            
            elif name == "validate_property":
                return self._validate_property(
                    material=arguments.get("material"),
                    property_name=arguments.get("property"),
                    value=arguments.get("value"),
                    unit=arguments.get("unit")
                )
            
            elif name == "generate_report":
                return self._generate_report(
                    title=arguments.get("title"),
                    literature_summary=arguments.get("literature_summary"),
                    hypotheses=arguments.get("hypotheses"),
                    validation_results=arguments.get("validation_results"),
                    format=arguments.get("format", "markdown")
                )
            
            else:
                return {"error": f"Unknown tool: {name}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def _search_literature(
        self,
        query: str,
        max_results: int = 10,
        year_from: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute literature search."""
        results = self.literature_db.search(
            query=query,
            max_results=max_results,
            year_from=year_from
        )
        
        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results
        }
    
    def _validate_property(
        self,
        material: str,
        property_name: str,
        value: float,
        unit: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute property validation."""
        result = self.properties_db.validate(
            material=material,
            property_name=property_name,
            value=value
        )
        
        return {
            "success": True,
            "material": material,
            "property": property_name,
            "input_value": value,
            "input_unit": unit,
            **result
        }
    
    def _generate_report(
        self,
        title: str,
        literature_summary: str = "",
        hypotheses: str = "",
        validation_results: str = "",
        format: str = "markdown"
    ) -> Dict[str, Any]:
        """Generate research report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report_content = f"""# {title}

**Generated:** {timestamp}  
**Framework:** NexusFlow Research Pipeline

---

## Executive Summary

This report summarizes the findings from automated literature mining, 
hypothesis generation, and validation analysis conducted by the 
NexusFlow multi-agent research system.

---

## Literature Summary

{literature_summary or '*No literature data provided*'}

---

## Research Hypotheses

{hypotheses or '*No hypotheses generated*'}

---

## Validation Results

{validation_results or '*No validation results available*'}

---

## Conclusions

Based on the analysis presented above, the following recommendations
are made for future research:

1. Prioritize high-confidence hypotheses for experimental validation
2. Address identified research gaps through targeted studies
3. Validate findings against independent datasets

---

*Report generated by NexusFlow MCP Server*
"""

        if format == "json":
            return {
                "success": True,
                "format": "json",
                "title": title,
                "timestamp": timestamp,
                "sections": {
                    "literature_summary": literature_summary,
                    "hypotheses": hypotheses,
                    "validation_results": validation_results
                }
            }
        else:
            return {
                "success": True,
                "format": format,
                "title": title,
                "timestamp": timestamp,
                "report": report_content
            }


# ============================================================================
# Standalone Server Entry Point
# ============================================================================

def run_server(host: str = "localhost", port: int = 8080):
    """Run the MCP server.
    
    This function starts the MCP server using stdio for communication,
    making it compatible with various MCP clients.
    
    Args:
        host: Server host (default: localhost)
        port: Server port (default: 8080)
    """
    import sys
    import asyncio
    
    server = MaterialsMCPServer()
    
    print(f"[INFO] Materials Science MCP Server starting...", file=sys.stderr)
    print(f"[INFO] Tools available: {len(server.tools)}", file=sys.stderr)
    print(f"[INFO] List tools: tools/list", file=sys.stderr)
    print(f"[INFO] Call tool: tools/call {{'name': 'search_literature', 'arguments': {{'query': 'cement'}}}}", file=sys.stderr)
    
    # For stdio-based communication
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            method = request.get("method", "")
            params = request.get("params", {})
            
            result = server.handle_request(method, params)
            
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": result
            }
            
            print(json.dumps(response))
            
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON"}))
        except Exception as e:
            print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    run_server()
