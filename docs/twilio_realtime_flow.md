# Twilio Realtime Voice Call Flow

This document visualizes the complete flow of making a real-time voice call for restaurant reservations using Twilio Media Streams and OpenAI Realtime API.

## Complete Call Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Orchestrator as Orchestrator Agent
    participant ReservationAgent as Reservation Agent
    participant Tool as initiate_reservation_call
    participant CallManager
    participant TwilioService
    participant TwilioCloud as Twilio Cloud
    participant Server as FastAPI Server
    participant TwilioHandler
    participant RealtimeAgent as Realtime Agent (OpenAI)
    participant Restaurant

    User->>CLI: "Book table at Luigi's for 4 tomorrow at 7pm"
    CLI->>Orchestrator: Process request
    Orchestrator->>ReservationAgent: Route to reservation workflow
    
    Note over ReservationAgent: Parse & validate details
    ReservationAgent->>Tool: find_restaurant("Luigi's")
    Tool-->>ReservationAgent: Restaurant details
    
    ReservationAgent->>Tool: initiate_reservation_call(details)
    
    Note over Tool,CallManager: Step 1: Create Call State
    Tool->>CallManager: create_call(reservation_details, call_id)
    CallManager-->>Tool: Call ID: abc-123
    
    Note over Tool,TwilioCloud: Step 2: Initiate Twilio Call
    Tool->>TwilioService: initiate_call(phone, twiml_url, callback_url)
    TwilioService->>TwilioCloud: REST API: Create Call
    TwilioCloud-->>TwilioService: Call SID: CA123456
    
    Note over TwilioCloud,Restaurant: Step 3: Call Restaurant
    TwilioCloud->>Restaurant: Dial phone number
    Restaurant-->>TwilioCloud: Ringing...
    
    Note over TwilioCloud,Server: Step 4: Fetch TwiML Instructions
    TwilioCloud->>Server: GET /twiml?call_id=abc-123
    Server-->>TwilioCloud: TwiML with WebSocket URL
    
    Note over TwilioCloud,TwilioHandler: Step 5: Establish WebSocket
    TwilioCloud->>Server: WebSocket /media-stream
    Server->>TwilioHandler: Accept WebSocket connection
    TwilioHandler->>TwilioHandler: Wait for 'start' event
    
    TwilioCloud->>TwilioHandler: Event: 'start' (with reservation details)
    
    Note over TwilioHandler,RealtimeAgent: Step 6: Initialize Realtime Agent
    TwilioHandler->>CallManager: Get call details (call_id)
    CallManager-->>TwilioHandler: Reservation details
    TwilioHandler->>RealtimeAgent: Create agent with instructions
    TwilioHandler->>RealtimeAgent: Start RealtimeSession
    RealtimeAgent-->>TwilioHandler: Session ready
    
    Note over Restaurant,RealtimeAgent: Step 7: Bidirectional Audio Stream
    Restaurant->>TwilioCloud: "Hello? (Audio)"
    TwilioCloud->>TwilioHandler: Media event (g711_ulaw audio)
    TwilioHandler->>RealtimeAgent: Send audio
    
    RealtimeAgent->>RealtimeAgent: Process & generate response
    RealtimeAgent->>TwilioHandler: Audio response
    TwilioHandler->>TwilioCloud: Media event (g711_ulaw audio)
    TwilioCloud->>Restaurant: "Hi, I'd like to make a reservation..."
    
    Note over RealtimeAgent: Conduct Conversation
    loop Conversation
        Restaurant->>RealtimeAgent: Audio (via Twilio & Handler)
        RealtimeAgent->>Restaurant: Audio response
        RealtimeAgent->>CallManager: Append transcript
    end
    
    Restaurant->>RealtimeAgent: "Confirmed! Your number is ABC123"
    
    Note over TwilioHandler,CallManager: Step 8: Call Completion
    TwilioCloud->>TwilioHandler: Event: 'stop'
    TwilioHandler->>CallManager: update_status(call_id, "completed")
    TwilioHandler->>CallManager: Store transcript
    
    Note over Tool,CLI: Step 9: Poll for Result
    Tool->>CallManager: Poll for completion (every 2s)
    CallManager-->>Tool: Status: completed
    Tool->>CallManager: Get call result
    CallManager-->>Tool: VoiceCallResult (confirmation #, transcript)
    
    Tool-->>ReservationAgent: Call result
    ReservationAgent-->>Orchestrator: Formatted result
    Orchestrator-->>CLI: Reservation confirmed
    CLI-->>User: Display confirmation
```

## Audio Streaming Details

### Audio Format Handling

```mermaid
graph LR
    Restaurant[Restaurant<br/>Audio Input] -->|Analog| TwilioCloud[Twilio Cloud]
    TwilioCloud -->|g711_ulaw<br/>8kHz| WebSocket[WebSocket<br/>Media Stream]
    WebSocket --> TwilioHandler[Twilio Handler]
    TwilioHandler -->|g711_ulaw<br/>8kHz| RealtimeAPI[OpenAI<br/>Realtime API]
    
    RealtimeAPI -->|g711_ulaw<br/>8kHz| TwilioHandler2[Twilio Handler]
    TwilioHandler2 -->|g711_ulaw<br/>8kHz| WebSocket2[WebSocket<br/>Media Stream]
    WebSocket2 -->|g711_ulaw<br/>8kHz| TwilioCloud2[Twilio Cloud]
    TwilioCloud2 -->|Analog| Restaurant2[Restaurant<br/>Audio Output]
    
    style TwilioHandler fill:#87ceeb
    style TwilioHandler2 fill:#87ceeb
    style RealtimeAPI fill:#90ee90
```

**Key Points:**
- Twilio uses **g711_ulaw** audio format at **8kHz** sample rate
- OpenAI Realtime API configured to use **g711_ulaw** (no conversion needed)
- Bidirectional streaming: Full-duplex communication
- Audio buffered in 50ms chunks for optimal performance

### WebSocket Events

```mermaid
sequenceDiagram
    participant Twilio
    participant Handler as Twilio Handler
    participant Realtime as Realtime Session

    Note over Twilio,Handler: Connection Established
    Twilio->>Handler: Event: 'connected'
    
    Note over Twilio,Handler: Stream Started
    Twilio->>Handler: Event: 'start' {streamSid, callSid, customParameters}
    Handler->>Handler: Extract reservation details
    Handler->>Realtime: Initialize RealtimeAgent
    
    Note over Twilio,Realtime: Audio Streaming
    loop During Call
        Twilio->>Handler: Event: 'media' {payload: base64_audio}
        Handler->>Realtime: send_audio(audio_bytes)
        Realtime->>Handler: Event: 'audio' {data: audio_bytes}
        Handler->>Twilio: Event: 'media' {payload: base64_audio}
    end
    
    Note over Twilio,Realtime: Transcription
    Realtime->>Handler: Event: 'transcript' {text, role}
    Handler->>Handler: Store in CallManager
    
    Note over Twilio,Handler: Stream Ended
    Twilio->>Handler: Event: 'stop'
    Handler->>Handler: Mark call completed
```

## Component Responsibilities

### 1. TwilioService
- **Location**: `concierge/services/twilio_service.py`
- **Purpose**: Initiate outbound calls via Twilio REST API
- **Key Methods**:
  - `initiate_call(to_number, twiml_url, status_callback)`: Start call
  - `_validate_phone_number()`: Security check (only demo number allowed)

### 2. TwilioHandler
- **Location**: `concierge/twilio_handler.py`
- **Purpose**: Manage WebSocket connection and audio streaming
- **Key Responsibilities**:
  - Accept WebSocket connection from Twilio
  - Extract reservation details from 'start' event
  - Create and manage RealtimeAgent instance
  - Handle bidirectional audio streaming (Twilio ↔ OpenAI)
  - Track playback for audio synchronization
  - Store transcripts in CallManager

### 3. RealtimeAgent (OpenAI)
- **Location**: `concierge/agents/voice_agent.py` (ReservationVoiceAgent)
- **Purpose**: Conduct natural voice conversation
- **Key Features**:
  - Dynamic instructions with reservation details
  - Voice Activity Detection (VAD) for turn-taking
  - Real-time audio processing
  - Transcript generation
  - Handles interruptions gracefully

### 4. CallManager
- **Location**: `concierge/services/call_manager.py`
- **Purpose**: Track call state and results
- **Key Responsibilities**:
  - Create call entries with unique IDs
  - Store reservation details
  - Track call status (pending, in_progress, completed, error)
  - Append transcript lines
  - Extract confirmation numbers from transcripts
  - Provide call results for polling

### 5. FastAPI Server
- **Location**: `concierge/api.py` (or `concierge/server.py`)
- **Purpose**: HTTP endpoints and WebSocket handler
- **Key Endpoints**:
  - `GET /twiml?call_id={id}`: Generate TwiML instructions
  - `WebSocket /media-stream`: Handle Twilio Media Stream
  - `POST /twilio-status`: Receive call status callbacks
  - `GET /calls/{call_id}/status`: Check call status (for polling)

## TwiML Example

When Twilio fetches instructions from `/twiml`, the server responds with:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://your-domain.ngrok.io/media-stream">
            <Parameter name="call_id" value="abc-123"/>
            <Parameter name="restaurant_name" value="Luigi's"/>
            <Parameter name="party_size" value="4"/>
            <Parameter name="date" value="tomorrow"/>
            <Parameter name="time" value="7pm"/>
            <Parameter name="customer_name" value="John"/>
        </Stream>
    </Connect>
</Response>
```

This instructs Twilio to:
1. Connect audio stream to WebSocket endpoint
2. Pass reservation details as custom parameters

## Realtime Agent Configuration

```python
RealtimeRunner(agent).run(
    model_config={
        "api_key": openai_api_key,
        "initial_model_settings": {
            "input_audio_format": "g711_ulaw",  # Match Twilio
            "output_audio_format": "g711_ulaw", # Match Twilio
            "voice": "alloy",                   # Voice selection
            "turn_detection": {
                "type": "server_vad",           # Server-side VAD
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
            },
        },
        "playback_tracker": playback_tracker,   # Audio sync
    }
)
```

## Error Handling

```mermaid
graph TD
    Start[Call Initiated] --> Check{Twilio<br/>Configured?}
    Check -->|No| SimError[Return: Twilio not configured]
    Check -->|Yes| CheckDomain{PUBLIC_DOMAIN<br/>Set?}
    
    CheckDomain -->|No| DomainError[Return: PUBLIC_DOMAIN required]
    CheckDomain -->|Yes| ValidatePhone{Valid Phone<br/>Number?}
    
    ValidatePhone -->|No| PhoneError[Return: Invalid phone number]
    ValidatePhone -->|Yes| CreateCall[Create Call in CallManager]
    
    CreateCall --> InitTwilio[Initiate Twilio Call]
    InitTwilio --> Poll{Poll Status<br/>180s timeout}
    
    Poll -->|Completed| Extract[Extract Confirmation]
    Poll -->|Timeout| TimeoutError[Return: Call timed out]
    Poll -->|Error| CallError[Return: Call failed]
    
    Extract --> Success[Return: Success with confirmation]
    
    style SimError fill:#ffcccc
    style DomainError fill:#ffcccc
    style PhoneError fill:#ffcccc
    style TimeoutError fill:#ffcccc
    style CallError fill:#ffcccc
    style Success fill:#ccffcc
```

## Deployment Requirements

1. **Twilio Account**:
   - Account SID and Auth Token
   - Phone number with Media Streams capability
   - Webhook URLs must be publicly accessible

2. **Public Domain** (for local development):
   - Use ngrok: `ngrok http 8080`
   - Set `PUBLIC_DOMAIN=abc123.ngrok.io` in `.env`
   - Twilio needs to reach your server for webhooks

3. **OpenAI API**:
   - API key with Realtime API access
   - Model: `gpt-4o-realtime-preview-2024-10-01`

4. **Server Requirements**:
   - FastAPI server running on accessible port
   - WebSocket support enabled
   - Low-latency network connection for real-time audio

## Security Considerations

1. **Phone Number Validation**: Only the demo restaurant number can be called
2. **Rate Limiting**: Guardrails prevent abuse (5/hour, 20/day)
3. **Session Isolation**: Each call has unique ID and isolated state
4. **Transcript Privacy**: Transcripts stored only in memory (not persisted)
5. **API Key Protection**: Never exposed in logs or responses

## Monitoring and Debugging

### Key Metrics to Track
- Call initiation time
- WebSocket connection latency
- Audio streaming quality
- Call duration
- Success/failure rates

### Logging Points
1. `TwilioService.initiate_call()`: Call initiated
2. `TwilioHandler.start()`: WebSocket connected
3. `TwilioHandler._handle_realtime_event()`: Transcripts
4. `CallManager.update_status()`: Status changes
5. `wait_for_call_completion()`: Polling progress

See the [OpenAI Agents SDK Tracing](https://openai.github.io/openai-agents-python/tracing/) for additional monitoring capabilities.

