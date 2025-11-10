# Agent Flow Architecture

This document visualizes the multi-agent architecture and routing flow of the AI Concierge system.

## Agent Hierarchy and Routing

```mermaid
graph TD
    User[User Input] --> Orchestrator[Orchestrator Agent<br/>Intent Analysis & Routing]
    
    Orchestrator -->|"reserve"| Reservation[Reservation Agent<br/>Parse & Validate Details]
    Orchestrator -->|"cancel"| Cancellation[Cancellation Agent<br/>Lookup & Cancel]
    Orchestrator -->|"search"| Search[Search Agent<br/>Restaurant Discovery]
    
    Reservation -->|tool| FindRestaurant[find_restaurant]
    Reservation -->|tool| InitiateReservation[initiate_reservation_call]
    
    Cancellation -->|tool| LookupHistory[lookup_reservation_from_history]
    Cancellation -->|tool| InitiateCancellation[initiate_cancellation_call]
    
    Search -->|tool| SearchLLM[search_restaurants_llm]
    
    FindRestaurant --> RestaurantDB[(Restaurant Service)]
    InitiateReservation --> ReservationVoice[ReservationVoiceAgent<br/>RealtimeAgent]
    InitiateCancellation --> CancellationVoice[CancellationVoiceAgent<br/>RealtimeAgent]
    SearchLLM --> LLMGeneration[LLM Generation]
    
    ReservationVoice --> TwilioHandler[Twilio Handler<br/>WebSocket Audio]
    CancellationVoice --> TwilioHandler
    TwilioHandler --> Restaurant[Restaurant<br/>Phone Call]
    
    TwilioHandler --> CallManagerDB[(CallManager<br/>Call State)]
    CallManagerDB --> TranscriptAgent[Transcript Analysis Agent<br/>Extract Confirmation]
    
    LookupHistory --> CallManagerDB
    
    Reservation -.->|return| Orchestrator
    Cancellation -.->|return| Orchestrator
    Search -.->|return| Orchestrator
    
    Orchestrator --> Result[Final Result<br/>to User]
    
    style Orchestrator fill:#ffddff
    style Reservation fill:#ffddff
    style Cancellation fill:#ffddff
    style Search fill:#ffddff
    style ReservationVoice fill:#ffa500
    style CancellationVoice fill:#ffa500
    style TranscriptAgent fill:#87ceeb
    style FindRestaurant fill:#9deddd
    style InitiateReservation fill:#9deddd
    style InitiateCancellation fill:#9deddd
    style LookupHistory fill:#9deddd
    style SearchLLM fill:#9deddd
```

## Agent Details

### Orchestrator Agent (Tier 1)
- **Role**: Central router and intent analyzer
- **Responsibilities**:
  - Analyze user intent from natural language
  - Route to appropriate specialized agent
  - Manage agent handoffs
  - Apply input/output guardrails

- **Handoffs**:
  - Reservation Agent
  - Cancellation Agent
  - Search Agent

### Reservation Agent (Tier 2)
- **Role**: Booking workflow manager
- **Tools**:
  - `find_restaurant`: Look up restaurant information
  - `initiate_reservation_call`: Trigger voice call to make reservation
- **Output**: Structured reservation confirmation

### Cancellation Agent (Tier 2)
- **Role**: Cancellation workflow manager
- **Tools**:
  - `lookup_reservation_from_history`: Search CallManager for completed reservation calls
  - `initiate_cancellation_call`: Trigger voice call to cancel reservation
- **Key Feature**: Uses CallManager to find reservations from completed calls (not session history)

### Search Agent (Tier 2)
- **Role**: Restaurant discovery
- **Tools**:
  - `search_restaurants_llm`: Generate restaurant recommendations using LLM
- **Output**: List of recommended restaurants with ratings

### ReservationVoiceAgent (RealtimeAgent)
- **Role**: Conduct real-time voice conversation for making reservations
- **Type**: `RealtimeAgent` (OpenAI Realtime API)
- **Created by**: `initiate_reservation_call` tool
- **Responsibilities**:
  - Natural voice conversation with restaurant staff
  - Request reservation with details (date, time, party size, name)
  - Handle dynamic responses and interruptions
  - Obtain confirmation number
- **Integration**: Twilio Media Streams for bidirectional audio

### CancellationVoiceAgent (RealtimeAgent)
- **Role**: Conduct real-time voice conversation for cancelling reservations
- **Type**: `RealtimeAgent` (OpenAI Realtime API)
- **Created by**: `initiate_cancellation_call` tool
- **Responsibilities**:
  - Natural voice conversation with restaurant staff
  - Cancel reservation using confirmation number or details
  - Handle dynamic responses and interruptions
  - Confirm cancellation
- **Integration**: Twilio Media Streams for bidirectional audio

### Transcript Analysis Agent
- **Role**: Analyze call transcripts to extract confirmed details
- **Used by**: CallManager after voice calls complete
- **Responsibilities**:
  - Extract confirmation numbers from transcripts
  - Identify confirmed date/time if different from requested
  - Update CallManager with accurate reservation details
- **Key Feature**: Uses LLM to understand natural conversation context

## Guardrails

The Orchestrator applies guardrails at both input and output stages:

### Input Guardrails
1. **Input Validation**: Empty input, length limits (max 1000 chars), suspicious patterns
2. **Party Size**: Validates party size between 1-12 people

### Output Guardrails
1. **Output Validation**: Detects sensitive information (API keys, SSN, credit cards)
2. **Output Sanitization**: Masks potential sensitive data

## Session Memory and Call Tracking

```mermaid
graph LR
    User[User Request] --> Orchestrator[Orchestrator]
    Orchestrator --> Session[(SQLiteSession<br/>Conversation History)]
    
    Session --> Messages[User & Assistant<br/>Messages]
    Session --> ToolResults[Tool Call<br/>Results]
    
    VoiceCall[Voice Call] --> CallManager[(CallManager<br/>Call State)]
    CallManager --> CompletedCalls[Completed Calls<br/>with Confirmations]
    
    CancellationAgent[Cancellation Agent] -->|lookup_reservation_from_history| CallManager
    
    style Session fill:#87ceeb
    style CallManager fill:#ffd700
```

**Two separate storage mechanisms:**

1. **SQLiteSession**: Stores conversation history (messages, tool results) for context-aware responses
2. **CallManager**: Stores completed call states with confirmation numbers for reservation lookup

The cancellation agent uses `CallManager` to find reservations, not session history. However, session history enables the agent to understand context like "cancel my reservation" without explicit details.

## Example Flow: "Cancel my reservation"

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator
    participant Cancellation as Cancellation Agent
    participant Lookup as lookup_reservation_from_history
    participant CallManager as CallManager
    participant VoiceCall as initiate_cancellation_call
    participant Restaurant

    User->>Orchestrator: "Cancel my reservation"
    Orchestrator->>Cancellation: Route to cancellation workflow
    Cancellation->>Lookup: Search for reservation
    Lookup->>CallManager: Query completed calls
    CallManager-->>Lookup: Found: Reservation #ABC123 at Luigi's
    Lookup-->>Cancellation: Reservation details
    Cancellation->>VoiceCall: Trigger cancellation call
    VoiceCall->>Restaurant: Voice call via Twilio
    Restaurant-->>VoiceCall: Confirmed cancellation
    VoiceCall-->>Cancellation: Success result
    Cancellation-->>Orchestrator: Cancellation confirmed
    Orchestrator-->>User: "Reservation cancelled successfully"
```

## Multi-Turn Conversation Example

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator
    participant Search as Search Agent
    participant Reservation as Reservation Agent
    participant Cancellation as Cancellation Agent
    participant Session as SQLiteSession
    participant CallManager as CallManager

    Note over User,CallManager: Turn 1: Search
    User->>Orchestrator: "Find Italian restaurants"
    Orchestrator->>Search: Route to search
    Search-->>User: "Bella Italia (4.8⭐), La Taverna (4.6⭐)"
    Search->>Session: Store conversation

    Note over User,CallManager: Turn 2: Book
    User->>Orchestrator: "Book Bella Italia for 2 tomorrow at 8pm"
    Orchestrator->>Reservation: Route to reservation
    Reservation->>CallManager: Create call state
    Reservation-->>User: "Reservation confirmed #XYZ789"
    Reservation->>Session: Store conversation
    Reservation->>CallManager: Mark completed with confirmation

    Note over User,CallManager: Turn 3: Cancel
    User->>Orchestrator: "Actually, cancel that"
    Orchestrator->>Cancellation: Route to cancellation
    Cancellation->>CallManager: Lookup completed calls
    CallManager-->>Cancellation: Found #XYZ789
    Cancellation-->>User: "Reservation cancelled"
```

## Key Features

1. **Intelligent Routing**: Orchestrator analyzes intent and routes to the right agent
2. **Session Memory**: SQLiteSession stores conversation history for context-aware responses
3. **Call Tracking**: CallManager stores completed call states with confirmation numbers for reservation lookup
4. **Tool Composition**: Each agent has specific tools for its domain
5. **Agent Handoffs**: Clean delegation between specialized agents
6. **Guardrails**: Built-in validation and rate limiting
7. **Real-time Voice**: Direct integration with Twilio for actual phone calls

