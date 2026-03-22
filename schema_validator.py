#!/usr/bin/env python3
"""
Schema Validator - Validate configuration files against JSON Schema.
Supports loading schemas from files or inline definitions.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_AVAILABLE = False
ValidationError = None

try:
    import jsonschema
    from jsonschema import Draft7Validator, Draft202012Validator
    from jsonschema.exceptions import ValidationError
    SCHEMA_AVAILABLE = True
except ImportError:
    pass


class SchemaValidationResult:
    """Represents a single schema validation error."""

    def __init__(self, path: List[str], message: str, validator: str, value: Any = None):
        self.path = path
        self.message = message
        self.validator = validator
        self.value = value

    def __str__(self) -> str:
        path_str = self._format_path()
        return f"[{path_str}] {self.message} (validator: {self.validator})"

    def _format_path(self) -> str:
        """Format the path for display, handling array indices."""
        if not self.path:
            return "(root)"
        
        parts = []
        for p in self.path:
            if isinstance(p, int):
                parts.append(f"[{p}]")
            else:
                if parts and not str(parts[-1]).startswith('['):
                    parts.append('.')
                parts.append(str(p))
        
        result = ''.join(str(p) for p in parts)
        return result if result else "(root)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "message": self.message,
            "validator": self.validator,
            "value": self.value
        }


class SchemaValidator:
    """Validate configuration data against JSON Schema."""

    def __init__(self, schema: Optional[Dict[str, Any]] = None, schema_path: Optional[str] = None):
        if not SCHEMA_AVAILABLE:
            raise ImportError(
                "jsonschema not available. Install with: pip install jsonschema"
            )

        if schema is None and schema_path is None:
            raise ValueError("Either schema or schema_path must be provided")

        self.schema = schema
        self.schema_path = schema_path

        if self.schema_path:
            self.schema = self._load_schema(schema_path)

        self._determine_validator()

    def _load_schema(self, path: str) -> Dict[str, Any]:
        """Load schema from a JSON file."""
        schema_file = Path(path)

        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")

        try:
            content = schema_file.read_text(encoding="utf-8")
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in schema file: {e}")
        except UnicodeDecodeError as e:
            raise ValueError(f"Cannot read schema file (encoding issue): {e}")

    def _determine_validator(self) -> None:
        """Determine the appropriate validator based on schema version."""
        if self.schema is None:
            raise ValueError("No schema loaded")

        schema_version = self.schema.get("$schema", "")

        if "2020-12" in schema_version:
            self.validator_cls = Draft202012Validator
        elif "draft-07" in schema_version or not schema_version:
            self.validator_cls = Draft7Validator
        else:
            self.validator_cls = Draft7Validator

    def validate(self, data: Any) -> List[SchemaValidationResult]:
        """Validate data against the schema."""
        results = []

        if self.schema is None:
            raise ValueError("No schema loaded")

        validator = self.validator_cls(self.schema)

        for error in validator.iter_errors(data):
            result = SchemaValidationResult(
                path=list(error.absolute_path),
                message=self._format_error_message(error),
                validator=error.validator,
                value=error.instance
            )
            results.append(result)

            for sub_error in error.context:
                sub_result = SchemaValidationResult(
                    path=list(sub_error.absolute_path),
                    message=self._format_error_message(sub_error),
                    validator=sub_error.validator,
                    value=sub_error.instance
                )
                results.append(sub_result)

        return results

    def _format_error_message(self, error: ValidationError) -> str:
        """Format a validation error into a human-readable message."""
        if error.validator == "required":
            missing_props = [p for p in error.validator_value if p not in error.instance]
            return f"Missing required property: {', '.join(missing_props)}"

        elif error.validator == "type":
            expected = error.validator_value
            actual = type(error.instance).__name__
            return f"Type mismatch: expected {expected}, got {actual}"

        elif error.validator == "minimum":
            return f"Value {error.instance} is less than minimum {error.validator_value}"

        elif error.validator == "maximum":
            return f"Value {error.instance} is greater than maximum {error.validator_value}"

        elif error.validator == "minLength":
            return f"String length {len(error.instance)} is less than minimum {error.validator_value}"

        elif error.validator == "maxLength":
            return f"String length {len(error.instance)} is greater than maximum {error.validator_value}"

        elif error.validator == "pattern":
            return f"String does not match pattern: {error.validator_value}"

        elif error.validator == "enum":
            return f"Value must be one of: {', '.join(str(v) for v in error.validator_value)}"

        elif error.validator == "minItems":
            return f"Array has too few items: {len(error.instance)} (minimum: {error.validator_value})"

        elif error.validator == "maxItems":
            return f"Array has too many items: {len(error.instance)} (maximum: {error.validator_value})"

        elif error.validator == "uniqueItems":
            return "Array items must be unique"

        elif error.validator == "format":
            return f"String does not match format: {error.validator_value}"

        elif error.validator == "additionalProperties":
            extra_props = set(error.instance.keys()) - set(error.schema.get('properties', {}).keys())
            if extra_props:
                return f"Additional properties not allowed: {', '.join(extra_props)}"
            return "Additional properties not allowed"

        elif error.validator == "minProperties":
            return f"Object has too few properties: {len(error.instance)} (minimum: {error.validator_value})"

        elif error.validator == "maxProperties":
            return f"Object has too many properties: {len(error.instance)} (maximum: {error.validator_value})"

        elif error.validator == "const":
            return f"Value must be exactly: {error.validator_value}"

        elif error.validator == "multipleOf":
            return f"Value {error.instance} is not a multiple of {error.validator_value}"

        elif error.validator == "exclusiveMinimum":
            return f"Value {error.instance} must be greater than (not equal to) {error.validator_value}"

        elif error.validator == "exclusiveMaximum":
            return f"Value {error.instance} must be less than (not equal to) {error.validator_value}"

        elif error.validator == "oneOf":
            return f"Value must match exactly one schema, but matched {len(error.context)} or none"

        elif error.validator == "anyOf":
            return f"Value must match at least one schema"

        elif error.validator == "allOf":
            return f"Value must match all schemas"

        elif error.validator == "if":
            return f"Conditional schema validation failed"

        elif error.validator == "then":
            return f"'then' clause validation failed"

        elif error.validator == "else":
            return f"'else' clause validation failed"

        elif error.validator == "not":
            return f"Value must not match the schema"

        elif error.validator == "propertyNames":
            return f"Property name validation failed"

        elif error.validator == "contains":
            return f"Array must contain at least one item matching the schema"

        elif error.validator == "dependentRequired":
            return f"Missing dependent required properties: {', '.join(error.validator_value)}"

        elif error.validator == "dependentSchemas":
            return f"Dependent schema validation failed"

        elif error.validator == "prefixItems":
            return f"Array items do not match prefix schema"

        elif error.validator == "unevaluatedProperties":
            return f"Unevaluated properties not allowed"

        elif error.validator == "unevaluatedItems":
            return f"Unevaluated items not allowed"

        else:
            return error.message

    def is_valid(self, data: Any) -> bool:
        """Check if data is valid against the schema."""
        return len(self.validate(data)) == 0


def load_schema_from_file(path: str) -> Dict[str, Any]:
    """Load a JSON schema from a file."""
    schema_file = Path(path)

    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    try:
        content = schema_file.read_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in schema file: {e}")


def create_basic_schema(properties: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    """Create a basic JSON schema from property definitions."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": properties
    }

    if required:
        schema["required"] = required

    return schema


def create_nested_schema(
    nested_props: Dict[str, Any],
    required: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Create a JSON schema with nested property support.
    
    Args:
        nested_props: Dictionary with dot-notation keys for nested properties.
                      Example: {"database.host": {"type": "string"}, "database.port": {"type": "integer"}}
        required: List of required properties (also supports dot-notation)
    
    Returns:
        A JSON Schema dictionary with proper nested structure.
    """
    def set_nested(schema_dict: Dict, path: str, value: Any) -> None:
        keys = path.split('.')
        current = schema_dict
        for key in keys[:-1]:
            if key not in current:
                current[key] = {"type": "object", "properties": {}}
            if "properties" not in current[key]:
                current[key]["properties"] = {}
            current = current[key]["properties"]
        current[keys[-1]] = value

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {}
    }

    for prop_path, prop_schema in nested_props.items():
        set_nested(schema["properties"], prop_path, prop_schema)

    if required:
        schema["required"] = required

    return schema


def validate_config_file(
    config_path: str,
    schema: Optional[Dict[str, Any]] = None,
    schema_path: Optional[str] = None
) -> Tuple[bool, List[SchemaValidationResult]]:
    """Validate a configuration file against a schema."""
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        content = config_file.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"Cannot read config file (encoding issue): {e}")

    suffix = config_file.suffix.lower()

    if suffix == ".json":
        import json
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
    elif suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            raise ImportError("PyYAML not available for YAML parsing")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
    elif suffix in (".toml",):
        try:
            import tomli
            data = tomli.loads(content)
        except ImportError:
            try:
                import tomllib as tomli
                data = tomli.loads(content)
            except ImportError:
                raise ImportError("tomli not available for TOML parsing")
        except tomli.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML in config file: {e}")
    else:
        raise ValueError(f"Unsupported config format: {suffix}")

    validator = SchemaValidator(schema=schema, schema_path=schema_path)
    results = validator.validate(data)

    return len(results) == 0, results
