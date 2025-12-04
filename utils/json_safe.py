#!/usr/bin/env python3
"""
Safe JSON Operations - Prevents crashes from malformed JSON.

Features:
- Try-catch wrappers for all JSON operations
- Validation before parsing
- Size limits
- Schema validation
- Graceful degradation
"""

import json
import logging
from typing import Any, Optional, Dict, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class JSONParseError(Exception):
    """Raised when JSON parsing fails."""
    pass


class JSONValidator:
    """Validates JSON data before parsing."""
    
    MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB default
    
    @staticmethod
    def validate_json_string(json_str: str, max_size: Optional[int] = None) -> bool:
        """
        Validate JSON string before parsing.
        
        Args:
            json_str: JSON string to validate
            max_size: Maximum allowed size in bytes
            
        Returns:
            True if valid
            
        Raises:
            JSONParseError: If validation fails
        """
        if not isinstance(json_str, str):
            raise JSONParseError(f"Expected string, got {type(json_str)}")
        
        # Check size
        max_size = max_size or JSONValidator.MAX_JSON_SIZE
        if len(json_str) > max_size:
            raise JSONParseError(
                f"JSON too large ({len(json_str)} bytes > {max_size} bytes)"
            )
        
        # Check for null bytes (corrupted data)
        if '\0' in json_str:
            raise JSONParseError("JSON contains null bytes (corrupted data)")
        
        # Basic structure check
        json_str = json_str.strip()
        if not json_str:
            raise JSONParseError("JSON string is empty")
        
        if not (json_str.startswith('{') or json_str.startswith('[')):
            raise JSONParseError("JSON must start with { or [")
        
        return True


def safe_json_loads(
    json_str: str,
    default: Any = None,
    max_size: Optional[int] = None,
    raise_on_error: bool = False
) -> Any:
    """
    Safely parse JSON string.
    
    Args:
        json_str: JSON string to parse
        default: Default value if parsing fails
        max_size: Maximum allowed size
        raise_on_error: Whether to raise exception on error
        
    Returns:
        Parsed JSON or default value
        
    Raises:
        JSONParseError: If raise_on_error=True and parsing fails
    """
    try:
        # Validate first
        JSONValidator.validate_json_string(json_str, max_size)
        
        # Parse
        return json.loads(json_str)
        
    except json.JSONDecodeError as e:
        error_msg = f"JSON parse error at line {e.lineno}, column {e.colno}: {e.msg}"
        logger.error(error_msg)
        
        if raise_on_error:
            raise JSONParseError(error_msg) from e
        
        return default
        
    except JSONParseError as e:
        logger.error(f"JSON validation error: {e}")
        
        if raise_on_error:
            raise
        
        return default
        
    except Exception as e:
        logger.error(f"Unexpected JSON parsing error: {e}", exc_info=True)
        
        if raise_on_error:
            raise JSONParseError(f"Unexpected error: {e}") from e
        
        return default


def safe_json_dumps(
    obj: Any,
    default: str = "{}",
    indent: Optional[int] = None,
    raise_on_error: bool = False
) -> str:
    """
    Safely serialize object to JSON.
    
    Args:
        obj: Object to serialize
        default: Default value if serialization fails
        indent: Indentation level
        raise_on_error: Whether to raise exception on error
        
    Returns:
        JSON string or default value
    """
    try:
        return json.dumps(obj, indent=indent, ensure_ascii=False)
        
    except (TypeError, ValueError) as e:
        logger.error(f"JSON serialization error: {e}")
        
        if raise_on_error:
            raise JSONParseError(f"Serialization failed: {e}") from e
        
        return default
        
    except Exception as e:
        logger.error(f"Unexpected JSON serialization error: {e}", exc_info=True)
        
        if raise_on_error:
            raise JSONParseError(f"Unexpected error: {e}") from e
        
        return default


def safe_json_load_file(
    file_path: str,
    default: Any = None,
    max_size: Optional[int] = None,
    raise_on_error: bool = False
) -> Any:
    """
    Safely load JSON from file.
    
    Args:
        file_path: Path to JSON file
        default: Default value if loading fails
        max_size: Maximum file size
        raise_on_error: Whether to raise exception on error
        
    Returns:
        Parsed JSON or default value
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            logger.warning(f"JSON file not found: {file_path}")
            if raise_on_error:
                raise JSONParseError(f"File not found: {file_path}")
            return default
        
        # Check file size
        file_size = path.stat().st_size
        max_size = max_size or JSONValidator.MAX_JSON_SIZE
        
        if file_size > max_size:
            error_msg = f"JSON file too large ({file_size} > {max_size} bytes)"
            logger.error(error_msg)
            if raise_on_error:
                raise JSONParseError(error_msg)
            return default
        
        # Read file
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse
        return safe_json_loads(content, default, max_size, raise_on_error)
        
    except JSONParseError:
        raise
        
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}", exc_info=True)
        
        if raise_on_error:
            raise JSONParseError(f"File load error: {e}") from e
        
        return default


def safe_json_save_file(
    file_path: str,
    obj: Any,
    indent: Optional[int] = 2,
    create_backup: bool = True,
    raise_on_error: bool = False
) -> bool:
    """
    Safely save JSON to file with atomic write.
    
    Args:
        file_path: Path to JSON file
        obj: Object to serialize
        indent: Indentation level
        create_backup: Whether to backup existing file
        raise_on_error: Whether to raise exception on error
        
    Returns:
        True if successful, False otherwise
    """
    try:
        path = Path(file_path)
        
        # Backup existing file
        if create_backup and path.exists():
            backup_path = path.with_suffix(f'.json.backup')
            import shutil
            shutil.copy(path, backup_path)
            logger.debug(f"Created backup: {backup_path}")
        
        # Serialize
        json_str = safe_json_dumps(obj, indent=indent, raise_on_error=True)
        
        # Atomic write (write to temp, then rename)
        temp_path = path.with_suffix('.json.tmp')
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
            f.flush()
            import os
            os.fsync(f.fileno())  # Ensure written to disk
        
        # Atomic rename
        temp_path.rename(path)
        
        logger.debug(f"JSON saved to: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving JSON to {file_path}: {e}", exc_info=True)
        
        if raise_on_error:
            raise JSONParseError(f"File save error: {e}") from e
        
        return False


def validate_json_schema(obj: Any, schema: Dict[str, Any]) -> bool:
    """
    Validate JSON object against schema.
    
    Args:
        obj: Object to validate
        schema: Schema definition
        
    Returns:
        True if valid
        
    Raises:
        JSONParseError: If validation fails
    """
    # Basic type validation
    if 'type' in schema:
        expected_type = schema['type']
        
        type_mapping = {
            'object': dict,
            'array': list,
            'string': str,
            'number': (int, float),
            'integer': int,
            'boolean': bool,
            'null': type(None)
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type and not isinstance(obj, expected_python_type):
            raise JSONParseError(
                f"Type mismatch: expected {expected_type}, got {type(obj).__name__}"
            )
    
    # Required fields
    if isinstance(obj, dict) and 'required' in schema:
        for field in schema['required']:
            if field not in obj:
                raise JSONParseError(f"Missing required field: {field}")
    
    # Properties validation (for objects)
    if isinstance(obj, dict) and 'properties' in schema:
        for key, value in obj.items():
            if key in schema['properties']:
                # Recursively validate
                validate_json_schema(value, schema['properties'][key])
    
    return True


# Convenience class
class SafeJSON:
    """Safe JSON operations namespace."""
    
    loads = staticmethod(safe_json_loads)
    dumps = staticmethod(safe_json_dumps)
    load_file = staticmethod(safe_json_load_file)
    save_file = staticmethod(safe_json_save_file)
    validate_schema = staticmethod(validate_json_schema)


if __name__ == "__main__":
    # Test safe JSON operations
    
    # Test 1: Parse valid JSON
    data = SafeJSON.loads('{"key": "value"}')
    print(f"Parsed: {data}")
    
    # Test 2: Parse invalid JSON (should not crash)
    data = SafeJSON.loads('invalid json', default={})
    print(f"Invalid JSON handled: {data}")
    
    # Test 3: Save to file
    SafeJSON.save_file('test.json', {'test': 'data'})
    print("File saved")
    
    # Test 4: Load from file
    data = SafeJSON.load_file('test.json', default={})
    print(f"File loaded: {data}")

