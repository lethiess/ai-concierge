"""Orchestrator agent that routes requests to specialized agents using OpenAI Agents SDK."""

import json
import logging
from typing import TYPE_CHECKING

from agents import Agent

from concierge.config import get_config
from concierge.prompts import load_prompt
from concierge.services.call_manager import get_call_manager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Orchestrator agent that routes requests to specialized agents.

    This is the main entry point for all user requests. It analyzes the intent
    and routes to the appropriate specialized agent.

    Attributes:
        specialized_agents: List of specialized agents to route to
        config: Application configuration
        _agent: The underlying Agent instance (created lazily)
    """

    def __init__(
        self,
        reservation_agent: Agent,
        cancellation_agent: Agent,
        search_agent: Agent,
        input_guardrails: list | None = None,
        output_guardrails: list | None = None,
    ) -> None:
        """Initialize the orchestrator agent.

        Args:
            reservation_agent: Agent for handling reservation requests (required)
            cancellation_agent: Agent for handling cancellations (required)
            search_agent: Agent for restaurant search (required)
            input_guardrails: List of input guardrails to apply (optional)
            output_guardrails: List of output guardrails to apply (optional)
        """
        # Build list of specialized agents
        self.specialized_agents: list[Agent] = [
            reservation_agent,
            cancellation_agent,
            search_agent,
        ]

        self.config = get_config()
        self.input_guardrails = input_guardrails or []
        self.output_guardrails = output_guardrails or []
        self._agent: Agent | None = None

        logger.info(
            "OrchestratorAgent initialized with %d specialized agents",
            len(self.specialized_agents),
        )

    def create(self) -> Agent:
        """Create and return the configured orchestrator agent.

        Returns:
            Configured orchestrator agent

        Note:
            The agent is created lazily on first call and cached.
        """
        if self._agent is None:
            # Load instructions from template
            instructions = load_prompt("orchestrator_agent")

            self._agent = Agent(
                name="AI Concierge Orchestrator",
                model=self.config.agent_model,
                instructions=instructions,
                handoffs=self.specialized_agents,
                input_guardrails=self.input_guardrails,
                output_guardrails=self.output_guardrails,
            )
            logger.info("Orchestrator agent created successfully")
            logger.info(
                f"  with {len(self.input_guardrails)} input guardrails and {len(self.output_guardrails)} output guardrails"
            )

        return self._agent

    @property
    def agent(self) -> Agent:
        """Get the agent instance (creates it if needed).

        Returns:
            The orchestrator agent
        """
        return self.create()


def format_reservation_result(result) -> str:
    """Format a reservation result for display to the user.

    Args:
        result: The reservation result from the agent run

    Returns:
        Formatted string for display
    """
    output = []

    output.append("=" * 60)
    output.append("RESERVATION RESULT")
    output.append("=" * 60)

    # Extract structured call information from tool calls
    call_result = None
    call_id = None

    # Try method 1: Extract from result.messages (if available)
    if hasattr(result, "messages"):
        for msg in result.messages:
            # Check for tool results
            if (
                hasattr(msg, "role")
                and msg.role == "tool"
                and hasattr(msg, "content")
                and msg.content
            ):
                try:
                    call_result = (
                        json.loads(msg.content)
                        if isinstance(msg.content, str)
                        else msg.content
                    )
                    if isinstance(call_result, dict) and "call_id" in call_result:
                        call_id = call_result["call_id"]
                        break
                except (json.JSONDecodeError, AttributeError):
                    pass
    elif hasattr(result, "raw_responses"):
        # Try extracting from raw_responses if messages not available
        for response in result.raw_responses:
            if hasattr(response, "choices") and response.choices:
                for choice in response.choices:
                    if hasattr(choice, "message") and hasattr(
                        choice.message, "tool_calls"
                    ):
                        for tool_call in choice.message.tool_calls:
                            if hasattr(tool_call, "function") and hasattr(
                                tool_call.function, "arguments"
                            ):
                                try:
                                    args = json.loads(tool_call.function.arguments)
                                    if isinstance(args, dict) and "call_id" in args:
                                        call_id = args["call_id"]
                                        break
                                except (json.JSONDecodeError, AttributeError):
                                    pass
    else:
        # Method 2: Get the most recent completed call from CallManager
        call_manager = get_call_manager()
        all_calls = call_manager.get_all_calls()

        # Find the most recently completed call
        completed_calls = [c for c in all_calls if c.status == "completed"]
        if completed_calls:
            # Sort by end_time (most recent first)
            completed_calls.sort(
                key=lambda c: c.end_time if c.end_time else c.start_time, reverse=True
            )
            most_recent_call = completed_calls[0]
            call_id = most_recent_call.call_id

    # If we have a call_id, get the actual call state from CallManager
    restaurant_name = None
    party_size = None
    confirmed_date = None
    confirmed_time = None
    confirmation_number = None
    customer_name = None
    special_requests = None
    status = "pending"

    if call_id:
        call_manager = get_call_manager()
        call_state = call_manager.get_call(call_id)
        if call_state:
            # Get basic reservation details
            restaurant_name = call_state.reservation_details.get("restaurant_name")
            party_size = call_state.reservation_details.get("party_size")
            customer_name = call_state.reservation_details.get("customer_name")
            special_requests = call_state.reservation_details.get("special_requests")

            # Get the actual confirmation details
            confirmation_number = call_state.confirmation_number
            status = call_state.status

            if call_state.start_time and call_state.end_time:
                (call_state.end_time - call_state.start_time).total_seconds()

            # Get the confirmed time from LLM analysis (stored in reservation_details)
            # If different from original, use that; otherwise fall back to original
            confirmed_time = call_state.reservation_details.get("confirmed_time")
            if not confirmed_time:
                # Fall back to original requested time
                confirmed_time = call_state.reservation_details.get("time", "")

            # Get the confirmed date from LLM analysis if available
            confirmed_date = call_state.reservation_details.get("confirmed_date")
            if not confirmed_date:
                confirmed_date = call_state.reservation_details.get("date", "")

    # Build the output message
    if restaurant_name:
        # Format the time nicely
        time_display = confirmed_time
        if confirmed_time:
            try:
                # Convert 24h to 12h format if needed
                if ":" in confirmed_time:
                    hour, minute = confirmed_time.split(":")
                    hour = int(hour)
                    minute = int(minute) if minute else 0
                    period = "PM" if hour >= 12 else "AM"
                    display_hour = hour if hour <= 12 else hour - 12
                    if display_hour == 0:
                        display_hour = 12
                    time_display = f"{display_hour}:{minute:02d} {period}"
            except (ValueError, AttributeError):
                pass

        date_display = confirmed_date if confirmed_date else "tomorrow"

        output.append(f"\nRestaurant: {restaurant_name}")
        output.append(f"Date: {date_display}")
        output.append(f"Time: {time_display}")
        output.append(f"Party Size: {party_size} people")

        if confirmation_number:
            output.append(f"Confirmation Number: {confirmation_number}")
        else:
            output.append("Confirmation Number: Not received")

        if customer_name:
            output.append(f"Reservation Name: {customer_name}")

        if special_requests:
            output.append(f"Special Instructions: {special_requests}")

        if status == "completed" and confirmation_number:
            output.append("\n✓ Reservation confirmed!")
        elif status == "completed":
            output.append("\n⚠ Call completed but no confirmation received.")
        else:
            output.append(f"\nStatus: {status.title()}")
    else:
        # No structured data available - return empty to avoid duplication
        return ""

    output.append("\n" + "=" * 60)

    return "\n".join(output)
