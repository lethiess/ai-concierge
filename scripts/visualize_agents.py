#!/usr/bin/env python3
"""Generate agent visualization using OpenAI Agents SDK.

This script creates visual graphs of the AI Concierge agent architecture,
showing agents, tools, and handoffs.

Requirements:
- openai-agents[viz] package installed
- Graphviz installed on your system

Usage:
    python scripts/visualize_agents.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def main():
    """Generate and display agent visualizations."""
    try:
        from agents.extensions.visualization import draw_graph
    except ImportError:
        print("Error: openai-agents[viz] not installed.")
        print("Install with: pip install 'openai-agents[viz]'")
        print("Also ensure Graphviz is installed on your system.")
        sys.exit(1)

    # Import agents and tools
    from concierge.agents.cancellation_agent import CancellationAgent
    from concierge.agents.orchestrator_agent import OrchestratorAgent
    from concierge.agents.reservation_agent import ReservationAgent
    from concierge.agents.search_agent import SearchAgent
    from concierge.agents.transcript_agent import TranscriptAnalysisAgent
    from concierge.agents.tools import (
        find_restaurant,
        initiate_cancellation_call,
        initiate_reservation_call,
        lookup_reservation_from_history,
        search_restaurants_llm,
    )
    from concierge.agents.guardrails import (
        input_validation_guardrail,
        output_validation_guardrail,
        party_size_guardrail,
    )

    print("Creating agent instances...")

    # Create specialized agents (Tier 2)
    reservation_agent_instance = ReservationAgent(
        find_restaurant, initiate_reservation_call
    )
    reservation_agent = reservation_agent_instance.create()

    cancellation_agent_instance = CancellationAgent(
        lookup_reservation_from_history, initiate_cancellation_call
    )
    cancellation_agent = cancellation_agent_instance.create()

    search_agent_instance = SearchAgent(search_restaurants_llm)
    search_agent = search_agent_instance.create()

    # Create orchestrator agent (Tier 1)
    orchestrator_instance = OrchestratorAgent(
        reservation_agent=reservation_agent,
        cancellation_agent=cancellation_agent,
        search_agent=search_agent,
        input_guardrails=[
            input_validation_guardrail,
            party_size_guardrail,
        ],
        output_guardrails=[
            output_validation_guardrail,
        ],
    )
    orchestrator = orchestrator_instance.create()

    # Create transcript agent
    transcript_agent_instance = TranscriptAnalysisAgent()
    transcript_agent_instance.create()

    from concierge.agents.voice_agent import VoiceAgent

    # ... (rest of imports)

    # Create voice agents (RealtimeAgent instances)
    # These need sample data to create
    sample_reservation_details = {
        "restaurant_name": "Demo Restaurant",
        "restaurant_phone": "+1234567890",
        "party_size": 4,
        "date": "tomorrow",
        "time": "7pm",
        "customer_name": "Demo Customer",
        "special_requests": "None",
        "confirmation_number": "12345",
    }

    reservation_voice_agent_instance = VoiceAgent(
        "reservation_voice_agent", sample_reservation_details
    )
    reservation_voice_agent = reservation_voice_agent_instance.create()

    cancellation_voice_agent_instance = VoiceAgent(
        "cancellation_voice_agent", sample_reservation_details
    )
    cancellation_voice_agent = cancellation_voice_agent_instance.create()

    print("Generating visualizations...")

    # Graph 1: Main Architecture (Orchestrator)
    print("\n1. Generating main architecture graph (Orchestrator)...")
    orchestrator_output_path = (
        project_root / "docs" / "orchestrator_agent_visualization"
    )
    try:
        draw_graph(orchestrator, filename=str(orchestrator_output_path))
        print(f"   ✓ Saved to: {orchestrator_output_path}.png")
    except Exception as e:
        print(f"   ⚠ Could not visualize orchestrator agent: {e}")

    # Graph 1b: Reservation Agent
    print("\n1b. Generating reservation agent graph...")
    reservation_output_path = project_root / "docs" / "reservation_agent_visualization"
    try:
        draw_graph(reservation_agent, filename=str(reservation_output_path))
        print(f"   ✓ Saved to: {reservation_output_path}.png")
    except Exception as e:
        print(f"   ⚠ Could not visualize reservation agent: {e}")

    # Graph 1c: Cancellation Agent
    print("\n1c. Generating cancellation agent graph...")
    cancellation_output_path = (
        project_root / "docs" / "cancellation_agent_visualization"
    )
    try:
        draw_graph(cancellation_agent, filename=str(cancellation_output_path))
        print(f"   ✓ Saved to: {cancellation_output_path}.png")
    except Exception as e:
        print(f"   ⚠ Could not visualize cancellation agent: {e}")

    # Graph 1d: Search Agent
    print("\n1d. Generating search agent graph...")
    search_output_path = project_root / "docs" / "search_agent_visualization"
    try:
        draw_graph(search_agent, filename=str(search_output_path))
        print(f"   ✓ Saved to: {search_output_path}.png")
    except Exception as e:
        print(f"   ⚠ Could not visualize search agent: {e}")

    # Graph 2: Transcript Analysis Agent
    print("\n2. Generating transcript agent graph...")
    transcript_output_path = project_root / "docs" / "transcript_agent_visualization"
    try:
        draw_graph(transcript_agent_instance, filename=str(transcript_output_path))
        print(f"   ✓ Saved to: {transcript_output_path}.png")
    except Exception as e:
        print(f"   ⚠ Could not visualize transcript agent: {e}")

    # Graph 3: Reservation Voice Agent (RealtimeAgent)
    print("\n3. Generating reservation voice agent graph...")
    reservation_voice_output_path = (
        project_root / "docs" / "reservation_voice_agent_visualization"
    )
    try:
        draw_graph(reservation_voice_agent, filename=str(reservation_voice_output_path))
        print(f"   ✓ Saved to: {reservation_voice_output_path}.png")
    except Exception as e:
        print(f"   ⚠ Could not visualize reservation voice agent: {e}")
        print("      (RealtimeAgent may not be compatible with draw_graph)")

    # Graph 4: Cancellation Voice Agent (RealtimeAgent)
    print("\n4. Generating cancellation voice agent graph...")
    cancellation_voice_output_path = (
        project_root / "docs" / "cancellation_voice_agent_visualization"
    )
    try:
        draw_graph(
            cancellation_voice_agent, filename=str(cancellation_voice_output_path)
        )
        print(f"   ✓ Saved to: {cancellation_voice_output_path}.png")
    except Exception as e:
        print(f"   ⚠ Could not visualize cancellation voice agent: {e}")
        print("      (RealtimeAgent may not be compatible with draw_graph)")

    print("\n" + "=" * 70)
    print("Visualization Summary")
    print("=" * 70)
    print("\nThe visualizations show:")
    print("  - Yellow boxes: Agents")
    print("  - Green ellipses: Tools")
    print("  - Arrows: Handoffs between agents")
    print("  - __start__ node: Entry point")
    print("  - __end__ node: Exit point")
    print("\nGenerated graphs:")

    # Summary of generated graphs
    print(f"  1. Orchestrator agent: {orchestrator_output_path}.png")
    print(f"  1b. Reservation agent: {reservation_output_path}.png")
    print(f"  1c. Cancellation agent: {cancellation_output_path}.png")
    print(f"  1d. Search agent: {search_output_path}.png")
    print(f"  2. Transcript agent: {transcript_output_path}.png")
    print(f"  3. Reservation voice agent: {reservation_voice_output_path}.png")
    print(f"  4. Cancellation voice agent: {cancellation_voice_output_path}.png")


if __name__ == "__main__":
    main()
