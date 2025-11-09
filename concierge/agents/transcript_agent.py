"""Agent for analyzing call transcripts and extracting confirmed reservation details."""

import logging
from agents import Agent, Runner
from concierge.config import get_config
from concierge.models import ConfirmedReservationDetails
from concierge.prompts import load_prompt

logger = logging.getLogger(__name__)


class TranscriptAnalysisAgent:
    """Agent that analyzes call transcripts to extract confirmed reservation details.

    This agent reads the conversation between the voice agent and restaurant staff,
    understands the context, and extracts the ACTUAL confirmed details rather than
    the originally requested details.
    """

    def __init__(self):
        self.config = get_config()
        self._agent = None

    def create(self) -> Agent:
        """Create the transcript analysis agent."""
        if self._agent is not None:
            return self._agent

        instructions = load_prompt("transcript_agent")

        self._agent = Agent(
            name="Transcript Analysis Agent",
            model=self.config.agent_model,
            instructions=instructions,
            output_type=ConfirmedReservationDetails,
        )

        logger.info("Transcript Analysis Agent created")
        return self._agent

    async def analyze_transcript(
        self, transcript_lines: list[str], original_details: dict
    ) -> ConfirmedReservationDetails:
        """Analyze a transcript and extract confirmed details.

        Args:
            transcript_lines: List of transcript lines from the call
            original_details: The originally requested reservation details

        Returns:
            ConfirmedReservationDetails with extracted information
        """
        if not self._agent:
            self.create()

        # Format transcript for analysis
        formatted_transcript = "\n".join(transcript_lines)

        # Create analysis prompt
        analysis_prompt = f"""Analyze this restaurant reservation call transcript.

ORIGINALLY REQUESTED:
- Time: {original_details.get('time')}
- Date: {original_details.get('date')}
- Party size: {original_details.get('party_size')}
- Name: {original_details.get('customer_name', 'Not specified')}

CONVERSATION TRANSCRIPT:
{formatted_transcript}

Extract the ACTUAL CONFIRMED details from this conversation.
Focus on what the restaurant AGREED TO, not what was originally requested.
Pay special attention to confirmation numbers mentioned near the end of the conversation."""

        logger.info("Analyzing transcript with LLM...")

        runner = Runner()
        result = await runner.run(starting_agent=self._agent, input=analysis_prompt)

        # The output should be a ConfirmedReservationDetails object
        confirmed_details = result.final_output

        logger.info("✓ LLM analysis complete:")
        logger.info(f"  - Confirmed time: {confirmed_details.confirmed_time}")
        logger.info(f"  - Confirmation number: {confirmed_details.confirmation_number}")
        logger.info(f"  - Was modified: {confirmed_details.was_modified}")

        return confirmed_details


# Singleton instance
_transcript_agent = None


def get_transcript_agent() -> TranscriptAnalysisAgent:
    """Get or create the transcript analysis agent."""
    global _transcript_agent
    if _transcript_agent is None:
        _transcript_agent = TranscriptAnalysisAgent()
    return _transcript_agent
