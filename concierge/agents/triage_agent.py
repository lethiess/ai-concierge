"""Triage/Orchestrator agent for managing reservation workflows."""

import json
import logging
from typing import Any

from openai import OpenAI

from concierge.config import get_config
from concierge.guardrails.input_validator import InputValidator
from concierge.guardrails.output_validator import OutputValidator
from concierge.models import ReservationRequest, ReservationResult, ReservationStatus
from concierge.services.restaurant_service import RestaurantService

logger = logging.getLogger(__name__)


class TriageAgent:
    """Orchestrator agent that manages the reservation workflow.

    This agent:
    1. Validates user input
    2. Parses reservation requests from natural language
    3. Looks up restaurant information
    4. Hands off to the voice agent for booking
    5. Returns results to the user
    """

    def __init__(
        self,
        restaurant_service: RestaurantService | None = None,
        openai_client: OpenAI | None = None,
    ) -> None:
        """Initialize the triage agent.

        Args:
            restaurant_service: Restaurant lookup service
            openai_client: OpenAI client for LLM calls
        """
        self.config = get_config()
        self.restaurant_service = restaurant_service or RestaurantService()
        self.openai_client = openai_client or OpenAI(api_key=self.config.openai_api_key)
        self.input_validator = InputValidator()
        self.output_validator = OutputValidator()

        logger.info("Triage agent initialized")

    def process_user_request(self, user_input: str) -> dict[str, Any]:
        """Process a user's reservation request.

        Args:
            user_input: Natural language reservation request

        Returns:
            Dictionary with processing result and any errors
        """
        logger.info(f"Processing user request: {user_input}")

        # Step 1: Validate input
        is_valid, error = self.input_validator.validate_user_input(user_input)
        if not is_valid:
            logger.warning(f"Input validation failed: {error}")
            return {
                "success": False,
                "error": error,
                "stage": "validation",
            }

        # Step 2: Parse the request using LLM
        try:
            parsed_request = self._parse_request(user_input)
            if not parsed_request:
                return {
                    "success": False,
                    "error": "Could not understand the reservation request",
                    "stage": "parsing",
                }

            logger.info(f"Parsed request: {parsed_request}")

            # Validate parsed data
            if parsed_request.get("party_size"):
                is_valid, error = self.input_validator.validate_party_size(
                    parsed_request["party_size"]
                )
                if not is_valid:
                    return {
                        "success": False,
                        "error": error,
                        "stage": "validation",
                    }

        except Exception as e:
            logger.exception("Error parsing request")
            return {
                "success": False,
                "error": f"Error processing request: {e!s}",
                "stage": "parsing",
            }

        # Step 3: Look up restaurant
        try:
            restaurant = self.restaurant_service.find_restaurant(
                parsed_request["restaurant_name"]
            )
            if not restaurant:
                return {
                    "success": False,
                    "error": f"Restaurant '{parsed_request['restaurant_name']}' not found",
                    "stage": "lookup",
                }

            logger.info(f"Found restaurant: {restaurant.name}")

        except Exception as e:
            logger.exception("Error looking up restaurant")
            return {
                "success": False,
                "error": f"Error finding restaurant: {e!s}",
                "stage": "lookup",
            }

        # Step 4: Create reservation request object
        try:
            reservation_request = ReservationRequest(**parsed_request)
        except Exception as e:
            logger.exception("Error creating reservation request")
            return {
                "success": False,
                "error": f"Invalid reservation details: {e!s}",
                "stage": "validation",
            }

        # Return ready for handoff to voice agent
        return {
            "success": True,
            "request": reservation_request,
            "restaurant": restaurant,
            "stage": "ready",
        }

    def _parse_request(self, user_input: str) -> dict[str, Any] | None:
        """Parse natural language reservation request using LLM.

        Args:
            user_input: Natural language input

        Returns:
            Dictionary with parsed reservation details, or None if parsing fails
        """
        system_prompt = """You are a helpful assistant that extracts reservation details from natural language.

Extract the following information:
- restaurant_name: Name of the restaurant
- party_size: Number of people (must be a positive integer)
- date: Reservation date (format as provided, or use relative terms like 'today', 'tomorrow')
- time: Reservation time (format as provided, e.g., '7:00 PM', '19:00')
- user_name: Customer name (if mentioned)
- user_phone: Customer phone number (if mentioned)
- special_requests: Any special requests or notes

Return ONLY a JSON object with these fields. If a field is not mentioned, omit it or use null.
Do not include any explanation, just the JSON.

Example input: "Book a table at Pizzeria Mario for 4 people tomorrow at 7pm under the name John"
Example output: {"restaurant_name": "Pizzeria Mario", "party_size": 4, "date": "tomorrow", "time": "7pm", "user_name": "John"}
"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.agent_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                return None

            parsed = json.loads(content)

            # Validate required fields
            if not parsed.get("restaurant_name"):
                logger.warning("Missing restaurant_name in parsed request")
                return None

            if not parsed.get("party_size"):
                logger.warning("Missing party_size in parsed request")
                return None

            if not parsed.get("date"):
                logger.warning("Missing date in parsed request")
                return None

            if not parsed.get("time"):
                logger.warning("Missing time in parsed request")
                return None

        except json.JSONDecodeError:
            logger.exception("Failed to parse LLM response as JSON")
            return None
        except Exception:
            logger.exception("Error calling LLM for parsing")
            return None
        else:
            return parsed

    def format_result(self, result: ReservationResult) -> str:
        """Format a reservation result for display to the user.

        Args:
            result: The reservation result

        Returns:
            Formatted string for display
        """
        output = []

        output.append("=" * 60)
        output.append("RESERVATION RESULT")
        output.append("=" * 60)

        # Status
        status_emoji = {
            ReservationStatus.CONFIRMED: "✓",
            ReservationStatus.PENDING: "⏳",
            ReservationStatus.REJECTED: "✗",
            ReservationStatus.ERROR: "⚠",
        }
        emoji = status_emoji.get(result.status, "•")
        output.append(f"\nStatus: {emoji} {result.status.value.upper()}")

        # Restaurant
        output.append(f"\nRestaurant: {result.restaurant.name}")
        output.append(f"Phone: {result.restaurant.phone_number}")

        # Reservation details
        output.append(f"\nDate: {result.request.date}")
        output.append(f"Time: {result.request.time}")
        output.append(f"Party size: {result.request.party_size} people")

        if result.request.user_name:
            output.append(f"Name: {result.request.user_name}")

        # Confirmation
        if result.confirmation_number:
            output.append(f"\nConfirmation #: {result.confirmation_number}")

        # Message
        output.append(f"\n{result.message}")

        # Call details
        if result.call_duration:
            output.append(f"\nCall duration: {result.call_duration:.1f} seconds")

        output.append("\n" + "=" * 60)

        formatted = "\n".join(output)

        # Validate output
        is_safe, warnings = self.output_validator.validate_output(formatted)
        if not is_safe:
            logger.warning(f"Output validation warnings: {warnings}")

        return formatted
