#!/usr/bin/env python3
"""Unit tests for validation modules."""

import pytest
from utils.input_validation import InputValidator, ValidationError, SQLQueryBuilder
from utils.message_validator import MessageValidator
from accounts.phone_normalizer import PhoneNormalizer
from accounts.username_validator import UsernameValidator


class TestInputValidation:
    """Test input validation."""
    
    def test_phone_validation_valid(self):
        result = InputValidator.validate_phone_number("+1234567890")
        assert result == "+1234567890"
    
    def test_phone_validation_invalid(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_phone_number("invalid")
    
    def test_username_validation(self):
        result = InputValidator.validate_username("valid_username")
        assert result == "valid_username"
    
    def test_url_validation_safe(self):
        result = InputValidator.validate_url("https://example.com")
        assert result == "https://example.com"
    
    def test_url_validation_ssrf(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_url("http://localhost")
    
    def test_sql_query_builder(self):
        query, params = SQLQueryBuilder.build_select(
            'accounts',
            ['phone_number', 'username'],
            where={'status': 'active'}
        )
        assert 'SELECT' in query
        assert '?' in query
        assert params == ['active']


class TestMessageValidation:
    """Test message validation."""
    
    def test_message_length_valid(self):
        valid, msg = MessageValidator.validate_length("Short message")
        assert valid is True
    
    def test_message_length_invalid(self):
        long_msg = "x" * 5000
        valid, msg = MessageValidator.validate_length(long_msg)
        assert valid is False
    
    def test_emoji_validation(self):
        valid, msg = MessageValidator.validate_emoji("Hello 👋")
        assert valid is True


class TestPhoneNormalization:
    """Test phone normalization."""
    
    def test_normalize_with_plus(self):
        result = PhoneNormalizer.normalize("+1234567890")
        assert result.startswith('+')
    
    def test_normalize_without_plus(self):
        result = PhoneNormalizer.normalize("1234567890")
        assert result.startswith('+')
    
    def test_duplicate_detection(self):
        existing = ["+1234567890"]
        assert PhoneNormalizer.is_duplicate("+1234567890", existing) is True
        assert PhoneNormalizer.is_duplicate("+9876543210", existing) is False


class TestUsernameValidation:
    """Test username validation."""
    
    def test_valid_username(self):
        valid, result = UsernameValidator.validate("valid_user123")
        assert valid is True
    
    def test_invalid_username_too_short(self):
        valid, result = UsernameValidator.validate("abc")
        assert valid is False
    
    def test_reserved_username(self):
        valid, result = UsernameValidator.validate("telegram")
        assert valid is False





