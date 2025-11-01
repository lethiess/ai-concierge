"""Output validation guardrails using OpenAI Agents SDK."""

import logging
import re

from agents import GuardrailFunctionOutput, OutputGuardrail

logger = logging.getLogger(__name__)


def output_validation_function(
    _context, _agent, output: str
) -> GuardrailFunctionOutput:
    """Validate agent output for sensitive information.

    Args:
        context: The guardrail context
        agent: The agent being run
        output: The output to validate

    Returns:
        GuardrailFunctionOutput indicating if validation passed
    """
    # Patterns that might indicate sensitive information
    sensitive_patterns = [
        (r"\b[A-Z0-9]{20,}\b", "API key or token"),
        (r"sk-[a-zA-Z0-9]{48}", "OpenAI API key"),
        (r"password\s*[:=]\s*\S+", "Password"),
        (r"secret\s*[:=]\s*\S+", "Secret"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
        (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "Credit card"),
    ]

    warnings = []

    for pattern, description in sensitive_patterns:
        if re.search(pattern, str(output), re.IGNORECASE):
            logger.warning(f"Potential {description} detected in output")
            warnings.append(f"Output may contain {description}")

    if warnings:
        return GuardrailFunctionOutput(
            output_info=f"Security warning: {'; '.join(warnings)}. Output blocked.",
            tripwire_triggered=True,
        )

    return GuardrailFunctionOutput(
        output_info="Output validation passed",
        tripwire_triggered=False,
    )


def sanitize_output_function(_context, _agent, output: str) -> GuardrailFunctionOutput:
    """Sanitize output by masking potential sensitive information.

    Args:
        context: The guardrail context
        agent: The agent being run
        output: The output to sanitize

    Returns:
        GuardrailFunctionOutput with sanitized output
    """
    if isinstance(output, str):
        # Mask potential API keys
        sanitized = re.sub(r"sk-[a-zA-Z0-9]{48}", "sk-***REDACTED***", output)
        # Mask long tokens
        sanitized = re.sub(r"\b[A-Z0-9]{20,}\b", "***REDACTED***", sanitized)

        return GuardrailFunctionOutput(
            output_info="Output sanitized",
            tripwire_triggered=False,
            modified_output=sanitized,
        )

    return GuardrailFunctionOutput(
        output_info="No sanitization needed",
        tripwire_triggered=False,
    )


# Create the guardrail instances
output_validation_guardrail = OutputGuardrail(
    guardrail_function=output_validation_function
)

output_sanitization_guardrail = OutputGuardrail(
    guardrail_function=sanitize_output_function
)
