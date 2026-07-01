# -*- coding: utf-8 -*-
"""
Data Validation Tool.

This module provides functionality for validating material properties
and experimental data against known ranges and literature values.

Usage:
    >>> from agent4science.tools import DataValidatorTool
    >>> validator = DataValidatorTool()
    >>> result = validator.validate("super sulfated cement", "compressive_strength", 42.5)
    >>> print(result)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationResult:
    """Result of a property validation."""
    material: str
    property_name: str
    value: float
    unit: Optional[str]
    is_valid: bool
    status: str  # "valid", "out_of_range", "unknown_material", "unknown_property"
    expected_range: Optional[Dict[str, float]]
    confidence: float  # 0-100
    message: str
    property_info: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class MaterialPropertyDatabase:
    """Database of known material property ranges.
    
    This class stores experimental property ranges extracted from
    literature, enabling validation of new measurements.
    """
    
    def __init__(self):
        # Initialize with known property ranges
        self.properties: Dict[str, Dict[str, Dict[str, Any]]] = {
            "super sulfated cement": {
                "compressive_strength": {
                    "min": 30.0,
                    "max": 55.0,
                    "unit": "MPa",
                    "age": "28 days",
                    "confidence": 95,
                    "source": "Zhang et al. 2023",
                    "description": "28-day compressive strength range for SSC"
                },
                "flexural_strength": {
                    "min": 5.0,
                    "max": 9.0,
                    "unit": "MPa",
                    "age": "28 days",
                    "confidence": 90,
                    "source": "Literature survey",
                    "description": "28-day flexural strength"
                },
                "ph": {
                    "min": 10.5,
                    "max": 11.5,
                    "unit": None,
                    "age": None,
                    "confidence": 98,
                    "source": "Wang & Brown 2021",
                    "description": "Pore solution pH at equilibrium"
                },
                "sulfate_resistance": {
                    "min": 95.0,
                    "max": 100.0,
                    "unit": "%",
                    "age": "90 days",
                    "confidence": 92,
                    "source": "ASTM C1012 testing",
                    "description": "Relative durability factor after sulfate exposure"
                },
                "co2_emissions": {
                    "min": 150.0,
                    "max": 250.0,
                    "unit": "kg CO2/tonne",
                    "age": None,
                    "confidence": 97,
                    "source": "LCA studies",
                    "description": "CO2 emissions per tonne of cement"
                },
                "freeze_thaw_durability": {
                    "min": 90.0,
                    "max": 98.0,
                    "unit": "%",
                    "age": "300 cycles",
                    "confidence": 88,
                    "source": "Chen et al. 2022",
                    "description": "Durability factor per ASTM C666"
                },
                "setting_time_initial": {
                    "min": 45.0,
                    "max": 180.0,
                    "unit": "minutes",
                    "age": None,
                    "confidence": 85,
                    "source": "Literature review",
                    "description": "Initial setting time by Vicat needle"
                },
                "setting_time_final": {
                    "min": 180.0,
                    "max": 360.0,
                    "unit": "minutes",
                    "age": None,
                    "confidence": 85,
                    "source": "Literature review",
                    "description": "Final setting time by Vicat needle"
                }
            },
            "OPC": {
                "compressive_strength": {
                    "min": 35.0,
                    "max": 60.0,
                    "unit": "MPa",
                    "age": "28 days",
                    "confidence": 99,
                    "source": "ASTM C150",
                    "description": "Standard 28-day compressive strength"
                },
                "ph": {
                    "min": 12.5,
                    "max": 13.5,
                    "unit": None,
                    "age": None,
                    "confidence": 99,
                    "source": "Standard reference",
                    "description": "Pore solution pH"
                },
                "co2_emissions": {
                    "min": 800.0,
                    "max": 950.0,
                    "unit": "kg CO2/tonne",
                    "age": None,
                    "confidence": 99,
                    "source": "Industry data",
                    "description": "Average CO2 emissions"
                }
            },
            "blast furnace slag": {
                "activity_index": {
                    "min": 70.0,
                    "max": 110.0,
                    "unit": "%",
                    "age": "28 days",
                    "confidence": 95,
                    "source": "ASTM C989",
                    "description": "Relative to OPC at same age"
                },
                "glass_content": {
                    "min": 85.0,
                    "max": 100.0,
                    "unit": "%",
                    "age": None,
                    "confidence": 90,
                    "source": "XRD analysis",
                    "description": "Amorphous glass content requirement"
                }
            }
        }
    
    def get_property_range(self, material: str, property_name: str) -> Optional[Dict[str, Any]]:
        """Get the expected range for a material property.
        
        Args:
            material: Material name
            property_name: Property name
            
        Returns:
            Property data dict or None if not found
        """
        # Case-insensitive lookup
        material_lower = material.lower()
        property_lower = property_name.lower()
        
        # Find matching material
        for mat_key in self.properties:
            if material_lower in mat_key.lower() or mat_key.lower() in material_lower:
                # Find matching property
                for prop_key in self.properties[mat_key]:
                    if property_lower in prop_key.lower() or prop_key.lower() in property_lower:
                        return self.properties[mat_key][prop_key]
        
        return None
    
    def list_materials(self) -> List[str]:
        """Get list of available materials."""
        return list(self.properties.keys())
    
    def list_properties(self, material: str) -> List[str]:
        """Get list of properties for a material."""
        material_lower = material.lower()
        for mat_key in self.properties:
            if material_lower in mat_key.lower() or mat_key.lower() in material_lower:
                return list(self.properties[mat_key].keys())
        return []


class DataValidatorTool:
    """Tool for validating material property data.
    
    This tool validates experimental measurements against known
    property ranges from literature, helping identify potential
    errors or novel findings.
    
    Attributes:
        db: Material property database
        
    Example:
        >>> validator = DataValidatorTool()
        >>> result = validator.validate(
        ...     material="super sulfated cement",
        ...     property_name="compressive_strength",
        ...     value=42.5
        ... )
        >>> if result.is_valid:
        ...     print("Property value is within expected range")
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the data validator.
        
        Args:
            api_key: Optional API key for extended validation services
        """
        self.db = MaterialPropertyDatabase()
        self.api_key = api_key
    
    def validate(
        self,
        material: str,
        property_name: str,
        value: float,
        unit: Optional[str] = None,
        strict: bool = False
    ) -> ValidationResult:
        """Validate a material property value.
        
        Args:
            material: Material name
            property_name: Property being validated
            value: Measured/proposed value
            unit: Optional unit specification
            strict: If True, require exact unit match
            
        Returns:
            ValidationResult with status and confidence
            
        Example:
            >>> result = validator.validate(
            ...     "super sulfated cement",
            ...     "compressive_strength",
            ...     42.5
            ... )
        """
        prop_data = self.db.get_property_range(material, property_name)
        
        if prop_data is None:
            return ValidationResult(
                material=material,
                property_name=property_name,
                value=value,
                unit=unit,
                is_valid=False,
                status="unknown_property",
                expected_range=None,
                confidence=0.0,
                message=f"Property '{property_name}' not found for '{material}'"
            )
        
        min_val = prop_data["min"]
        max_val = prop_data["max"]
        expected_unit = prop_data.get("unit")
        
        # Check unit compatibility (simplified)
        if unit and expected_unit and unit != expected_unit:
            # Could add unit conversion here
            if strict:
                return ValidationResult(
                    material=material,
                    property_name=property_name,
                    value=value,
                    unit=unit,
                    is_valid=False,
                    status="unit_mismatch",
                    expected_range={"min": min_val, "max": max_val},
                    confidence=0.0,
                    message=f"Unit mismatch: expected {expected_unit}, got {unit}"
                )
        
        # Check if value is within range
        in_range = min_val <= value <= max_val
        
        # Calculate confidence based on position within range
        center = (min_val + max_val) / 2
        range_half = (max_val - min_val) / 2
        
        if range_half > 0:
            deviation = abs(value - center) / range_half
            position_confidence = max(0, 100 - deviation * 50)
        else:
            position_confidence = 100 if value == center else 0
        
        # Combine with source confidence
        source_confidence = prop_data.get("confidence", 90)
        final_confidence = (position_confidence + source_confidence) / 2
        
        if in_range:
            message = f"Value {value} is within expected range [{min_val}, {max_val}]"
            if expected_unit:
                message += f" {expected_unit}"
        else:
            distance = min(abs(value - min_val), abs(value - max_val))
            if value < min_val:
                message = f"Value {value} is below expected minimum {min_val}"
            else:
                message = f"Value {value} is above expected maximum {max_val}"
        
        return ValidationResult(
            material=material,
            property_name=property_name,
            value=value,
            unit=unit or expected_unit,
            is_valid=in_range,
            status="valid" if in_range else "out_of_range",
            expected_range={"min": min_val, "max": max_val},
            confidence=final_confidence,
            message=message,
            property_info=prop_data.get("description")
        )
    
    def validate_batch(
        self,
        data: List[Dict[str, Any]]
    ) -> List[ValidationResult]:
        """Validate multiple properties at once.
        
        Args:
            data: List of dicts with 'material', 'property', 'value', optional 'unit'
            
        Returns:
            List of ValidationResult objects
        """
        results = []
        for item in data:
            result = self.validate(
                material=item["material"],
                property_name=item["property"],
                value=item["value"],
                unit=item.get("unit")
            )
            results.append(result)
        return results
    
    def get_expected_values(
        self,
        material: str,
        property_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get expected value information for a property.
        
        Args:
            material: Material name
            property_name: Property name
            
        Returns:
            Dict with min, max, unit, source, etc. or None
        """
        return self.db.get_property_range(material, property_name)
    
    def list_available_properties(self, material: str) -> List[str]:
        """List all validatable properties for a material."""
        return self.db.list_properties(material)


# Convenience function for quick validation
def validate_property(
    material: str,
    property_name: str,
    value: float,
    unit: Optional[str] = None
) -> ValidationResult:
    """Quick property validation.
    
    Args:
        material: Material name
        property_name: Property name
        value: Value to validate
        unit: Optional unit
        
    Returns:
        ValidationResult
    """
    validator = DataValidatorTool()
    return validator.validate(material, property_name, value, unit)


if __name__ == "__main__":
    # Demo usage
    print("=" * 60)
    print("Data Validation Tool - Demo")
    print("=" * 60)
    
    validator = DataValidatorTool()
    
    # List available materials
    print("\nAvailable Materials:")
    for mat in validator.db.list_materials():
        print(f"  - {mat}")
        props = validator.db.list_properties(mat)
        for prop in props[:3]:  # Show first 3
            print(f"      • {prop}")
        if len(props) > 3:
            print(f"      ... and {len(props) - 3} more")
    
    print("\n" + "-" * 60)
    print("Validation Examples:")
    print("-" * 60)
    
    # Test valid value
    result = validator.validate("super sulfated cement", "compressive_strength", 42.5)
    print(f"\n[Test 1] Compressive Strength = 42.5 MPa")
    print(f"  Status: {result.status}")
    print(f"  Valid: {result.is_valid}")
    print(f"  Confidence: {result.confidence:.1f}%")
    print(f"  Range: [{result.expected_range['min']}, {result.expected_range['max']}]")
    
    # Test out of range
    result2 = validator.validate("super sulfated cement", "compressive_strength", 80.0)
    print(f"\n[Test 2] Compressive Strength = 80.0 MPa")
    print(f"  Status: {result2.status}")
    print(f"  Valid: {result2.is_valid}")
    print(f"  Message: {result2.message}")
    
    # Test pH validation
    result3 = validator.validate("super sulfated cement", "ph", 11.0)
    print(f"\n[Test 3] pH = 11.0")
    print(f"  Status: {result3.status}")
    print(f"  Valid: {result3.is_valid}")
    print(f"  Confidence: {result3.confidence:.1f}%")
