"""Tests for guardrails using OpenAI Agents SDK."""

from agents import Agent, GuardrailFunctionOutput

from concierge.guardrails import (
    input_validation_guardrail,
    output_validation_guardrail,
    party_size_guardrail,
)


class TestInputValidation:
    """Tests for input validation guardrails."""

    def test_valid_input(self):
        """Test that valid input passes validation."""
        agent = Agent(name="Test")
        context = {}
        user_input = "Book a table at Demo Restaurant for 4 people tomorrow at 7pm"

        result = input_validation_guardrail.guardrail_function(
            context, agent, user_input
        )

        assert isinstance(result, GuardrailFunctionOutput)
        assert result.tripwire_triggered is False

    def test_empty_input(self):
        """Test that empty input fails validation."""
        agent = Agent(name="Test")
        context = {}
        user_input = ""

        result = input_validation_guardrail.guardrail_function(
            context, agent, user_input
        )

        assert result.tripwire_triggered is True
        assert "empty" in result.output_info.lower()

    def test_too_long_input(self):
        """Test that excessively long input fails validation."""
        agent = Agent(name="Test")
        context = {}
        user_input = "x" * 1001  # Over the limit

        result = input_validation_guardrail.guardrail_function(
            context, agent, user_input
        )

        assert result.tripwire_triggered is True
        assert "too long" in result.output_info.lower()

    def test_suspicious_input(self):
        """Test that suspicious patterns fail validation."""
        agent = Agent(name="Test")
        context = {}
        suspicious_inputs = [
            "Book a table <script>alert('xss')</script>",
            "javascript:void(0)",
            "onclick=malicious()",
        ]

        for user_input in suspicious_inputs:
            result = input_validation_guardrail.guardrail_function(
                context, agent, user_input
            )
            assert result.tripwire_triggered is True, f"Should block: {user_input}"


class TestPartySizeValidation:
    """Tests for party size validation guardrail."""

    def test_valid_party_size(self):
        """Test that valid party sizes pass."""
        agent = Agent(name="Test")
        context = {}
        valid_inputs = [
            "Book for 1 person",
            "Reserve for 4 people",
            "Table for 20",
        ]

        for user_input in valid_inputs:
            result = party_size_guardrail.guardrail_function(context, agent, user_input)
            assert result.tripwire_triggered is False, f"Should pass: {user_input}"

    def test_invalid_party_size(self):
        """Test that invalid party sizes fail."""
        agent = Agent(name="Test")
        context = {}
        invalid_inputs = [
            "Book for 0 people",
            "Reserve for 100 people",
            "Table for 999",
        ]

        for user_input in invalid_inputs:
            result = party_size_guardrail.guardrail_function(context, agent, user_input)
            assert result.tripwire_triggered is True, f"Should fail: {user_input}"


class TestOutputValidation:
    """Tests for output validation guardrails."""

    def test_safe_output(self):
        """Test that safe output passes validation."""
        agent = Agent(name="Test")
        context = {}
        output = "Your reservation is confirmed for 4 people at 7pm."

        result = output_validation_guardrail.guardrail_function(context, agent, output)

        assert isinstance(result, GuardrailFunctionOutput)
        assert result.tripwire_triggered is False

    def test_output_with_api_key(self):
        """Test that output containing API keys fails validation."""
        agent = Agent(name="Test")
        context = {}
        output = "Here is your key: sk-" + "x" * 48

        result = output_validation_guardrail.guardrail_function(context, agent, output)

        assert result.tripwire_triggered is True
        assert "API key" in result.output_info or "token" in result.output_info
