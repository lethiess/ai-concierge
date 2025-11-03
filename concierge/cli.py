"""Command-line interface for AI Concierge using OpenAI Agents SDK."""

import logging
import os
import sys

from agents import Runner
from agents.extensions.visualization import draw_graph

from concierge.agents import (
    OrchestratorAgent,
    ReservationAgent,
    format_reservation_result,
)
from concierge.agents.tools import find_restaurant
from concierge.config import get_config, setup_logging
from concierge.guardrails.input_validator import (
    input_validation_guardrail,
    party_size_guardrail,
)
from concierge.guardrails.output_validator import output_validation_guardrail

logger = logging.getLogger(__name__)


class ConciergeCLI:
    """Command-line interface for the AI Concierge system using Agents SDK."""

    def __init__(self) -> None:
        """Initialize the CLI."""
        self.config = get_config()
        setup_logging(self.config)

        # Ensure OpenAI API key is available to the SDK via environment variable
        # The SDK reads directly from os.environ, not from our Config
        if self.config.openai_api_key and "OPENAI_API_KEY" not in os.environ:
            os.environ["OPENAI_API_KEY"] = self.config.openai_api_key

        # Create the 2-tier agent architecture:
        # Orchestrator → Reservation Agent (which triggers realtime voice calls)

        # Tier 2: Reservation Agent (handles reservation logic + voice calls)
        reservation_agent_instance = ReservationAgent(find_restaurant)
        reservation_agent = reservation_agent_instance.create()

        # Tier 1: Orchestrator (routes requests)
        orchestrator_instance = OrchestratorAgent(reservation_agent)
        self.orchestrator = orchestrator_instance.create()

        # Add guardrails to the orchestrator
        self.orchestrator.guardrails = [
            input_validation_guardrail,
            party_size_guardrail,
            output_validation_guardrail,
        ]

        draw_graph(self.orchestrator, filename="agent_graph")

        logger.info("AI Concierge CLI initialized with realtime voice capabilities")

        # Display configuration status
        self._display_config_status()

    def _display_config_status(self) -> None:
        """Display configuration status to the user."""
        print("\n" + "=" * 60)
        print("AI CONCIERGE - Restaurant Reservation System")
        print("Powered by OpenAI Agents SDK + Realtime API")
        print("=" * 60)

        print("\nConfiguration Status:")
        print(
            f"  OpenAI API: {'✓ Configured' if self.config.openai_api_key else '✗ Not configured'}"
        )
        print(
            f"  Twilio:     {'✓ Configured' if self.config.has_twilio_config() else '✗ Not configured (will simulate)'}"
        )

        if not self.config.has_twilio_config():
            print("\nNote: Twilio is not configured. Calls will be simulated.")
            print("To enable real calls, set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,")
            print("and TWILIO_PHONE_NUMBER in your .env file.")

        print("\nAgent Architecture:")
        print("  Orchestrator → Reservation Agent → Realtime Voice Call")
        print("  (Uses OpenAI Realtime API for natural phone conversations)")

        print("\n" + "=" * 60 + "\n")

    def run(self) -> None:
        """Run the CLI application."""
        print("Welcome! I can help you with restaurant reservations.\n")
        print("Examples:")
        print('  "Book a table at Demo Restaurant for 4 people tomorrow at 7pm"')
        print('  "Reserve 2 seats at Mario\'s Pizza on Friday at 6:30 PM"')
        print(
            '  "Table for 6 at The Steakhouse next Tuesday at 8pm under John Smith"\n'
        )
        print("Type 'quit' or 'exit' to end the session.\n")

        while True:
            try:
                # Get user input
                user_input = input("\nYour request: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("\nThank you for using AI Concierge. Goodbye!")
                    break

                # Process the request through the orchestrator
                self._process_request(user_input)

            except KeyboardInterrupt:
                print("\n\nExiting AI Concierge. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                print(f"\n⚠ An unexpected error occurred: {e}")
                print("Please try again or type 'quit' to exit.")

    def _process_request(self, user_input: str) -> None:
        """Process a single request using the orchestrator.

        The orchestrator will route to the appropriate specialized agent.

        Args:
            user_input: User's natural language request
        """
        print("\n" + "-" * 60)
        print("Processing your request through AI Concierge...")
        print("-" * 60 + "\n")

        try:
            # Run the orchestrator using the SDK Runner
            # The orchestrator will route to the appropriate agent
            runner = Runner()
            result = runner.run_sync(starting_agent=self.orchestrator, input=user_input)

            # Display the result
            if hasattr(result, "final_output"):
                print("\n✓ Request processed successfully!")
                print(f"\nAgent response:\n{result.final_output}")
            else:
                print("\n✓ Request processed")
                print(f"\nResult: {result}")

            # Display formatted result if available
            formatted = format_reservation_result(result)
            print(f"\n{formatted}")

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            print(f"\n⚠ Error processing request: {e}")
            print("\nPlease try again with a different request.")


def main() -> None:
    """Main entry point for the CLI."""
    try:
        # Validate configuration by attempting to load it
        get_config()
    except Exception as e:
        print(f"Configuration error: {e}")
        print("\nPlease set the required environment variables.")
        print("Create a .env file with at minimum:")
        print("  OPENAI_API_KEY=your_key_here")
        sys.exit(1)

    # Run the CLI
    cli = ConciergeCLI()
    cli.run()


if __name__ == "__main__":
    main()
