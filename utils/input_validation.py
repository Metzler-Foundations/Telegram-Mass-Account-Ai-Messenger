#!/usr/bin/env python3
"""
Input Validation & Sanitization - Security hardening.

Features:
- SQL injection prevention
- XSS sanitization
- Phone number validation and normalization
- URL validation
- Path traversal prevention
- Template injection prevention
"""

import re
import html
import urllib.parse
from pathlib import Path
from typing import Optional, List, Any, Dict
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Validation error exception."""
    pass


class InputValidator:
    """Comprehensive input validation and sanitization."""
    
    # Regex patterns
    PHONE_NUMBER_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    API_KEY_PATTERN = re.compile(r'^[A-Za-z0-9\-_]{20,}$')
    COUNTRY_CODE_PATTERN = re.compile(r'^[A-Z]{2}$')
    
    # Dangerous SQL keywords (basic check - parameterized queries are primary defense)
    SQL_INJECTION_PATTERNS = [
        r"('|(\\')|(;)|(\-\-)|(\/\*)|(\*\/))",  # SQL metacharacters
        r"\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b",  # SQL keywords
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',  # Event handlers
        r'<iframe[^>]*>',
    ]
    
    @staticmethod
    def sanitize_sql_string(value: str) -> str:
        """
        Sanitize string for SQL (backup defense - use parameterized queries!).
        
        Args:
            value: Input string
            
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value)}")
        
        # Check for SQL injection patterns
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {value[:50]}")
                raise ValidationError("Input contains potentially dangerous SQL characters")
        
        # Escape single quotes (defense in depth)
        return value.replace("'", "''")
    
    @staticmethod
    def sanitize_html(value: str) -> str:
        """
        Sanitize string for HTML display (XSS prevention).
        
        Args:
            value: Input string
            
        Returns:
            HTML-escaped string
        """
        if not isinstance(value, str):
            return str(value)
        
        # Check for XSS patterns
        for pattern in InputValidator.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential XSS detected: {value[:50]}")
        
        # HTML escape
        return html.escape(value)
    
    @staticmethod
    def validate_phone_number(phone: str, normalize: bool = True) -> str:
        """
        Validate and normalize phone number.
        
        Args:
            phone: Phone number string
            normalize: Whether to normalize format
            
        Returns:
            Normalized phone number
            
        Raises:
            ValidationError: If phone number is invalid
        """
        if not isinstance(phone, str):
            raise ValidationError(f"Phone number must be string, got {type(phone)}")
        
        # Remove common separators
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Validate format
        if not InputValidator.PHONE_NUMBER_PATTERN.match(cleaned):
            raise ValidationError(f"Invalid phone number format: {phone}")
        
        # Normalize to E.164 format
        if normalize and not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        
        return cleaned
    
    @staticmethod
    def validate_username(username: str) -> str:
        """
        Validate Telegram username format.
        
        Args:
            username: Username string
            
        Returns:
            Validated username
            
        Raises:
            ValidationError: If username is invalid
        """
        if not isinstance(username, str):
            raise ValidationError(f"Username must be string, got {type(username)}")
        
        # Remove @ prefix if present
        if username.startswith('@'):
            username = username[1:]
        
        # Validate format
        if not InputValidator.USERNAME_PATTERN.match(username):
            raise ValidationError(
                f"Invalid username: {username}. "
                "Must be 5-32 characters, start with letter, contain only letters, digits, and underscores"
            )
        
        return username
    
    @staticmethod
    def validate_country_code(code: str) -> str:
        """
        Validate ISO 3166-1 alpha-2 country code.
        
        Args:
            code: Country code
            
        Returns:
            Validated country code (uppercase)
            
        Raises:
            ValidationError: If country code is invalid
        """
        if not isinstance(code, str):
            raise ValidationError(f"Country code must be string, got {type(code)}")
        
        code = code.upper()
        
        if not InputValidator.COUNTRY_CODE_PATTERN.match(code):
            raise ValidationError(f"Invalid country code: {code}. Must be 2-letter ISO code (e.g., US, GB)")
        
        return code
    
    @staticmethod
    def validate_api_key(api_key: str, min_length: int = 20) -> str:
        """
        Validate API key format.
        
        Args:
            api_key: API key string
            min_length: Minimum length requirement
            
        Returns:
            Validated API key
            
        Raises:
            ValidationError: If API key is invalid
        """
        if not isinstance(api_key, str):
            raise ValidationError(f"API key must be string, got {type(api_key)}")
        
        if len(api_key) < min_length:
            raise ValidationError(f"API key too short (minimum {min_length} characters)")
        
        if not InputValidator.API_KEY_PATTERN.match(api_key):
            raise ValidationError("API key contains invalid characters")
        
        return api_key
    
    @staticmethod
    def validate_url(url: str, allowed_schemes: List[str] = None) -> str:
        """
        Validate URL and check for SSRF risks.
        
        Args:
            url: URL string
            allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])
            
        Returns:
            Validated URL
            
        Raises:
            ValidationError: If URL is invalid or dangerous
        """
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        if not isinstance(url, str):
            raise ValidationError(f"URL must be string, got {type(url)}")
        
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception as e:
            raise ValidationError(f"Invalid URL: {e}")
        
        # Check scheme
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(f"URL scheme '{parsed.scheme}' not allowed. Allowed: {allowed_schemes}")
        
        # Check for internal/private IPs (SSRF prevention)
        if parsed.hostname:
            hostname = parsed.hostname.lower()
            
            # Block localhost
            if hostname in ['localhost', '127.0.0.1', '::1']:
                raise ValidationError("Cannot access localhost URLs")
            
            # Block private networks
            if any(hostname.startswith(prefix) for prefix in ['10.', '172.16.', '192.168.']):
                raise ValidationError("Cannot access private network URLs")
            
            # Block link-local
            if hostname.startswith('169.254.'):
                raise ValidationError("Cannot access link-local addresses")
            
            # Block metadata services
            if hostname == '169.254.169.254':
                raise ValidationError("Cannot access cloud metadata service")
        
        return url
    
    @staticmethod
    def validate_file_path(path: str, base_dir: Optional[str] = None) -> Path:
        """
        Validate file path and prevent directory traversal.
        
        Args:
            path: File path string
            base_dir: Base directory to restrict to
            
        Returns:
            Validated Path object
            
        Raises:
            ValidationError: If path is invalid or dangerous
        """
        if not isinstance(path, str):
            raise ValidationError(f"Path must be string, got {type(path)}")
        
        # Convert to Path
        try:
            file_path = Path(path).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid file path: {e}")
        
        # Check for directory traversal
        if '..' in path or path.startswith('/'):
            logger.warning(f"Potential directory traversal attempt: {path}")
        
        # If base directory specified, ensure path is within it
        if base_dir:
            base_path = Path(base_dir).resolve()
            try:
                file_path.relative_to(base_path)
            except ValueError:
                raise ValidationError(f"Path {path} is outside allowed directory {base_dir}")
        
        return file_path
    
    @staticmethod
    def validate_template_string(template: str) -> str:
        """
        Validate template string and check for code injection.
        
        Args:
            template: Template string
            
        Returns:
            Validated template string
            
        Raises:
            ValidationError: If template contains dangerous code
        """
        if not isinstance(template, str):
            raise ValidationError(f"Template must be string, got {type(template)}")
        
        # Check for dangerous Python code patterns
        dangerous_patterns = [
            r'__import__',
            r'eval\s*\(',
            r'exec\s*\(',
            r'compile\s*\(',
            r'open\s*\(',
            r'__.*__',  # Dunder methods
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, template, re.IGNORECASE):
                raise ValidationError(f"Template contains potentially dangerous code: {pattern}")
        
        return template
    
    @staticmethod
    def validate_message_length(message: str, max_length: int = 4096) -> str:
        """
        Validate message length for Telegram.
        
        Args:
            message: Message text
            max_length: Maximum allowed length (Telegram limit is 4096)
            
        Returns:
            Validated message
            
        Raises:
            ValidationError: If message is too long
        """
        if not isinstance(message, str):
            raise ValidationError(f"Message must be string, got {type(message)}")
        
        if len(message) > max_length:
            raise ValidationError(f"Message too long ({len(message)} > {max_length} characters)")
        
        return message
    
    @staticmethod
    def sanitize_dict(data: Dict[str, Any], allowed_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Sanitize dictionary input.
        
        Args:
            data: Input dictionary
            allowed_keys: List of allowed keys (None = allow all)
            
        Returns:
            Sanitized dictionary
        """
        if not isinstance(data, dict):
            raise ValidationError(f"Expected dict, got {type(data)}")
        
        sanitized = {}
        for key, value in data.items():
            # Check allowed keys
            if allowed_keys and key not in allowed_keys:
                logger.warning(f"Ignoring unexpected key: {key}")
                continue
            
            # Sanitize string values
            if isinstance(value, str):
                sanitized[key] = InputValidator.sanitize_html(value)
            else:
                sanitized[key] = value
        
        return sanitized


class SQLQueryBuilder:
    """Safe SQL query builder with parameterization."""
    
    @staticmethod
    def build_select(table: str, columns: List[str], where: Optional[Dict[str, Any]] = None) -> tuple:
        """
        Build parameterized SELECT query.
        
        Args:
            table: Table name
            columns: List of column names
            where: WHERE clause conditions
            
        Returns:
            Tuple of (query, params)
        """
        # Validate table name (must be alphanumeric + underscore)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            raise ValidationError(f"Invalid table name: {table}")
        
        # Validate column names
        for col in columns:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col):
                raise ValidationError(f"Invalid column name: {col}")
        
        query = f"SELECT {', '.join(columns)} FROM {table}"
        params = []
        
        if where:
            conditions = []
            for key, value in where.items():
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                    raise ValidationError(f"Invalid column name in WHERE: {key}")
                conditions.append(f"{key} = ?")
                params.append(value)
            
            query += " WHERE " + " AND ".join(conditions)
        
        return query, params
    
    @staticmethod
    def build_insert(table: str, data: Dict[str, Any]) -> tuple:
        """
        Build parameterized INSERT query.
        
        Args:
            table: Table name
            data: Dictionary of column: value
            
        Returns:
            Tuple of (query, params)
        """
        # Validate table name
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            raise ValidationError(f"Invalid table name: {table}")
        
        columns = []
        params = []
        
        for key, value in data.items():
            # Validate column name
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                raise ValidationError(f"Invalid column name: {key}")
            columns.append(key)
            params.append(value)
        
        placeholders = ', '.join(['?' for _ in columns])
        query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        
        return query, params
    
    @staticmethod
    def build_update(table: str, data: Dict[str, Any], where: Dict[str, Any]) -> tuple:
        """
        Build parameterized UPDATE query.
        
        Args:
            table: Table name
            data: Dictionary of column: value to update
            where: WHERE clause conditions
            
        Returns:
            Tuple of (query, params)
        """
        # Validate table name
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            raise ValidationError(f"Invalid table name: {table}")
        
        set_clauses = []
        params = []
        
        for key, value in data.items():
            # Validate column name
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                raise ValidationError(f"Invalid column name: {key}")
            set_clauses.append(f"{key} = ?")
            params.append(value)
        
        query = f"UPDATE {table} SET {', '.join(set_clauses)}"
        
        if where:
            conditions = []
            for key, value in where.items():
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                    raise ValidationError(f"Invalid column name in WHERE: {key}")
                conditions.append(f"{key} = ?")
                params.append(value)
            
            query += " WHERE " + " AND ".join(conditions)
        
        return query, params


# Convenience functions
def sanitize_html(text: str) -> str:
    """Sanitize HTML/XSS."""
    return InputValidator.sanitize_html(text)


def validate_phone(phone: str) -> str:
    """Validate and normalize phone number."""
    return InputValidator.validate_phone_number(phone)


def validate_url(url: str) -> str:
    """Validate URL."""
    return InputValidator.validate_url(url)


def safe_sql_query(table: str, columns: List[str], where: Optional[Dict[str, Any]] = None) -> tuple:
    """Build safe parameterized SELECT query."""
    return SQLQueryBuilder.build_select(table, columns, where)



