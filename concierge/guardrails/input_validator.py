"""Input validation guardrails using OpenAI Agents SDK."""

import logging
import re

from agents import GuardrailFunctionOutput, InputGuardrail

logger = logging.getLogger(__name__)


def input_validation_function(
    _context, _agent, user_input: str
) -> GuardrailFunctionOutput:
    """Validate user input for security and abuse prevention.

    Args:
        context: The guardrail context
        agent: The agent being run
        user_input: Raw user input string

    Returns:
        GuardrailFunctionOutput indicating if validation passed
    """
    # Patterns that indicate potential abuse or inappropriate content
    blocked_patterns = [
        r"<script",
        r"javascript:",
        r"onclick",
        r"onerror",
        r"eval\(",
        r"exec\(",
    ]

    # Extremely long inputs may indicate abuse
    max_input_length = 1000

    # Check for empty input
    if not user_input or not user_input.strip():
        logger.warning("Empty input detected")
        return GuardrailFunctionOutput(
            output_info="Input cannot be empty. Please provide a reservation request.",
            tripwire_triggered=True,
        )

    # Check input length
    if len(user_input) > max_input_length:
        logger.warning(f"Input too long: {len(user_input)} characters")
        return GuardrailFunctionOutput(
            output_info=f"Input too long (max {max_input_length} characters). Please shorten your request.",
            tripwire_triggered=True,
        )

    # Check for suspicious patterns
    user_input_lower = user_input.lower()
    for pattern in blocked_patterns:
        if re.search(pattern, user_input_lower):
            logger.warning(f"Blocked pattern detected: {pattern}")
            return GuardrailFunctionOutput(
                output_info="Input contains suspicious content. Please rephrase your request.",
                tripwire_triggered=True,
            )

    # Input is valid
    return GuardrailFunctionOutput(
        output_info="Input validation passed",
        tripwire_triggered=False,
    )


def party_size_validation_function(
    _context, _agent, user_input: str
) -> GuardrailFunctionOutput:
    """Validate party size constraints.

    Args:
        context: The guardrail context
        agent: The agent being run
        user_input: User input string

    Returns:
        GuardrailFunctionOutput indicating if validation passed
    """
    # This is a simple check - the actual party size will be extracted by the agent
    # We just check for obviously invalid values mentioned in the text

    # Look for numbers in the input
    numbers = re.findall(r"\b\d+\b", user_input)

    min_party_size = 1
    max_party_size = 50

    for num_str in numbers:
        num = int(num_str)
        # If we find a number that looks like a party size but is invalid
        if num < min_party_size or num > max_party_size:
            logger.warning(f"Potentially invalid party size detected: {num}")
            return GuardrailFunctionOutput(
                output_info=f"Party size must be between {min_party_size} and {max_party_size} people.",
                tripwire_triggered=True,
            )

    return GuardrailFunctionOutput(
        output_info="Party size validation passed",
        tripwire_triggered=False,
    )


# Create the guardrail instances
input_validation_guardrail = InputGuardrail(
    guardrail_function=input_validation_function
)

party_size_guardrail = InputGuardrail(guardrail_function=party_size_validation_function)
