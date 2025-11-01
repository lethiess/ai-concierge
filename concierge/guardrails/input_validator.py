"""Input validation guardrails."""

import logging
import re
from typing import ClassVar

logger = logging.getLogger(__name__)


class InputValidator:
    """Validates user input for security and abuse prevention."""

    # Patterns that indicate potential abuse or inappropriate content
    BLOCKED_PATTERNS: ClassVar[list[str]] = [
        r"<script",
        r"javascript:",
        r"onclick",
        r"onerror",
        r"eval\(",
        r"exec\(",
    ]

    # Extremely long inputs may indicate abuse
    MAX_INPUT_LENGTH: ClassVar[int] = 1000

    # Minimum and maximum party sizes that make sense
    MIN_PARTY_SIZE: ClassVar[int] = 1
    MAX_PARTY_SIZE: ClassVar[int] = 50

    @classmethod
    def validate_user_input(cls, user_input: str) -> tuple[bool, str | None]:
        """Validate raw user input from CLI.

        Args:
            user_input: Raw user input string

        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message is None
            If invalid, error_message contains the reason
        """
        if not user_input or not user_input.strip():
            return False, "Input cannot be empty"

        if len(user_input) > cls.MAX_INPUT_LENGTH:
            logger.warning(f"Input too long: {len(user_input)} characters")
            return False, f"Input too long (max {cls.MAX_INPUT_LENGTH} characters)"

        # Check for suspicious patterns
        user_input_lower = user_input.lower()
        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, user_input_lower):
                logger.warning(f"Blocked pattern detected: {pattern}")
                return False, "Input contains suspicious content"

        return True, None

    @classmethod
    def validate_party_size(cls, party_size: int) -> tuple[bool, str | None]:
        """Validate party size is reasonable.

        Args:
            party_size: Number of people for reservation

        Returns:
            Tuple of (is_valid, error_message)
        """
        if party_size < cls.MIN_PARTY_SIZE:
            return False, f"Party size must be at least {cls.MIN_PARTY_SIZE}"

        if party_size > cls.MAX_PARTY_SIZE:
            return False, f"Party size cannot exceed {cls.MAX_PARTY_SIZE}"

        return True, None

    @classmethod
    def validate_phone_number(cls, phone: str) -> tuple[bool, str | None]:
        """Validate phone number format.

        Args:
            phone: Phone number string

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic phone number validation - accepts various formats
        # Remove common separators
        cleaned = re.sub(r"[\s\-\(\)\.]", "", phone)

        # Check if it's a valid international format (starts with +)
        if cleaned.startswith("+"):
            if len(cleaned) < 10 or len(cleaned) > 15:
                return False, "Invalid phone number format"
            if not cleaned[1:].isdigit():
                return False, "Phone number must contain only digits after +"
        else:
            # Domestic format
            if len(cleaned) < 10 or len(cleaned) > 11:
                return False, "Invalid phone number format"
            if not cleaned.isdigit():
                return False, "Phone number must contain only digits"

        return True, None
