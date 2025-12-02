# System Architecture

## Agent Hierarchy

The system uses a 2-tier agent architecture with a central orchestrator.

```mermaid
graph TD
    User[User Input] --> Orchestrator[Orchestrator Agent]
    Orchestrator -->|"reserve"| Reservation[Reservation Agent]
    Orchestrator -->|"cancel"| Cancellation[Cancellation Agent]
    Orchestrator -->|"search"| Search[Search Agent]
    
    Reservation -->|tool| InitiateReservation[initiate_reservation_call]
    Cancellation -->|tool| InitiateCancellation[initiate_cancellation_call]
    
    InitiateReservation --> ReservationVoice["ReservationVoiceAgent<br/>(Realtime API)"]
    InitiateCancellation --> CancellationVoice["CancellationVoiceAgent<br/>(Realtime API)"]
    
    ReservationVoice --> TwilioHandler[Twilio Handler]
    CancellationVoice --> TwilioHandler
    TwilioHandler --> Restaurant[Restaurant Phone]
```

## Agent Details

### 1. Orchestrator Agent (Tier 1)
Routes requests based on intent:
- "book" → Reservation Agent
- "cancel" → Cancellation Agent
- "find" → Search Agent

### 2. Reservation Agent (Tier 2)
- Parses reservation details.
- Uses `find_restaurant` tool.
- Triggers voice call via `initiate_reservation_call`.

### 3. Cancellation Agent (Tier 2)
- Parses cancellation requests.
- Uses `lookup_reservation_from_history` to find reservations in session memory.
- Triggers cancellation call via `initiate_cancellation_call`.

### 4. Search Agent (Tier 2)
- Parses search queries.
- Uses `search_restaurants_llm` to generate realistic options.

### 5. Realtime Voice Agent
- Conducts natural voice conversations using OpenAI Realtime API.
- Connects via Twilio Media Streams.

## Voice Call Flow

Real-time voice calls are handled via Twilio Media Streams and OpenAI Realtime API.

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator
    participant Tool as initiate_reservation_call
    participant CallManager
    participant Twilio
    participant Handler as TwilioHandler
    participant Agent as RealtimeAgent
    participant Restaurant

    User->>Orchestrator: "Book table..."
    Orchestrator->>Tool: initiate_reservation_call()
    Tool->>CallManager: Create call state
    Tool->>Twilio: Initiate call
    
    Twilio->>Restaurant: Dial phone
    Twilio->>Handler: WebSocket Connect
    Handler->>Agent: Start Realtime Session
    
    loop Voice Conversation
        Restaurant->>Twilio: Audio
        Twilio->>Handler: Stream Audio
        Handler->>Agent: Stream Audio
        Agent->>Handler: Audio Response
        Handler->>Twilio: Stream Audio
        Twilio->>Restaurant: Audio
    end
    
    Twilio->>Handler: Stop
    Handler->>CallManager: Save Transcript & Status
    Tool->>CallManager: Poll for result
    Tool-->>Orchestrator: Confirmation Details
```

## Session Memory

The system uses two separate storage mechanisms:

1. **SQLiteSession**: Stores conversation history (messages, tool results) for context-aware responses.
2. **CallManager**: Stores completed call states with confirmation numbers for reservation lookup.

```mermaid
graph LR
    User --> Orchestrator
    Orchestrator --> Session[(SQLiteSession)]
    VoiceCall --> CallManager[(CallManager)]
    CancellationAgent -->|lookup| CallManager
```

## Guardrails
- **Input**: Rate limiting, validation, party size checks.
- **Output**: Sanitization (PII redaction), validation.

## Configuration
Agents are configured in `concierge/config.py`.
