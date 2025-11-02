"""AI Concierge agents using OpenAI Agents SDK."""

from concierge.agents.orchestrator_agent import (
    OrchestratorAgent,
    create_orchestrator_agent,
    format_reservation_result,
)
from concierge.agents.reservation_agent import (
    ReservationAgent,
    ReservationDetails,
    create_reservation_agent,
)
from concierge.agents.tools import find_restaurant
from concierge.agents.voice_agent import (
    ReservationResult,
    VoiceAgent,
    create_voice_agent,
    make_reservation_call_via_twilio,
    simulate_reservation_call,
)

__all__ = [
    # Classes
    "OrchestratorAgent",
    "ReservationAgent",
    "ReservationDetails",
    "ReservationResult",
    "VoiceAgent",
    # Factory functions (backward compatibility)
    "create_orchestrator_agent",
    "create_reservation_agent",
    "create_voice_agent",
    # Tools
    "find_restaurant",
    # Utilities
    "format_reservation_result",
    "make_reservation_call_via_twilio",
    "simulate_reservation_call",
]
