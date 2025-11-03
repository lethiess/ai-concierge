# AI Concierge Agent Architecture

This document describes the agent architecture for the AI Concierge restaurant reservation system, built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) and [Realtime API](https://openai.github.io/openai-agents-python/realtime/guide/).

## Overview

The AI Concierge uses a **2-tier agent architecture** with realtime voice capabilities for making actual phone calls to restaurants:

```
User Input (Text) → Orchestrator → Reservation Agent → Realtime Voice Call → Restaurant
```

Key features:
- **Intelligent Routing**: Orchestrator analyzes intent and routes to specialized agents
- **Structured Data Extraction**: Reservation agent parses and validates booking details  
- **Real-time Voice Conversations**: Uses OpenAI Realtime API for natural phone calls
- **Twilio Integration**: Connects actual phone calls via Twilio Media Streams

## Architecture Flow

### 1. Text Input Processing (CLI)
User provides reservation request via command line interface (text input)

### 2. Orchestrator Agent (Tier 1)
Analyzes request intent and routes to appropriate specialized agent

### 3. Reservation Agent (Tier 2)
- Parses reservation details using LLM
- Looks up restaurant information
- Validates constraints
- Triggers realtime voice call

### 4. Realtime Voice Call
- Uses OpenAI **RealtimeAgent** for natural voice conversation
- Connects via **Twilio Media Streams** for actual phone calls
- Full-duplex audio streaming (bidirectional)
- Real-time conversation with restaurant staff

## Agents

### 1. Orchestrator Agent (Tier 1)

**Role**: Request router and intent analyzer

**Responsibilities**:
- Analyze user requests to determine intent
- Route to appropriate specialized agent based on request type
- Handle unsupported request types gracefully

**Current Routing Logic**:
- Reservation requests → Reservation Agent
- Future: Cancellation requests → Cancellation Agent
- Future: Query requests → Query Agent
- Future: Modification requests → Modification Agent

**Handoffs**:
- `Reservation Agent`: For booking/making reservations
- Future: Additional specialized agents

### 2. Reservation Agent (Tier 2)

**Role**: Reservation workflow manager

**Responsibilities**:
- Parse and validate reservation details from user input
- Extract structured information (restaurant, party size, date, time, etc.)
- Look up restaurant information using tools
- Validate constraints (party size 1-50, all required fields present)
- **Trigger realtime voice call** via `initiate_reservation_call` tool

**Tools**:
- `find_restaurant`: Look up restaurant by name and phone number
- `initiate_reservation_call`: Trigger realtime voice call to restaurant

**Output Type**: `ReservationDetails` (structured Pydantic model)

**Note**: This agent does NOT hand off to another agent. Instead, it uses a tool that triggers a realtime voice call outside the agent loop.

### 3. Realtime Voice Agent (OpenAI Realtime API)

**Role**: Conduct real-time voice conversations

**Implementation**: Uses `RealtimeAgent` from the SDK, not a regular `Agent`

**Responsibilities**:
- Conduct natural voice conversation with restaurant staff
- Request reservation with all details (date, time, party size, name)
- Handle dynamic responses and interruptions
- Ask about alternative times if needed
- Obtain confirmation number
- Handle voicemail scenarios gracefully

**Configuration**:
- Model: `gpt-4o-realtime-preview-2024-10-01`
- Voice: Configurable (alloy, echo, fable, onyx, nova, shimmer)
- Audio Format: PCM16 for Twilio compatibility
- Temperature: 0.8 for natural conversation

**Integration**: 
- **Twilio Media Streams**: WebSocket connection for bidirectional audio
- **RealtimeRunner**: Manages the agent session
- **Audio Streaming**: Twilio ↔ WebSocket ↔ RealtimeAgent

## Function Tools

All tools are decorated with `@function_tool` from the Agents SDK:

### Restaurant Tool

```python
@function_tool
def find_restaurant(restaurant_name: str) -> dict:
    """Find a restaurant by name and get phone number."""
```

### Reservation Tool (Inside Reservation Agent)

```python
@function_tool
async def initiate_reservation_call(
    restaurant_name: str,
    restaurant_phone: str,
    party_size: int,
    date: str,
    time: str,
    customer_name: str | None = None,
    special_requests: str | None = None,
) -> dict:
    """Initiate a real-time voice call to make the restaurant reservation."""
```

## Realtime Voice Call Architecture

```
┌─────────────────┐
│  User (CLI)     │
│  Text Request   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Orchestrator   │
│  Agent          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Reservation    │
│  Agent          │
│  (Parses data)  │
└────────┬────────┘
         │
         │ initiate_reservation_call()
         ▼
┌─────────────────────────────────────────────┐
│  Realtime Voice Call                        │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐ │
│  │ Twilio  │──▶│WebSocket │──▶│ Realtime │ │
│  │  Call   │   │  Server  │   │  Agent   │ │
│  │         │◀──│          │◀──│          │ │
│  └─────────┘   └──────────┘   └──────────┘ │
│                                             │
│  Restaurant ←─── Audio ────→ OpenAI        │
└─────────────────────────────────────────────┘
```

## Guardrails

The system uses the SDK's built-in guardrail system for input and output validation:

### Input Guardrails

1. **Input Validation Guardrail**
   - Checks for empty input
   - Validates input length (max 1000 chars)
   - Blocks suspicious patterns (XSS, injection attempts)

2. **Party Size Guardrail**
   - Ensures party size is between 1-50 people
   - Validates numbers in user input

### Output Guardrails

1. **Output Validation Guardrail**
   - Detects sensitive information in output
   - Blocks outputs containing API keys, passwords, SSNs, credit cards

2. **Output Sanitization Guardrail**
   - Masks potential API keys and tokens
   - Redacts long alphanumeric sequences

## Agent Loop

The SDK's Runner executes the agent loop:

```python
runner = Runner()
result = runner.run_sync(starting_agent=orchestrator, input=user_input)
```

**Loop flow**:
1. Orchestrator receives user input
2. Guardrails validate input
3. Orchestrator analyzes intent (e.g., "reservation request")
4. Orchestrator hands off to Reservation Agent
5. Reservation Agent extracts reservation details using LLM
6. Reservation Agent uses `find_restaurant` tool to get restaurant info
7. Reservation Agent calls `initiate_reservation_call` tool
8. **Outside agent loop**: Realtime voice call is made
9. Voice call result is returned to Reservation Agent
10. Guardrails validate output
11. Final output returned to user

## Example Flow

```python
# User: "Book a table at Demo Restaurant for 4 people tomorrow at 7pm"

# 1. Orchestrator analyzes: "This is a reservation request"
# 2. Orchestrator hands off to Reservation Agent
# 3. Reservation Agent extracts:
ReservationDetails(
    restaurant_name="Demo Restaurant",
    party_size=4,
    date="tomorrow",
    time="7pm",
    user_name=None,
    user_phone=None,
    special_requests=None
)

# 4. Reservation Agent uses find_restaurant tool
# Returns: {"name": "Demo Restaurant", "phone_number": "+1234567890", ...}

# 5. Reservation Agent calls initiate_reservation_call tool
# This triggers:

# 6. Create RealtimeAgent with conversation context
voice_agent = RealtimeAgent(
    name="Restaurant Reservation Voice Agent",
    instructions="Call Demo Restaurant to book 4 people at 7pm tomorrow...",
    voice="alloy",
)

# 7. Connect Twilio call to WebSocket
# 8. Stream audio bidirectionally: Restaurant ↔ Twilio ↔ WebSocket ↔ RealtimeAgent
# 9. Conduct natural voice conversation
# 10. Extract confirmation number from conversation

# 11. Return result:
{
    "success": True,
    "status": "confirmed",
    "confirmation_number": "ABC123",
    "message": "Reservation confirmed...",
    "call_duration": 45.2
}

# 12. Result flows back through agent chain to user
```

## Twilio Media Streams Integration

For production deployment, the system requires:

1. **Twilio Account** with Media Streams capability
2. **WebSocket Server** to handle Twilio ↔ RealtimeAgent communication
3. **TwiML** configuration to route calls to WebSocket
4. **Audio Format Handling**:
   - Twilio uses 8kHz mulaw audio
   - RealtimeAgent uses PCM16
   - Conversion handled in WebSocket server
5. **Call Management**:
   - Track call state (initiated, ringing, answered, completed)
   - Handle interruptions and errors
   - Extract structured data from conversation

## Key Benefits of This Architecture

1. **Natural Conversations**: RealtimeAgent enables human-like phone calls
2. **Real-time Processing**: Full-duplex audio for immediate responses
3. **Modularity**: Orchestrator can route to different specialized agents
4. **Extensibility**: Easy to add cancellation, query, modification agents
5. **Structured Outputs**: Pydantic models ensure data validation
6. **Intelligent Routing**: Orchestrator handles different request types

## Key Benefits of Using Agents SDK + Realtime API

1. **Structured Outputs**: Automatic validation with Pydantic models
2. **Agent Handoffs**: Clean delegation between specialized agents
3. **Function Tools**: Type-safe tool definitions
4. **Built-in Guardrails**: Extensible validation framework
5. **Tracing**: Automatic debugging and monitoring
6. **Realtime Voice**: Natural, low-latency conversations
7. **Provider Agnostic**: Works with OpenAI and 100+ LLMs via LiteLLM

## Configuration

Agents are configured in `concierge/config.py`:

```python
agent_model: str = "gpt-4o"  # For text agents
realtime_model: str = "gpt-4o-realtime-preview-2024-10-01"  # For voice
```

## Testing

Tests verify agent creation and tool functionality:

```python
def test_create_voice_agent():
    reservation_details = {...}
    voice_agent = create_voice_agent(reservation_details)
    
    assert isinstance(voice_agent, RealtimeAgent)
    assert "restaurant_name" in voice_agent.instructions
```

## Future Extensibility

The orchestrator pattern makes it easy to add new capabilities:

### Cancellation Agent
```python
cancellation_agent = Agent(
    name="Cancellation Agent",
    instructions="Handle reservation cancellations...",
    tools=[find_reservation, cancel_via_call],
)

orchestrator = create_orchestrator_agent(
    reservation_agent,
    cancellation_agent,  # New!
)
```

## References

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [Realtime API Guide](https://openai.github.io/openai-agents-python/realtime/guide/)
- [Voice Examples](https://github.com/openai/openai-agents-python/tree/main/examples/voice)
- [SDK Documentation](https://openai.github.io/openai-agents-python/)
- [Guardrails Documentation](https://openai.github.io/openai-agents-python/guardrails/)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/twiml/stream)
