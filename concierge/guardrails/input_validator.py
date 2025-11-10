"""Input validation guardrails using OpenAI Agents SDK."""

import logging
import re

from agents import GuardrailFunctionOutput, input_guardrail

logger = logging.getLogger(__name__)


@input_guardrail(name="input_validation_guardrail")
def input_validation_guardrail(_context, _agent, user_input) -> GuardrailFunctionOutput:
    """Validate user input for security and abuse prevention.

    Args:
        context: The guardrail context
        agent: The agent being run
        user_input: User input (can be string or list of messages)

    Returns:
        GuardrailFunctionOutput indicating if validation passed
    """
    # Extract string content from input (SDK may pass list of messages)
    if isinstance(user_input, list):
        # Extract text from message list
        text_parts = []
        for msg in user_input:
            if isinstance(msg, dict) and "content" in msg:
                text_parts.append(str(msg["content"]))
            elif hasattr(msg, "content"):
                text_parts.append(str(msg.content))
        input_text = " ".join(text_parts)
    else:
        input_text = str(user_input)

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
    if not input_text or not input_text.strip():
        logger.warning("Guardrail triggered: Empty input detected")
        return GuardrailFunctionOutput(
            output_info="Input cannot be empty. Please provide a reservation request.",
            tripwire_triggered=True,
        )

    # Check input length
    if len(input_text) > max_input_length:
        logger.warning(
            f"Guardrail triggered: Input too long ({len(input_text)} > {max_input_length} chars)"
        )
        return GuardrailFunctionOutput(
            output_info=f"Input too long (max {max_input_length} characters). Please shorten your request.",
            tripwire_triggered=True,
        )

    # Check for suspicious patterns
    input_text_lower = input_text.lower()
    for pattern in blocked_patterns:
        if re.search(pattern, input_text_lower):
            logger.warning(
                f"Guardrail triggered: Suspicious pattern detected ({pattern})"
            )
            return GuardrailFunctionOutput(
                output_info="Input contains suspicious content. Please rephrase your request.",
                tripwire_triggered=True,
            )

    # Input is valid
    return GuardrailFunctionOutput(
        output_info="Input validation passed",
        tripwire_triggered=False,
    )


@input_guardrail(name="party_size_guardrail")
def party_size_guardrail(_context, _agent, user_input) -> GuardrailFunctionOutput:
    """Validate party size constraints.

    Args:
        context: The guardrail context
        agent: The agent being run
        user_input: User input (can be string or list of messages)

    Returns:
        GuardrailFunctionOutput indicating if validation passed
    """
    # Extract string content from input (SDK may pass list of messages)
    if isinstance(user_input, list):
        # Extract text from message list
        text_parts = []
        for msg in user_input:
            if isinstance(msg, dict) and "content" in msg:
                text_parts.append(str(msg["content"]))
            elif hasattr(msg, "content"):
                text_parts.append(str(msg.content))
        input_text = " ".join(text_parts)
    else:
        input_text = str(user_input)

    # This is a simple check - the actual party size will be extracted by the agent
    # We just check for obviously invalid values mentioned in the text

    # Look for numbers in the input
    numbers = re.findall(r"\b\d+\b", input_text)

    min_party_size = 1
    max_party_size = 12

    for num_str in numbers:
        num = int(num_str)
        # If we find a number that looks like a party size but is invalid
        if num < min_party_size or num > max_party_size:
            logger.warning(
                f"Guardrail triggered: Invalid party size ({num} people, allowed: {min_party_size}-{max_party_size})"
            )
            return GuardrailFunctionOutput(
                output_info=f"Party size must be between {min_party_size} and {max_party_size} people.",
                tripwire_triggered=True,
            )

    return GuardrailFunctionOutput(
        output_info="Party size validation passed",
        tripwire_triggered=False,
    )
