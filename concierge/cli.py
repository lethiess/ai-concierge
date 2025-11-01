"""Command-line interface for AI Concierge."""

import asyncio
import logging
import sys

from concierge.agents.triage_agent import TriageAgent
from concierge.agents.voice_agent import VoiceAgent
from concierge.config import get_config, setup_logging

logger = logging.getLogger(__name__)


class ConciergeCLI:
    """Command-line interface for the AI Concierge system."""

    def __init__(self) -> None:
        """Initialize the CLI."""
        self.config = get_config()
        setup_logging(self.config)
        self.triage_agent = TriageAgent()
        self.voice_agent = VoiceAgent()

        logger.info("AI Concierge CLI initialized")

        # Display configuration status
        self._display_config_status()

    def _display_config_status(self) -> None:
        """Display configuration status to the user."""
        print("\n" + "=" * 60)
        print("AI CONCIERGE - Restaurant Reservation System")
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

                # Process the request
                self._process_request(user_input)

            except KeyboardInterrupt:
                print("\n\nExiting AI Concierge. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                print(f"\n⚠ An unexpected error occurred: {e}")
                print("Please try again or type 'quit' to exit.")

    def _process_request(self, user_input: str) -> None:
        """Process a single reservation request.

        Args:
            user_input: User's natural language request
        """
        print("\n" + "-" * 60)
        print("Processing your request...")
        print("-" * 60 + "\n")

        # Step 1: Parse and validate with triage agent
        result = self.triage_agent.process_user_request(user_input)

        if not result["success"]:
            print(f"⚠ {result['error']}")
            print(f"(Error at stage: {result['stage']})")
            return

        # Extract parsed information
        request = result["request"]
        restaurant = result["restaurant"]

        # Display parsed information
        print("I understood your request as:")
        print(f"  Restaurant: {restaurant.name}")
        print(f"  Date: {request.date}")
        print(f"  Time: {request.time}")
        print(f"  Party size: {request.party_size} people")
        if request.user_name:
            print(f"  Name: {request.user_name}")
        if request.special_requests:
            print(f"  Special requests: {request.special_requests}")

        print(f"\nRestaurant phone: {restaurant.phone_number}")

        # Ask for confirmation
        confirm = input("\nProceed with this reservation? (yes/no): ").strip().lower()

        if confirm not in ["yes", "y"]:
            print("Reservation cancelled.")
            return

        # Step 2: Make the call with voice agent
        print("\n" + "-" * 60)
        print("Initiating call to restaurant...")
        print("-" * 60 + "\n")

        try:
            # Run async call in sync context
            reservation_result = asyncio.run(
                self.voice_agent.make_reservation_call(request, restaurant)
            )

            # Step 3: Display result
            formatted_result = self.triage_agent.format_result(reservation_result)
            print(formatted_result)

        except Exception as e:
            logger.error(f"Error making reservation: {e}", exc_info=True)
            print(f"\n⚠ Error making reservation: {e}")


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
