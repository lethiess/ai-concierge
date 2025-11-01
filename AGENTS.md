# AI Concierge Agent Architecture

This document describes the agent architecture for the AI Concierge restaurant reservation system, built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python).

## Overview

The AI Concierge uses a **multi-agent architecture** with handoffs to handle restaurant reservations end-to-end:

```
User Input → Triage Agent → Voice Agent → Reservation Result
```

## Agents

### 1. Triage Agent

**Role**: Orchestrator and request parser

**Responsibilities**:
- Validate and parse natural language reservation requests
- Extract structured information (restaurant, party size, date, time, etc.)
- Look up restaurant information
- Hand off to Voice Agent for call execution

**Tools**:
- `find_restaurant`: Look up restaurant by name

**Handoffs**:
- `Voice Agent`: For making the actual reservation call

**Output Type**: `ReservationDetails` (structured Pydantic model)

### 2. Voice Agent

**Role**: Voice conversation executor

**Responsibilities**:
- Initiate outbound calls to restaurants via Twilio
- Conduct natural voice conversations
- Request reservation with all details
- Obtain confirmation numbers
- Handle edge cases (voicemail, unavailable times)

**Tools**:
- `make_call`: Initiate a phone call
- `get_call_status`: Check call status
- `end_call`: End active calls

**Output Type**: `ReservationResult` (structured Pydantic model)

## Function Tools

All tools are decorated with `@function_tool` from the Agents SDK:

### Restaurant Tools

```python
@function_tool
def find_restaurant(restaurant_name: str) -> dict:
    """Find a restaurant by name."""
```

### Twilio/Voice Tools

```python
@function_tool
def make_call(
    phone_number: str,
    restaurant_name: str,
    party_size: int,
    date: str,
    time: str,
    customer_name: str | None = None,
    special_requests: str | None = None,
) -> dict:
    """Initiate a phone call to make a reservation."""

@function_tool
def get_call_status(call_sid: str) -> dict:
    """Get the status of an ongoing call."""

@function_tool
def end_call(call_sid: str) -> dict:
    """End an active call."""
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
result = Runner.run_sync(
    agent=triage_agent,
    input=user_input,
)
```

**Loop flow**:
1. Triage agent receives user input
2. Guardrails validate input
3. Agent extracts reservation details using LLM
4. Agent uses `find_restaurant` tool to get restaurant info
5. Agent hands off to Voice Agent
6. Voice Agent uses `make_call` tool
7. Voice Agent returns structured `ReservationResult`
8. Guardrails validate output
9. Final output returned to user

## Example Flow

```python
# User: "Book a table at Demo Restaurant for 4 people tomorrow at 7pm"

# 1. Triage Agent processes input
# 2. Guardrails validate (passes)
# 3. Triage Agent extracts:
ReservationDetails(
    restaurant_name="Demo Restaurant",
    party_size=4,
    date="tomorrow",
    time="7pm",
    user_name=None,
    user_phone=None,
    special_requests=None
)

# 4. Triage Agent uses find_restaurant tool
# 5. Triage Agent hands off to Voice Agent
# 6. Voice Agent calls make_call tool
# 7. Voice Agent returns:
ReservationResult(
    status="confirmed",
    restaurant_name="Demo Restaurant",
    confirmation_number="DEMO-12345",
    message="Reservation confirmed...",
    call_duration=45.0
)

# 8. Output validated
# 9. Result displayed to user
```

## Key Benefits of Using Agents SDK

1. **Structured Outputs**: Automatic validation with Pydantic models
2. **Agent Handoffs**: Clean delegation between specialized agents
3. **Function Tools**: Type-safe tool definitions with automatic schema generation
4. **Built-in Guardrails**: Extensible input/output validation framework
5. **Tracing**: Automatic tracing for debugging and monitoring
6. **Provider Agnostic**: Works with OpenAI and 100+ other LLMs via LiteLLM

## Configuration

Agents are configured in `concierge/config.py`:

```python
agent_model: str = "gpt-4o"
agent_temperature: float = 0.7
```

## Testing

Tests use the SDK's Agent class directly:

```python
def test_create_triage_agent():
    voice_agent = create_voice_agent(...)
    triage_agent = create_triage_agent(voice_agent, find_restaurant)
    
    assert isinstance(triage_agent, Agent)
    assert len(triage_agent.handoffs) == 1
```

## References

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [Documentation](https://openai.github.io/openai-agents-python/)
- [Handoffs Example](https://github.com/openai/openai-agents-python/blob/main/examples/handoffs/message_filter.py)
- [Guardrails Documentation](https://openai.github.io/openai-agents-python/guardrails/)
