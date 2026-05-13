"""
CU (Custom Understanding) Analyzer Configuration Validator

A fully portable, standalone Python module to validate CU analyzer JSON configurations.
This validator checks for all possible failure cases and provides detailed, actionable error messages.

Usage:
    from cu_analyzer_validator import validate_cu_analyzer, validate_cu_analyzer_file
    
    # Validate a dictionary
    result = validate_cu_analyzer(config_dict)
    if not result.is_valid:
        for error in result.errors:
            print(error)
    
    # Validate a file
    result = validate_cu_analyzer_file("path/to/analyzer.json")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from enum import Enum
from pathlib import Path


class FieldType(Enum):
    """Valid field types in CU analyzer schema."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    DATE = "date"
    TIME = "time"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    CURRENCY = "currency"
    ADDRESS = "address"
    COUNTRY_REGION = "countryRegion"
    SELECTION_MARK = "selectionMark"
    SIGNATURE = "signature"
    SELECTION_GROUP = "selectionGroup"


class FieldMethod(Enum):
    """Valid extraction methods."""
    EXTRACT = "extract"
    GENERATE = "generate"
    CLASSIFY = "classify"


class TableFormat(Enum):
    """Valid table formats."""
    HTML = "html"
    MARKDOWN = "markdown"


class ChartFormat(Enum):
    """Valid chart formats."""
    CHARTJS = "chartjs"
    MARKDOWN = "markdown"


class AnnotationFormat(Enum):
    """Valid annotation formats."""
    MARKDOWN = "markdown"
    JSON = "json"


@dataclass
class ValidationError:
    """Represents a single validation error."""
    path: str
    message: str
    severity: str = "error"  # "error", "warning", "info"
    suggestion: Optional[str] = None
    
    def __str__(self) -> str:
        result = f"[{self.severity.upper()}] {self.path}: {self.message}"
        if self.suggestion:
            result += f"\n  → Suggestion: {self.suggestion}"
        return result


@dataclass
class ValidationResult:
    """Result of validation containing all errors and warnings."""
    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    info: List[ValidationError] = field(default_factory=list)
    field_count: int = 0
    max_depth: int = 0
    
    def add_error(self, path: str, message: str, suggestion: Optional[str] = None):
        """Add an error to the result."""
        self.errors.append(ValidationError(path, message, "error", suggestion))
        self.is_valid = False
    
    def add_warning(self, path: str, message: str, suggestion: Optional[str] = None):
        """Add a warning to the result."""
        self.warnings.append(ValidationError(path, message, "warning", suggestion))
    
    def add_info(self, path: str, message: str, suggestion: Optional[str] = None):
        """Add an info message to the result."""
        self.info.append(ValidationError(path, message, "info", suggestion))
    
    def get_summary(self) -> str:
        """Get a summary of the validation result."""
        status = "✅ VALID" if self.is_valid else "❌ INVALID"
        lines = [
            f"Validation Result: {status}",
            f"  Fields analyzed: {self.field_count}",
            f"  Maximum nesting depth: {self.max_depth}",
            f"  Errors: {len(self.errors)}",
            f"  Warnings: {len(self.warnings)}",
            f"  Info: {len(self.info)}",
        ]
        return "\n".join(lines)
    
    def get_all_messages(self) -> str:
        """Get all validation messages formatted."""
        lines = [self.get_summary(), ""]
        
        if self.errors:
            lines.append("=" * 60)
            lines.append("ERRORS:")
            lines.append("=" * 60)
            for error in self.errors:
                lines.append(str(error))
                lines.append("")
        
        if self.warnings:
            lines.append("-" * 60)
            lines.append("WARNINGS:")
            lines.append("-" * 60)
            for warning in self.warnings:
                lines.append(str(warning))
                lines.append("")
        
        if self.info:
            lines.append("-" * 60)
            lines.append("INFO:")
            lines.append("-" * 60)
            for info in self.info:
                lines.append(str(info))
                lines.append("")
        
        return "\n".join(lines)


class CUAnalyzerValidator:
    """
    Comprehensive validator for CU (Custom Understanding) Analyzer configurations.
    
    Validates:
    - JSON structure and syntax
    - Required top-level sections (config, fieldSchema)
    - Config options and their valid values
    - Field schema structure and types
    - Field naming conventions
    - Nested object/array structures
    - Method specifications
    - Description requirements
    - Circular reference detection
    - Character limits and constraints
    - Reserved keywords
    """
    
    # Constraints
    MAX_FIELD_NAME_LENGTH = 64
    MAX_DESCRIPTION_LENGTH = 4096
    MAX_NESTING_DEPTH = 10
    MAX_TOTAL_FIELDS = 500
    MAX_ARRAY_DEPTH = 5
    
    # Valid top-level keys in CU analyzer schemas
    VALID_TOP_LEVEL_KEYS = frozenset({
        "config", "fieldSchema", "$schema", "description", 
        "baseAnalyzerId", "models", "scenario"
    })
    
    # Reserved field names that cannot be used
    RESERVED_FIELD_NAMES = frozenset({
        "id", "type", "method", "description", "properties", "items",
        "content", "boundingRegions", "spans", "confidence", "source"
    })
    
    # Valid config keys and their expected types/values
    VALID_CONFIG_KEYS = {
        "returnDetails": bool,
        "enableOcr": bool,
        "enableLayout": bool,
        "enableFormula": bool,
        "enableFigureDescription": bool,
        "enableFigureAnalysis": bool,
        "chartFormat": {"chartjs", "markdown"},
        "disableContentFiltering": bool,
        "tableFormat": {"html", "markdown"},
        "estimateFieldSourceAndConfidence": bool,
        "enableSegment": bool,
        "omitContent": bool,
        "segmentPerPage": bool,
        "enableAnnotations": bool,
        "annotationFormat": {"markdown", "json"},
        "locale": str,
        "locales": list,
        "features": list,
        "queryFields": list,
        "contentCategories": dict,
        "enableFace": bool,
        "disableFaceBlurring": bool,
        "_experimental": dict,
    }
    
    # Field name pattern (alphanumeric, starting with letter, camelCase recommended)
    FIELD_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')
    
    def __init__(self):
        self.result = ValidationResult()
        self._visited_paths: Set[str] = set()
        self._current_depth = 0
        self._field_names_seen: Set[str] = set()
    
    def validate(self, config: Any) -> ValidationResult:
        """
        Validate a CU analyzer configuration.
        
        Args:
            config: The configuration to validate (dict or JSON string)
            
        Returns:
            ValidationResult with all errors, warnings, and info
        """
        self.result = ValidationResult()
        self._visited_paths = set()
        self._current_depth = 0
        self._field_names_seen = set()
        
        # Handle JSON string input
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError as e:
                self.result.add_error(
                    "root",
                    f"Invalid JSON syntax: {e.msg} at line {e.lineno}, column {e.colno}",
                    "Check for missing commas, unclosed brackets, or invalid escape sequences"
                )
                return self.result
        
        # Must be a dictionary
        if not isinstance(config, dict):
            self.result.add_error(
                "root",
                f"Configuration must be a JSON object (dict), got {type(config).__name__}",
                "Wrap your configuration in curly braces {}"
            )
            return self.result
        
        # Check for empty config
        if not config:
            self.result.add_error(
                "root",
                "Configuration is empty",
                "Add 'config' and 'fieldSchema' sections"
            )
            return self.result
        
        # Validate top-level structure
        self._validate_top_level_structure(config)
        
        # Validate config section
        if "config" in config:
            self._validate_config_section(config["config"])
        
        # Validate fieldSchema section
        if "fieldSchema" in config:
            self._validate_field_schema(config["fieldSchema"])
        
        # Check for unknown top-level keys
        unknown_keys = set(config.keys()) - self.VALID_TOP_LEVEL_KEYS
        for key in unknown_keys:
            self.result.add_warning(
                f"root.{key}",
                f"Unknown top-level key '{key}' will be ignored",
                f"Valid top-level keys are: {', '.join(sorted(self.VALID_TOP_LEVEL_KEYS))}"
            )
        
        # Set final statistics
        self.result.max_depth = self._current_depth
        
        return self.result
    
    def _validate_top_level_structure(self, config: Dict[str, Any]):
        """Validate that required top-level sections exist."""
        
        has_field_schema = "fieldSchema" in config
        has_content_categories = (
            "config" in config
            and isinstance(config.get("config"), dict)
            and "contentCategories" in config["config"]
        )
        
        # Either fieldSchema or contentCategories is required
        if not has_field_schema and not has_content_categories:
            self.result.add_error(
                "root",
                "Missing required 'fieldSchema' section (or 'config.contentCategories' for classify-and-route)",
                "Add a 'fieldSchema' with field definitions, or use 'config.contentCategories' to classify and route to inner analyzers"
            )
        elif has_field_schema and not isinstance(config["fieldSchema"], dict):
            self.result.add_error(
                "root.fieldSchema",
                f"'fieldSchema' must be an object, got {type(config['fieldSchema']).__name__}",
                "fieldSchema should be: { \"fields\": { ... } }"
            )
        
        # config is optional but recommended
        if "config" not in config:
            self.result.add_info(
                "root",
                "No 'config' section found - default values will be used",
                "Consider adding a 'config' section to customize analyzer behavior"
            )
        elif not isinstance(config.get("config"), dict):
            self.result.add_error(
                "root.config",
                f"'config' must be an object, got {type(config.get('config')).__name__}",
                "config should be: { \"returnDetails\": true, ... }"
            )
    
    def _validate_config_section(self, config_section: Any):
        """Validate the config section values."""
        if not isinstance(config_section, dict):
            return  # Already reported in top-level validation
        
        for key, value in config_section.items():
            path = f"config.{key}"
            
            if key not in self.VALID_CONFIG_KEYS:
                self.result.add_warning(
                    path,
                    f"Unknown config key '{key}'",
                    f"Valid config keys are: {', '.join(sorted(self.VALID_CONFIG_KEYS.keys()))}"
                )
                continue
            
            expected = self.VALID_CONFIG_KEYS[key]
            
            # Check type/value
            if isinstance(expected, set):
                # Enumerated values
                if value not in expected:
                    self.result.add_error(
                        path,
                        f"Invalid value '{value}' for '{key}'",
                        f"Valid values are: {', '.join(sorted(expected))}"
                    )
            elif expected == bool:
                if not isinstance(value, bool):
                    self.result.add_error(
                        path,
                        f"'{key}' must be a boolean (true/false), got {type(value).__name__}: {value}",
                        "Use true or false (without quotes)"
                    )
            elif expected == str:
                if not isinstance(value, str):
                    self.result.add_error(
                        path,
                        f"'{key}' must be a string, got {type(value).__name__}",
                        "Wrap the value in quotes"
                    )
            elif expected == list:
                if not isinstance(value, list):
                    self.result.add_error(
                        path,
                        f"'{key}' must be an array, got {type(value).__name__}",
                        "Use square brackets: []"
                    )
        
        # Check for conflicting options
        if config_section.get("enableSegment") and config_section.get("segmentPerPage"):
            self.result.add_warning(
                "config",
                "Both 'enableSegment' and 'segmentPerPage' are enabled",
                "Review if both segmentation options are intended"
            )
        
        # Validate contentCategories if present
        if "contentCategories" in config_section:
            self._validate_content_categories(config_section["contentCategories"])
    
    def _validate_content_categories(self, categories: Any):
        """Validate the contentCategories section for classify-and-route schemas."""
        if not isinstance(categories, dict):
            self.result.add_error(
                "config.contentCategories",
                f"'contentCategories' must be an object, got {type(categories).__name__}",
                "contentCategories should map category names to objects with 'description' and optional 'analyzerId'"
            )
            return
        
        if not categories:
            self.result.add_error(
                "config.contentCategories",
                "No categories defined in contentCategories",
                "Add at least one category (e.g., 'invoice': { 'description': '...', 'analyzerId': '...' })"
            )
            return
        
        has_analyzer_refs = False
        for cat_name, cat_def in categories.items():
            path = f"config.contentCategories.{cat_name}"
            
            if not isinstance(cat_def, dict):
                self.result.add_error(
                    path,
                    f"Category '{cat_name}' must be an object, got {type(cat_def).__name__}",
                    f"Define as: \"{cat_name}\": {{ \"description\": \"...\", \"analyzerId\": \"...\" }}"
                )
                continue
            
            # Description is required
            if "description" not in cat_def:
                self.result.add_error(
                    path,
                    f"Category '{cat_name}' is missing required 'description'",
                    "Add a description explaining what documents belong in this category"
                )
            elif not isinstance(cat_def["description"], str):
                self.result.add_error(
                    path,
                    f"Category '{cat_name}' description must be a string",
                    "Provide a text description of the category"
                )
            elif len(cat_def["description"]) < 10:
                self.result.add_warning(
                    path,
                    f"Category '{cat_name}' has a very short description ({len(cat_def['description'])} chars)",
                    "Provide detailed classification criteria for better accuracy"
                )
            
            # analyzerId is optional (some categories like 'other' may not route)
            if "analyzerId" in cat_def:
                has_analyzer_refs = True
                if not isinstance(cat_def["analyzerId"], str):
                    self.result.add_error(
                        path,
                        f"Category '{cat_name}' analyzerId must be a string",
                        "Provide the ID of the inner analyzer to route to"
                    )
                elif not cat_def["analyzerId"]:
                    self.result.add_warning(
                        path,
                        f"Category '{cat_name}' has an empty analyzerId",
                        "Provide the analyzer ID or remove the analyzerId key"
                    )
            
            # Check for unknown keys
            valid_category_keys = {"description", "analyzerId"}
            unknown = set(cat_def.keys()) - valid_category_keys
            for key in unknown:
                self.result.add_warning(
                    f"{path}.{key}",
                    f"Unknown key '{key}' in category '{cat_name}'",
                    f"Valid category keys are: {', '.join(sorted(valid_category_keys))}"
                )
        
        if has_analyzer_refs:
            self.result.add_info(
                "config.contentCategories",
                f"Classify-and-route schema with {len(categories)} categories",
                "Inner analyzers must be created before the classifier can route to them"
            )
    
    def _validate_field_schema(self, field_schema: Any):
        """Validate the fieldSchema section."""
        if not isinstance(field_schema, dict):
            return  # Already reported
        
        if "fields" not in field_schema:
            self.result.add_error(
                "fieldSchema",
                "Missing required 'fields' property in fieldSchema",
                "Add a 'fields' object containing your field definitions"
            )
            return
        
        fields = field_schema.get("fields")
        if not isinstance(fields, dict):
            self.result.add_error(
                "fieldSchema.fields",
                f"'fields' must be an object, got {type(fields).__name__}",
                "fields should be: { \"fieldName\": { \"type\": \"string\", ... }, ... }"
            )
            return
        
        if not fields:
            self.result.add_error(
                "fieldSchema.fields",
                "No fields defined in fieldSchema",
                "Add at least one field definition"
            )
            return
        
        # Validate each field
        sibling_names: Set[str] = set()
        for field_name, field_def in fields.items():
            self._validate_field(f"fieldSchema.fields.{field_name}", field_name, field_def, depth=1, is_array_item=False, sibling_names=sibling_names)
        
        # Check total field count
        if self.result.field_count > self.MAX_TOTAL_FIELDS:
            self.result.add_error(
                "fieldSchema.fields",
                f"Too many fields: {self.result.field_count} exceeds maximum of {self.MAX_TOTAL_FIELDS}",
                "Consider consolidating fields or splitting into multiple analyzers"
            )
    
    def _validate_field(self, path: str, field_name: str, field_def: Any, depth: int, is_array_item: bool = False, sibling_names: Optional[Set[str]] = None):
        """Validate a single field definition recursively."""
        self.result.field_count += 1
        self._current_depth = max(self._current_depth, depth)
        
        # Check nesting depth
        if depth > self.MAX_NESTING_DEPTH:
            self.result.add_error(
                path,
                f"Maximum nesting depth of {self.MAX_NESTING_DEPTH} exceeded",
                "Flatten your field structure or reduce nesting"
            )
            return
        
        # Validate field name (skip for array items which use synthetic name)
        if not is_array_item:
            self._validate_field_name(path, field_name, sibling_names)
        
        # Field must be an object
        if not isinstance(field_def, dict):
            self.result.add_error(
                path,
                f"Field definition must be an object, got {type(field_def).__name__}",
                "Field should be: { \"type\": \"string\", \"description\": \"...\", ... }"
            )
            return
        
        # Check for empty field definition
        if not field_def:
            self.result.add_error(
                path,
                "Empty field definition",
                "Add at least 'type' and 'description' properties"
            )
            return
        
        # Type is required
        if "type" not in field_def:
            self.result.add_error(
                path,
                "Missing required 'type' property",
                f"Add a type property. Valid types: {', '.join(t.value for t in FieldType)}"
            )
            return
        
        field_type = field_def.get("type")
        
        # Validate type value
        valid_types = {t.value for t in FieldType}
        if field_type not in valid_types:
            self.result.add_error(
                f"{path}.type",
                f"Invalid field type '{field_type}'",
                f"Valid types are: {', '.join(sorted(valid_types))}"
            )
            return
        
        # Validate description
        self._validate_description(path, field_def)
        
        # Validate method if present
        if "method" in field_def:
            self._validate_method(path, field_def.get("method"), field_type)
        
        # Type-specific validation
        if field_type == "object":
            self._validate_object_field(path, field_def, depth)
        elif field_type == "array":
            self._validate_array_field(path, field_def, depth)
        else:
            # Scalar types should not have properties or items
            if "properties" in field_def:
                self.result.add_error(
                    f"{path}.properties",
                    f"Field type '{field_type}' cannot have 'properties' (only 'object' type can)",
                    f"Change type to 'object' or remove 'properties'"
                )
            if "items" in field_def:
                self.result.add_error(
                    f"{path}.items",
                    f"Field type '{field_type}' cannot have 'items' (only 'array' type can)",
                    f"Change type to 'array' or remove 'items'"
                )
        
        # Check for unknown properties in field definition
        self._check_unknown_field_properties(path, field_def, field_type)
    
    def _validate_field_name(self, path: str, field_name: str, sibling_names: Optional[Set[str]] = None):
        """Validate field naming conventions."""
        
        # Check length
        if len(field_name) > self.MAX_FIELD_NAME_LENGTH:
            self.result.add_error(
                path,
                f"Field name '{field_name}' exceeds maximum length of {self.MAX_FIELD_NAME_LENGTH} characters",
                "Use a shorter, more concise field name"
            )
        
        # Check pattern
        if not self.FIELD_NAME_PATTERN.match(field_name):
            self.result.add_error(
                path,
                f"Invalid field name '{field_name}': must start with a letter and contain only alphanumeric characters and underscores",
                "Use camelCase naming (e.g., 'firstName', 'totalAmount')"
            )
        
        # Check for reserved names at root level
        if field_name.lower() in {r.lower() for r in self.RESERVED_FIELD_NAMES}:
            self.result.add_warning(
                path,
                f"Field name '{field_name}' may conflict with reserved system field names",
                "Consider using a more specific name to avoid potential conflicts"
            )
        
        # Check for duplicates within the same scope (case-insensitive)
        if sibling_names is not None:
            field_name_lower = field_name.lower()
            if field_name_lower in sibling_names:
                self.result.add_error(
                    path,
                    f"Duplicate field name '{field_name}' (case-insensitive) within the same object",
                    "Use unique field names within the same object"
                )
            sibling_names.add(field_name_lower)
    
    def _validate_description(self, path: str, field_def: Dict[str, Any]):
        """Validate field description."""
        description = field_def.get("description")
        
        if description is None:
            self.result.add_warning(
                path,
                "Missing 'description' property",
                "Add a description to improve extraction accuracy. Descriptions help the model understand what to extract."
            )
            return
        
        if not isinstance(description, str):
            self.result.add_error(
                f"{path}.description",
                f"Description must be a string, got {type(description).__name__}",
                "Wrap the description in quotes"
            )
            return
        
        if not description.strip():
            self.result.add_warning(
                f"{path}.description",
                "Description is empty or whitespace-only",
                "Add a meaningful description to guide extraction"
            )
            return
        
        # Check length
        if len(description) > self.MAX_DESCRIPTION_LENGTH:
            self.result.add_error(
                f"{path}.description",
                f"Description exceeds maximum length of {self.MAX_DESCRIPTION_LENGTH} characters",
                "Shorten the description while keeping key instructions"
            )
    
    def _validate_method(self, path: str, method: Any, field_type: str):
        """Validate extraction method."""
        valid_methods = {m.value for m in FieldMethod}
        
        if not isinstance(method, str):
            self.result.add_error(
                f"{path}.method",
                f"Method must be a string, got {type(method).__name__}",
                f"Valid methods are: {', '.join(sorted(valid_methods))}"
            )
            return
        
        if method not in valid_methods:
            self.result.add_error(
                f"{path}.method",
                f"Invalid method '{method}'",
                f"Valid methods are: {', '.join(sorted(valid_methods))}"
            )
    
    def _validate_object_field(self, path: str, field_def: Dict[str, Any], depth: int):
        """Validate object type field."""
        
        if "properties" not in field_def:
            self.result.add_error(
                path,
                "Object field missing required 'properties' property",
                "Add 'properties': { \"subFieldName\": { \"type\": \"...\", ... }, ... }"
            )
            return
        
        properties = field_def.get("properties")
        
        if not isinstance(properties, dict):
            self.result.add_error(
                f"{path}.properties",
                f"'properties' must be an object, got {type(properties).__name__}",
                "properties should contain field definitions as key-value pairs"
            )
            return
        
        if not properties:
            return  # Empty properties is allowed by API
        
        # Validate each property
        sibling_names: Set[str] = set()
        for prop_name, prop_def in properties.items():
            self._validate_field(f"{path}.properties.{prop_name}", prop_name, prop_def, depth + 1, is_array_item=False, sibling_names=sibling_names)
    
    def _validate_array_field(self, path: str, field_def: Dict[str, Any], depth: int):
        """Validate array type field."""
        
        if "items" not in field_def:
            self.result.add_error(
                path,
                "Array field missing required 'items' property",
                "Add 'items': { \"type\": \"object\", \"properties\": { ... } }"
            )
            return
        
        items = field_def.get("items")
        
        if not isinstance(items, dict):
            self.result.add_error(
                f"{path}.items",
                f"'items' must be an object, got {type(items).__name__}",
                "items should define the structure of array elements"
            )
            return
        
        if not items:
            self.result.add_error(
                f"{path}.items",
                "Array 'items' definition is empty",
                "Define the structure of array elements"
            )
            return
        
        # Check array nesting depth
        array_depth = self._count_array_depth(field_def)
        if array_depth > self.MAX_ARRAY_DEPTH:
            self.result.add_error(
                path,
                f"Array nesting depth of {array_depth} exceeds maximum of {self.MAX_ARRAY_DEPTH}",
                "Flatten your array structure"
            )
        
        # Validate items as a field definition (mark as array item to skip name validation)
        self._validate_field(f"{path}.items", "[item]", items, depth + 1, is_array_item=True, sibling_names=None)
    
    def _count_array_depth(self, field_def: Dict[str, Any], current_depth: int = 1) -> int:
        """Count the nesting depth of arrays."""
        if field_def.get("type") != "array":
            return 0
        
        items = field_def.get("items", {})
        if items.get("type") == "array":
            return current_depth + self._count_array_depth(items, current_depth + 1)
        
        # Check for arrays in object properties
        max_depth = current_depth
        if items.get("type") == "object":
            properties = items.get("properties", {})
            for prop_def in properties.values():
                if isinstance(prop_def, dict) and prop_def.get("type") == "array":
                    nested_depth = current_depth + self._count_array_depth(prop_def, 1)
                    max_depth = max(max_depth, nested_depth)
        
        return max_depth
    
    def _check_unknown_field_properties(self, path: str, field_def: Dict[str, Any], field_type: str):
        """Check for unknown properties in field definition."""
        
        # Known properties for all fields
        common_properties = {
            "type", "description", "method", "example", "examples"
        }
        
        # Type-specific known properties
        type_specific = {
            "object": {"properties"},
            "array": {"items", "minItems", "maxItems"},
            "string": {"enum", "pattern", "minLength", "maxLength", "format"},
            "number": {"minimum", "maximum", "multipleOf"},
            "integer": {"minimum", "maximum", "multipleOf"},
            "date": {"format"},
            "time": {"format"},
        }
        
        known = common_properties | type_specific.get(field_type, set())
        
        for key in field_def.keys():
            if key not in known:
                # Don't warn about common extensions
                if key in {"$comment", "$ref", "title", "default"}:
                    continue
                self.result.add_info(
                    f"{path}.{key}",
                    f"Property '{key}' may not be recognized by CU analyzer",
                    "Verify this property is supported or remove if not needed"
                )


def validate_cu_analyzer(config: Union[str, Dict[str, Any]]) -> ValidationResult:
    """
    Validate a CU analyzer configuration.
    
    Args:
        config: Either a dictionary containing the configuration,
                or a JSON string to parse
    
    Returns:
        ValidationResult with is_valid flag and detailed error/warning lists
    
    Example:
        >>> config = {"fieldSchema": {"fields": {"name": {"type": "string"}}}}
        >>> result = validate_cu_analyzer(config)
        >>> print(result.is_valid)
        True
    """
    validator = CUAnalyzerValidator()
    return validator.validate(config)


def validate_cu_analyzer_file(file_path: Union[str, Path]) -> ValidationResult:
    """
    Validate a CU analyzer configuration from a JSON file.
    
    Args:
        file_path: Path to the JSON file containing the analyzer configuration
    
    Returns:
        ValidationResult with is_valid flag and detailed error/warning lists
    
    Example:
        >>> result = validate_cu_analyzer_file("analyzer.json")
        >>> if not result.is_valid:
        ...     print(result.get_all_messages())
    """
    result = ValidationResult()
    
    file_path = Path(file_path)
    
    if not file_path.exists():
        result.add_error(
            "file",
            f"File not found: {file_path}",
            "Check the file path and ensure the file exists"
        )
        return result
    
    if not file_path.is_file():
        result.add_error(
            "file",
            f"Path is not a file: {file_path}",
            "Provide a path to a JSON file"
        )
        return result
    
    if file_path.suffix.lower() not in ('.json', '.jsonc'):
        result.add_warning(
            "file",
            f"File extension '{file_path.suffix}' is not .json",
            "CU analyzer configurations should use .json extension"
        )
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError as e:
        result.add_error(
            "file",
            f"File encoding error: {e}",
            "Ensure the file is saved with UTF-8 encoding"
        )
        return result
    except IOError as e:
        result.add_error(
            "file",
            f"Error reading file: {e}",
            "Check file permissions and try again"
        )
        return result
    
    # Remove BOM if present
    if content.startswith('\ufeff'):
        content = content[1:]
        result.add_info(
            "file",
            "File contains UTF-8 BOM (byte order mark)",
            "Consider saving without BOM for better compatibility"
        )
    
    return validate_cu_analyzer(content)


def validate_and_print(config: Union[str, Dict[str, Any], Path]) -> bool:
    """
    Convenience function to validate and print results.
    
    Args:
        config: Configuration dict, JSON string, or file path
    
    Returns:
        True if valid, False otherwise
    """
    if isinstance(config, Path) or (isinstance(config, str) and 
                                     (config.endswith('.json') or '\\' in config or '/' in config)):
        result = validate_cu_analyzer_file(config)
    else:
        result = validate_cu_analyzer(config)
    
    print(result.get_all_messages())
    return result.is_valid


# Command-line interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python cu_analyzer_validator.py <path_to_analyzer.json>")
        print("\nValidates a CU (Custom Understanding) Analyzer JSON configuration file.")
        print("\nExample:")
        print("  python cu_analyzer_validator.py my-analyzer.json")
        sys.exit(1)
    
    file_path = sys.argv[1]
    is_valid = validate_and_print(file_path)
    sys.exit(0 if is_valid else 1)
