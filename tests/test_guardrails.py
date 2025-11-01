"""Tests for guardrail modules."""

from concierge.guardrails.input_validator import InputValidator
from concierge.guardrails.output_validator import OutputValidator


class TestInputValidator:
    """Tests for the InputValidator."""

    def test_validate_empty_input(self):
        """Test validation of empty input."""
        is_valid, error = InputValidator.validate_user_input("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_too_long_input(self):
        """Test validation of excessively long input."""
        long_input = "x" * 2000
        is_valid, error = InputValidator.validate_user_input(long_input)
        assert is_valid is False
        assert "too long" in error.lower()

    def test_validate_suspicious_patterns(self):
        """Test detection of suspicious patterns."""
        suspicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:void(0)",
            "onclick='malicious()'",
        ]

        for user_input in suspicious_inputs:
            is_valid, error = InputValidator.validate_user_input(user_input)
            assert is_valid is False
            assert "suspicious" in error.lower()

    def test_validate_normal_input(self):
        """Test validation of normal input."""
        is_valid, error = InputValidator.validate_user_input(
            "Book a table for 4 people at 7pm"
        )
        assert is_valid is True
        assert error is None

    def test_validate_party_size_valid(self):
        """Test validation of valid party sizes."""
        for size in [1, 5, 10, 20, 50]:
            is_valid, error = InputValidator.validate_party_size(size)
            assert is_valid is True
            assert error is None

    def test_validate_party_size_invalid(self):
        """Test validation of invalid party sizes."""
        # Too small
        is_valid, _error = InputValidator.validate_party_size(0)
        assert is_valid is False

        # Too large
        is_valid, _error = InputValidator.validate_party_size(100)
        assert is_valid is False

    def test_validate_phone_number_valid(self):
        """Test validation of valid phone numbers."""
        valid_numbers = [
            "+1234567890",
            "+441234567890",
            "1234567890",
            "(123) 456-7890",
            "123-456-7890",
        ]

        for number in valid_numbers:
            is_valid, error = InputValidator.validate_phone_number(number)
            assert is_valid is True, f"Failed for {number}: {error}"

    def test_validate_phone_number_invalid(self):
        """Test validation of invalid phone numbers."""
        invalid_numbers = [
            "123",  # Too short
            "+123abc456",  # Contains letters
            "",  # Empty
        ]

        for number in invalid_numbers:
            is_valid, _error = InputValidator.validate_phone_number(number)
            assert is_valid is False, f"Should have failed for {number}"


class TestOutputValidator:
    """Tests for the OutputValidator."""

    def test_validate_safe_output(self):
        """Test validation of safe output."""
        safe_text = "Your reservation is confirmed for 4 people at 7pm"
        is_safe, warnings = OutputValidator.validate_output(safe_text)
        assert is_safe is True
        assert len(warnings) == 0

    def test_detect_api_key(self):
        """Test detection of API keys."""
        unsafe_text = "Here is your key: sk-" + "x" * 48
        is_safe, warnings = OutputValidator.validate_output(unsafe_text)
        assert is_safe is False
        assert len(warnings) > 0

    def test_detect_long_token(self):
        """Test detection of long tokens."""
        unsafe_text = "Token: " + "A" * 25
        is_safe, warnings = OutputValidator.validate_output(unsafe_text)
        assert is_safe is False
        assert len(warnings) > 0

    def test_sanitize_api_key(self):
        """Test sanitization of API keys."""
        text = "Key: sk-" + "x" * 48
        sanitized = OutputValidator.sanitize_output(text)
        assert "sk-***REDACTED***" in sanitized
        assert "sk-x" not in sanitized

    def test_sanitize_dict(self):
        """Test sanitization of dictionary outputs."""
        data = {
            "message": "Success",
            "api_key": "sk-" + "x" * 48,
        }
        sanitized = OutputValidator.sanitize_output(data)
        assert "sk-***REDACTED***" in sanitized["api_key"]
