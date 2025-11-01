"""Command-line interface for AI Concierge using OpenAI Agents SDK."""

import logging
import sys

from agents import Runner

from concierge.agents.triage_agent import create_triage_agent, format_reservation_result
from concierge.agents.tools import (
    end_call,
    find_restaurant,
    get_call_status,
    make_call,
)
from concierge.agents.voice_agent import create_voice_agent
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

        # Create agents using the SDK
        voice_agent = create_voice_agent(make_call, get_call_status, end_call)
        self.triage_agent = create_triage_agent(voice_agent, find_restaurant)

        # Add guardrails
        self.triage_agent.guardrails = [
            input_validation_guardrail,
            party_size_guardrail,
            output_validation_guardrail,
        ]

        logger.info("AI Concierge CLI initialized with Agents SDK")

        # Display configuration status
        self._display_config_status()

    def _display_config_status(self) -> None:
        """Display configuration status to the user."""
        print("\n" + "=" * 60)
        print("AI CONCIERGE - Restaurant Reservation System")
        print("Powered by OpenAI Agents SDK")
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

        print("\n" + "=" * 60 + "\n")

    def run(self) -> None:
        """Run the CLI application."""
        print("Welcome! I can help you make restaurant reservations.\n")
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

                # Process the request using Agents SDK
                self._process_request(user_input)

            except KeyboardInterrupt:
                print("\n\nExiting AI Concierge. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                print(f"\n⚠ An unexpected error occurred: {e}")
                print("Please try again or type 'quit' to exit.")

    def _process_request(self, user_input: str) -> None:
        """Process a single reservation request using the Agents SDK.

        Args:
            user_input: User's natural language request
        """
        print("\n" + "-" * 60)
        print("Processing your request with AI agents...")
        print("-" * 60 + "\n")

        try:
            # Run the triage agent using the SDK Runner
            result = Runner.run_sync(
                agent=self.triage_agent,
                input=user_input,
            )

            # Display the result
            if hasattr(result, "final_output"):
                print("\n✓ Reservation processed successfully!")
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


async def async_main() -> None:
    """Async entry point for the CLI (if needed for async operations)."""
    cli = ConciergeCLI()
    cli.run()


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
