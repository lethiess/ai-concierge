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

Key features:
- **Intelligent Routing**: Orchestrator analyzes intent and routes to 3 specialized agents
- **Session Memory**: SQLiteSession maintains conversation history across turns
- **Real-time Voice Conversations**: Uses OpenAI Realtime API for natural phone calls
- **Twilio Integration**: Connects actual phone calls via Twilio Media Streams
- **LLM-Powered Search**: Generates realistic restaurant recommendations
- **Rate Limiting**: Guardrails prevent abuse (5/hour, 20/day per session)

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
- Reservation requests ("book", "reserve") → Reservation Agent
- Cancellation requests ("cancel", "remove reservation") → Cancellation Agent
- Search requests ("find restaurant", "best italian") → Search Agent

**Handoffs**:
- `Reservation Agent`: For booking/making reservations
- `Cancellation Agent`: For cancelling reservations (NEW!)
- `Search Agent`: For restaurant discovery (NEW!)

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

### 3. Cancellation Agent (Tier 2) - NEW!

**Role**: Reservation cancellation manager

**Responsibilities**:
- Parse cancellation requests (confirmation # or "my reservation")
- Search conversation history for recent reservations using session memory
- Extract structured cancellation information
- **Trigger realtime voice call** via `initiate_cancellation_call` tool

**Tools**:
- `lookup_reservation_from_history`: Search SQLiteSession for recent reservations
- `initiate_cancellation_call`: Trigger realtime voice call to cancel reservation

**Key Feature**: Uses **session memory** to find reservations! User can say "cancel my reservation" without providing details.

**Output Type**: Voice call result with cancellation status

### 4. Search Agent (Tier 2) - NEW!

**Role**: Restaurant discovery and recommendations

**Responsibilities**:
- Parse natural language search queries
- Extract search criteria (cuisine, location, rating)
- **Generate restaurant options** via LLM-powered mock search
- Present results to user

**Tools**:
- `search_restaurants_llm`: Uses OpenAI API to generate realistic restaurant data based on criteria

**Key Feature**: All generated restaurants map to demo phone number for actual reservations!

**Example queries**:
- "Find the best Italian restaurant in Konstanz"
- "Show me highly rated Chinese food"
- "Where can I get vegetarian options downtown"

### 5. Realtime Voice Agent (OpenAI Realtime API)

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

## Session Memory (NEW!)

The system uses **SQLiteSession** from the OpenAI Agents SDK for conversation memory:

### How it Works

1. Each user conversation gets a unique `session_id`
2. All messages (user, assistant, tool results) are automatically stored
3. Session persists across multiple requests
4. Agents can access conversation history via context

### Benefits

- **"Cancel my reservation"** works without providing details (searches history!)
- Multi-turn conversations: "Find Italian → Book that → Cancel it"
- No manual state management needed
- Automatic context preservation

### Implementation

```python
# Server creates session per request
session = SQLiteSession(session_id, "conversations.db")
result = await runner.run(orchestrator, user_input, session=session)
```

### Tools Using Session Memory

- `lookup_reservation_from_history`: Searches session for recent reservations

## Guardrails

The system uses the SDK's built-in guardrail system for validation and rate limiting:

### Input Guardrails

1. **Rate Limiting Guardrail (NEW!)**
   - Limits: 5 requests/hour per session, 20/day
   - Tracks requests in SQLite database
   - Prevents abuse and controls costs

2. **Input Validation Guardrail**
   - Checks for empty input
   - Validates input length (max 1000 chars)
   - Blocks suspicious patterns (XSS, injection attempts)

3. **Party Size Guardrail**
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

**Loop flow** (with session memory):
1. Session created/retrieved via `SQLiteSession(session_id)`
2. Orchestrator receives user input with conversation history
3. Guardrails validate input (rate limiting checks session history)
4. Orchestrator analyzes intent and routes to specialized agent:
   - "book" → Reservation Agent
   - "cancel" → Cancellation Agent
   - "find" → Search Agent
5. Specialized agent processes request:
   - May use tools (find_restaurant, search_llm, lookup_history)
   - May trigger voice calls (reservation or cancellation)
6. **Outside agent loop**: Realtime voice call if needed
7. Result returned to specialized agent
8. Specialized agent hands back to Orchestrator
9. Guardrails validate output
10. Final output returned to user
11. **All conversation stored in session automatically**

## Example Flows

### Scenario 1: Make Reservation

```python
# Turn 1: "Book a table at Luigi's for 4 people tomorrow at 7pm"
session = SQLiteSession("user_123", "conversations.db")
result = await runner.run(orchestrator, input, session=session)

# 1. Orchestrator routes to Reservation Agent
# 2. Reservation Agent extracts details and calls find_restaurant
# 3. initiate_reservation_call triggers voice call
# 4. RealtimeAgent conducts conversation → gets confirmation #ABC123
# 5. Result stored in session history automatically
```

### Scenario 2: Cancel Using Session Memory (NEW!)

```python
# Turn 2 (same session): "Cancel my reservation"

# 1. Orchestrator routes to Cancellation Agent
# 2. Cancellation Agent uses lookup_reservation_from_history tool
# 3. Tool searches session history → finds reservation #ABC123
# 4. initiate_cancellation_call triggers voice call
# 5. RealtimeAgent cancels reservation
# 6. Result returned: "Reservation cancelled successfully"
```

### Scenario 3: Search Then Book (Multi-Turn)

```python
# Turn 1: "Find the best Italian restaurant in Konstanz"
# → Search Agent uses search_restaurants_llm
# → LLM generates 3-5 realistic options
# → User sees: "Bella Italia (4.8⭐), La Taverna (4.6⭐), ..."

# Turn 2: "Book Bella Italia for 2 tomorrow at 8pm"
# → Orchestrator remembers Bella Italia from search (session memory!)
# → Reservation Agent makes booking
# → Voice call conducted

# Turn 3: "Actually, cancel that"
# → Cancellation Agent finds booking in session history
# → Cancellation voice call made
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
3. **Session Memory**: SQLiteSession enables "cancel my reservation" without details
4. **Modularity**: Orchestrator routes to 3 specialized agents
5. **Multi-Turn Dialogs**: Search → Book → Cancel in one conversation
6. **Extensibility**: Easy to add more specialized agents
7. **Structured Outputs**: Pydantic models ensure data validation
8. **Intelligent Routing**: Orchestrator handles different request types
9. **Rate Limiting**: Guardrails prevent abuse
10. **LLM-Powered Search**: Generate realistic options without external APIs

## Key Benefits of Using Agents SDK + Realtime API

1. **Session Memory**: Automatic conversation history management (no manual state!)
2. **Structured Outputs**: Automatic validation with Pydantic models
3. **Agent Handoffs**: Clean delegation between specialized agents
4. **Function Tools**: Type-safe tool definitions
5. **Built-in Guardrails**: Extensible validation and rate limiting
6. **Tracing**: Automatic debugging and monitoring
7. **Realtime Voice**: Natural, low-latency conversations
8. **Provider Agnostic**: Works with OpenAI and 100+ LLMs via LiteLLM

## Demonstrating SDK Capabilities

This implementation showcases:

1. **Multi-Agent Orchestration**: 3 specialized agents with intelligent routing
2. **Session Memory**: SQLiteSession for conversation persistence
3. **Realtime API**: Voice calls for both booking AND cancellation
4. **Custom Guardrails**: Rate limiting with SQLite tracking
5. **Tool Composition**: find_restaurant, search_llm, lookup_history, voice calls
6. **LLM Tool Calling**: Search agent uses LLM to generate mock data
7. **Context Management**: Session enables "cancel my reservation" magic

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
