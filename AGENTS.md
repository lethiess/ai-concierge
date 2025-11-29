# AI Concierge Agent Architecture

This document describes the agent architecture for the AI Concierge restaurant reservation system, built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) and [Realtime API](https://openai.github.io/openai-agents-python/realtime/guide/).

## Overview

The AI Concierge uses a **2-tier agent architecture** with realtime voice capabilities and conversation memory:

```
                      ┌─ Reservation Agent → Voice Call (Make)
User → Orchestrator ──┼─ Cancellation Agent → Voice Call (Cancel) + Session Lookup
  ↕                   └─ Search Agent → LLM Mock Search
SQLiteSession
(Conversation Memory)
```

## Architecture Flow

1.  **Text Input Processing (CLI)**: User provides reservation request via command line interface.
2.  **Orchestrator Agent (Tier 1)**: Analyzes request intent and routes to appropriate specialized agent.
3.  **Specialized Agents (Tier 2)**:
    -   **Reservation Agent**: Parses details, validates constraints, triggers voice call.
    -   **Cancellation Agent**: Searches history, extracts details, triggers cancellation call.
    -   **Search Agent**: Generates restaurant recommendations via LLM.
4.  **Realtime Voice Call**: Uses OpenAI **RealtimeAgent** and **Twilio Media Streams** for natural voice conversations.

## Agents

### 1. Orchestrator Agent
Routes requests based on intent:
-   "book" → Reservation Agent
-   "cancel" → Cancellation Agent
-   "find" → Search Agent

### 2. Reservation Agent
-   Parses reservation details.
-   Uses `find_restaurant` tool.
-   Triggers voice call via `initiate_reservation_call`.

### 3. Cancellation Agent
-   Parses cancellation requests.
-   Uses `lookup_reservation_from_history` to find reservations in session memory.
-   Triggers cancellation call via `initiate_cancellation_call`.

### 4. Search Agent
-   Parses search queries.
-   Uses `search_restaurants_llm` to generate realistic options.

### 5. Realtime Voice Agent
-   Conducts natural voice conversations using OpenAI Realtime API.
-   Connects via Twilio Media Streams.

## Session Memory
The system uses **SQLiteSession** to persist conversation history, enabling features like "cancel my reservation" without re-entering details.

## Guardrails
-   **Input**: Rate limiting, validation, party size checks.
-   **Output**: Sanitization (PII redaction), validation.

## Configuration
Agents are configured in `concierge/config.py`.

## References
-   [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
-   [Realtime API Guide](https://openai.github.io/openai-agents-python/realtime/guide/)
