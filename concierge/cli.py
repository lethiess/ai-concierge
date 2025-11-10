"""Command-line interface for AI Concierge - HTTP client for server API."""

import logging
import sys
import uuid

import httpx

from concierge.config import get_config, setup_logging

logger = logging.getLogger(__name__)


class ConciergeCLI:
    """Command-line interface for the AI Concierge system - HTTP client."""

    def __init__(self) -> None:
        """Initialize the CLI."""
        self.config = get_config()
        setup_logging(self.config)

        # Generate session_id for this CLI conversation (enables conversation memory)
        self.session_id = f"cli-{uuid.uuid4().hex[:12]}"
        logger.info(f"CLI session_id: {self.session_id}")

        logger.info("AI Concierge CLI initialized as HTTP client")

        # Display configuration status
        self._display_config_status()

    def _display_config_status(self) -> None:
        """Display configuration status to the user."""
        print("\n" + "=" * 60)
        print("AI CONCIERGE - Restaurant Reservation System")
        print("Powered by OpenAI Agents SDK + Realtime API")
        print("\n" + "=" * 60)
        print(f"agent model: {self.config.agent_model}")
        print(f"realtime model: {self.config.realtime_model}")
        print(f"realtime voice: {self.config.realtime_voice}")
        print("\n" + "=" * 60 + "\n")

    def run(self) -> None:
        """Run the CLI application."""
        print("Welcome! I can help you with restaurant reservations.\n")
        print("Examples:")
        print('  "Book a table at Luigi\'s Pizza for 4 people tomorrow at 7pm"')
        print('  "Reserve 2 seats at New York Bar at Friday at 10:00 PM"')
        print('  "Table for 6 at The Steakhouse next Tuesday at 8pm under John Smith"')
        print('  "Cancel my reservation" (remembers from conversation!)\n')
        print(f"Session ID: {self.session_id}")
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
        """Process a single request by sending it to the server API.

        Args:
            user_input: User's natural language request
        """
        print("\n" + "-" * 60)
        print("Processing your request through AI Concierge...")
        print("-" * 60 + "\n")

        try:
            # Send request to server API with session_id for conversation memory
            with httpx.Client(timeout=300.0) as client:
                response = client.post(
                    f"{self.config.server_url}/process-request",
                    json={"user_input": user_input, "session_id": self.session_id},
                )

                if response.status_code == 200:
                    result = response.json()

                    # Display the result
                    print("\n✓ Request processed successfully!")

                    # Show agent response
                    final_output = result.get("final_output", "")
                    formatted_result = result.get("formatted_result", "")

                    if final_output:
                        print(f"\nAgent response:\n{final_output}")

                    # Only show formatted result if it's different from final_output
                    # (i.e., if we have structured reservation data)
                    if formatted_result and formatted_result != final_output:
                        print(f"\n{formatted_result}")

                else:
                    error_data = (
                        response.json()
                        if response.headers.get("content-type", "").startswith(
                            "application/json"
                        )
                        else {}
                    )
                    error_msg = error_data.get("error", response.text)
                    print(
                        f"\n⚠ Server error (status {response.status_code}): {error_msg}"
                    )

        except httpx.TimeoutException:
            logger.exception("Request timed out")
            print(
                "\n⚠ Request timed out. The server may be processing a long-running call."
            )
            print("Please try again or check the server logs.")
        except httpx.ConnectError:
            logger.exception("Cannot connect to server")
            print(f"\n⚠ Cannot connect to server at {self.config.server_url}")
            print("Make sure the server is running:")
            print("  python -m concierge.server")
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
