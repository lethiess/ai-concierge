"""Output validation guardrails."""

import logging
import re
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class OutputValidator:
    """Validates agent outputs to prevent leaking sensitive information."""

    # Patterns that might indicate sensitive information
    SENSITIVE_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (r"\b[A-Z0-9]{20,}\b", "API key or token"),
        (r"sk-[a-zA-Z0-9]{48}", "OpenAI API key"),
        (r"password\s*[:=]\s*\S+", "Password"),
        (r"secret\s*[:=]\s*\S+", "Secret"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
        (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "Credit card"),
    ]

    @classmethod
    def validate_output(cls, output: str) -> tuple[bool, list[str]]:
        """Validate agent output for sensitive information.

        Args:
            output: The output text to validate

        Returns:
            Tuple of (is_safe, warnings)
            is_safe: True if output is safe, False if it contains sensitive data
            warnings: List of warning messages about what was detected
        """
        warnings = []

        for pattern, description in cls.SENSITIVE_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                logger.warning(f"Potential {description} detected in output")
                warnings.append(f"Output may contain {description}")

        is_safe = len(warnings) == 0
        return is_safe, warnings

    @classmethod
    def sanitize_output(cls, output: Any) -> Any:
        """Sanitize output by removing or masking sensitive information.

        Args:
            output: The output to sanitize (string or dict)

        Returns:
            Sanitized version of the output
        """
        if isinstance(output, str):
            # Mask potential API keys
            sanitized = re.sub(r"sk-[a-zA-Z0-9]{48}", "sk-***REDACTED***", output)
            # Mask long tokens
            return re.sub(r"\b[A-Z0-9]{20,}\b", "***REDACTED***", sanitized)

        if isinstance(output, dict):
            return {k: cls.sanitize_output(v) for k, v in output.items()}

        if isinstance(output, list):
            return [cls.sanitize_output(item) for item in output]

        return output
