# AI Concierge - Restaurant Reservation System

A multi-agent AI system for automated restaurant reservations using OpenAI Agents SDK and Twilio Voice.

## Overview

AI Concierge is an MVP demonstration of a multi-agent system that:
- Accepts natural language reservation requests via CLI
- Parses and validates user input with guardrails
- Looks up restaurant information
- Makes real voice calls to restaurants using Twilio + OpenAI Realtime API
- Books reservations through natural conversation
- Returns structured results

## Features

- **Multi-Agent Architecture**: 3 specialized agents (Reservation, Cancellation, Search)
- **Session Memory**: SQLiteSession remembers conversation across turns
- **Natural Language Processing**: Parse reservation requests from conversational input
- **Voice Integration**: Real phone calls using Twilio and OpenAI Realtime API
- **LLM-Powered Search**: Generate restaurant recommendations dynamically
- **Guardrails**: Rate limiting, input/output validation for security
- **Flexible Configuration**: Works with or without Twilio (simulates calls if not configured)

## Architecture

The system uses a **3-tier agent architecture** with a separate WebSocket server for real-time voice:

```
┌─────────────┐
│  CLI Input  │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ Orchestrator Agent  │  ← Routes requests to specialized agents
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Reservation Agent   │  ← Parses details, validates, triggers call
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│   Voice Agent       │  ← Creates call, initiates Twilio
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐     ┌─────────────────────┐
│  FastAPI Server     │────▶│  Twilio Media       │
│  (WebSocket)        │     │  Streams            │
└──────┬──────────────┘     └──────┬──────────────┘
       │                            │
       ▼                            ▼
┌─────────────────────┐     ┌─────────────────────┐
│  RealtimeAgent      │────▶│   Restaurant        │
│  (OpenAI)           │     │   Phone Call        │
└─────────────────────┘     └─────────────────────┘
```

### Components

#### Agents (OpenAI Agents SDK)
- **Orchestrator Agent**: Routes requests to 3 specialized agents based on intent
- **Reservation Agent**: Parses reservation details and manages the booking workflow
- **Cancellation Agent**: Looks up reservations in session history and cancels them (NEW!)
- **Search Agent**: Uses LLM to generate restaurant recommendations (NEW!)
- **Voice Agents (RealtimeAgent)**: Conducts natural voice conversations in real-time

#### Services
- **FastAPI Server**: WebSocket server for Twilio Media Streams integration
- **CallManager**: Tracks call state, transcripts, and confirmation numbers
- **AudioConverter**: Converts between Twilio (mulaw 8kHz) and OpenAI (PCM16 24kHz)
- **Restaurant Service**: Mock service that returns demo restaurant data
- **Twilio Service**: Initiates calls and manages Twilio integration

#### Infrastructure
- **Session Memory**: SQLiteSession for automatic conversation history (NEW!)
- **Guardrails**: Rate limiting (5/hour, 20/day), input/output validation using SDK guardrails
- **CLI**: Terminal-based user interface with session support
- **WebSocket Bridge**: Bidirectional audio streaming between Twilio and OpenAI

## Setup

### Prerequisites

- Python 3.13+
- OpenAI API key
- (Optional) Twilio account with phone number for real calls
- (Optional) ngrok for local development with Twilio webhooks

### Installation

1. Clone the repository:
```bash
cd ai-concierge
```

2. Install dependencies:
```bash
uv sync --extra dev
```

3. Configure environment variables:
```bash
# Create .env file with your credentials
cat > .env << EOF
# Required
OPENAI_API_KEY=sk-your-api-key-here

# Optional - for real calls
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+1xxxxx

# Optional - for WebSocket server
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
PUBLIC_DOMAIN=  # Your ngrok domain (set after starting ngrok)

# Voice configuration
REALTIME_VOICE=alloy

# Demo configuration
DEMO_RESTAURANT_NAME=Demo Restaurant
DEMO_RESTAURANT_PHONE=+1234567890
LOG_LEVEL=INFO
EOF
```

### Environment Variables

**Required:**
- `OPENAI_API_KEY`: Your OpenAI API key

**Optional (for real calls):**
- `TWILIO_ACCOUNT_SID`: Twilio account SID
- `TWILIO_AUTH_TOKEN`: Twilio authentication token
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number

**Demo Configuration:**
- `DEMO_RESTAURANT_PHONE`: Phone number for demo restaurant (default: +1234567890)
- `DEMO_RESTAURANT_NAME`: Name of demo restaurant
- `LOG_LEVEL`: Logging level (default: INFO)

## Usage

### Quick Start (Simulation Mode)

For testing without Twilio, just run the CLI:

```bash
python -m concierge
```

This will simulate calls without making real phone calls.

### Full Setup (Real Calls)

For actual phone calls, you need to run both the server and CLI:

**Terminal 1 - Start the WebSocket Server:**
```bash
python -m concierge.server
# Or use the helper script:
bash scripts/start_server.sh
```

**Terminal 2 - Start ngrok (for local development):**
```bash
ngrok http 8080
```

Copy the ngrok domain (e.g., `abc123.ngrok.io`) and add it to your `.env`:
```bash
PUBLIC_DOMAIN=abc123.ngrok.io
```

Restart the server to pick up the new configuration.

**Terminal 3 - Run the CLI:**
```bash
python -m concierge
```

See [docs/deployment.md](docs/deployment.md) for detailed setup instructions.

### Example Interactions

#### Making a Reservation
```
Your request: Book a table at Luigi's for 4 people tomorrow at 7pm
→ Orchestrator routes to Reservation Agent
→ Voice call made to restaurant
→ Confirmation #ABC123 received
```

#### Searching for Restaurants (NEW!)
```
Your request: Find the best Italian restaurant in Konstanz
→ Orchestrator routes to Search Agent
→ LLM generates 3-5 realistic options with ratings
→ User can then book one of them
```

#### Cancelling with Session Memory (NEW!)
```
Your request: Cancel my reservation
→ Orchestrator routes to Cancellation Agent
→ Agent searches session history for recent bookings
→ Finds confirmation #ABC123 automatically
→ Voice call made to cancel reservation
→ Success!
```

#### Multi-Turn Conversation (NEW!)
```
Turn 1: Find me highly rated Chinese restaurants
Turn 2: Book Dragon Palace for 3 people Friday at 7pm
Turn 3: Actually, cancel that
→ All works seamlessly thanks to session memory!
```

#### Classic Format
```
Your request: Book a table at Demo Restaurant for 4 people tomorrow at 7pm

I understood your request as:
  Restaurant: Demo Restaurant
  Date: tomorrow
  Time: 7pm
  Party size: 4 people

Proceed with this reservation? (yes/no): yes

Initiating call to restaurant...

============================================================
RESERVATION RESULT
============================================================

Status: ✓ CONFIRMED

Restaurant: Demo Restaurant
Phone: +1234567890

Date: tomorrow
Time: 7pm
Party size: 4 people

Confirmation #: DEMO-12345678

Reservation confirmed at Demo Restaurant for 4 people on tomorrow at 7pm

Call duration: 2.5 seconds

============================================================
```

### Example Requests

- `"Book a table at Mario's Pizza for 2 people Friday at 6:30 PM"`
- `"Reserve 6 seats at The Steakhouse next Tuesday at 8pm under John Smith"`
- `"Table for 4 at Demo Restaurant tomorrow at 7pm, we need a high chair"`

## Running Tests

```bash
pytest
```

Run with coverage:
```bash
pytest --cov=concierge
```

## Development

### Running the WebSocket Server

For real-time voice calls, you need to run the WebSocket server:

```bash
# Start the server
python -m concierge.server

# Or use the helper script
bash scripts/start_server.sh
```

The server provides these endpoints:
- `GET /health` - Health check
- `GET /metrics` - Server metrics
- `GET /calls` - List all calls
- `GET /calls/{call_id}/status` - Get call status
- `POST /twiml?call_id={id}` - Generate TwiML for Twilio
- `WebSocket /media-stream?call_id={id}` - Media stream handler

See [docs/deployment.md](docs/deployment.md) for detailed setup with ngrok.

### Agent Visualization

Visualize your agent architecture:

```bash
# Install visualization dependencies
pip install "openai-agents[viz]"
```

```python
from agents.extensions.visualization import draw_graph
from concierge.agents.orchestrator_agent import create_orchestrator_agent
from concierge.agents.reservation_agent import create_reservation_agent

reservation_agent = create_reservation_agent()
orchestrator = create_orchestrator_agent(reservation_agent)

# Generate and display graph
draw_graph(orchestrator)

# Or save to file
draw_graph(orchestrator, filename="agent_architecture").view()
```

This generates a visual graph showing agents (yellow), tools (green), and handoffs (arrows).

See [Agent Visualization guide](https://openai.github.io/openai-agents-python/visualization/) for details.

### Tracing and Monitoring

The SDK includes [built-in tracing](https://openai.github.io/openai-agents-python/tracing/) (enabled by default):

- View traces at [OpenAI Traces dashboard](https://platform.openai.com/traces)
- Automatic tracing of agent runs, tool calls, handoffs, and guardrails
- Add custom traces with `from agents import trace`

To disable tracing:
```bash
export OPENAI_AGENTS_DISABLE_TRACING=1
```

### Code Style

The project follows PEP8 standards with Ruff for linting:

```bash
# Format code
ruff format .

# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Project Structure

```
ai-concierge/
├── concierge/              # Main package
│   ├── agents/            # Agent implementations
│   │   ├── orchestrator_agent.py  # Routes requests
│   │   ├── reservation_agent.py   # Parses details
│   │   ├── voice_agent.py         # Real-time calls
│   │   └── tools.py               # Function tools
│   ├── services/          # External service integrations
│   │   ├── audio_converter.py     # Audio format conversion
│   │   ├── call_manager.py        # Call state tracking
│   │   ├── restaurant_service.py  # Restaurant lookup
│   │   └── twilio_service.py      # Twilio integration
│   ├── guardrails/        # Input/output validation
│   │   ├── input_validator.py
│   │   └── output_validator.py
│   ├── models/            # Data models
│   │   └── reservation.py
│   ├── config.py          # Configuration management
│   ├── cli.py             # CLI interface
│   └── server.py          # FastAPI WebSocket server
├── tests/                 # Test suite
│   ├── test_agents.py
│   ├── test_audio_converter.py
│   ├── test_call_manager.py
│   └── ...
├── scripts/               # Helper scripts
│   └── start_server.sh
├── docs/                  # Documentation
│   ├── deployment.md      # Deployment guide
│   └── ...
├── AGENTS.md             # Agent architecture docs
└── pyproject.toml        # Dependencies and config
```

## How It Works

### 1. Input Processing

The CLI accepts natural language input and passes it to the Triage Agent.

### 2. Request Parsing

The Triage Agent uses OpenAI's LLM to parse the request into structured data:
- Restaurant name
- Date and time
- Party size
- Customer name (optional)
- Special requests (optional)

### 3. Validation

Guardrails validate:
- Input length and content
- Party size constraints
- Phone number format
- Suspicious patterns (XSS, injection attempts)

### 4. Restaurant Lookup

The Restaurant Service returns information (phone number) for the requested restaurant. In MVP, this returns static demo data.

### 5. Voice Call

The Voice Agent:
- Initiates a call via Twilio
- Uses OpenAI Realtime API for natural conversation
- Attempts to book the reservation
- Extracts confirmation details

If Twilio is not configured, the system simulates the call.

### 6. Result Display

The result is formatted and displayed with:
- Confirmation status
- Restaurant details
- Reservation details
- Confirmation number
- Call duration

## MVP Limitations

This is an MVP with the following limitations:

1. **Mock Restaurant Service**: Returns static demo restaurant data
2. **RealtimeAgent Integration**: WebSocket audio bridging partially implemented (POC stage)
3. **In-Memory State**: Call state not persisted to database
4. **Local Development**: Requires ngrok for Twilio webhooks
5. **No WhatsApp Integration**: Uses CLI instead (planned for future)
6. **Limited Error Handling**: Basic error handling for demo purposes

## Future Enhancements

- [ ] Complete RealtimeRunner audio bridge implementation
- [ ] Webhook-based call completion (instead of polling)
- [ ] WhatsApp Business API integration
- [ ] Real restaurant database/API integration (Yelp, Google Places)
- [ ] Redis/PostgreSQL for persistent call state
- [ ] Multi-language support
- [ ] Voicemail detection and handling
- [ ] Call recording and playback
- [ ] Production deployment to Railway/Fly.io
- [ ] Advanced monitoring with Langfuse/Datadog
- [ ] Cancellation and modification agents
- [ ] Visualization dashboard

## Resources

### OpenAI Agents SDK
- [GitHub Repository](https://github.com/openai/openai-agents-python)
- [Documentation](https://openai.github.io/openai-agents-python/)
- [Realtime API Guide](https://openai.github.io/openai-agents-python/realtime/guide/)
- [Voice Examples](https://github.com/openai/openai-agents-python/tree/main/examples/voice)
- [Guardrails](https://openai.github.io/openai-agents-python/guardrails/)

### Twilio
- [Voice API](https://www.twilio.com/docs/voice)
- [Media Streams](https://www.twilio.com/docs/voice/twiml/stream)

### Other
- [FastAPI](https://fastapi.tiangolo.com/)
- [ngrok](https://ngrok.com/docs)

## Documentation

- [AGENTS.md](AGENTS.md) - Detailed agent architecture
- [docs/deployment.md](docs/deployment.md) - Deployment guide with ngrok

## License

MIT

## Input-Guardrail Testcase:

### Party Size

Book a table at Luigi's Pizza for 30 people tomorrow at 7 pm

### Content size to long 

Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Duis autem vel eum iriure dolor in hendrerit in vulputate velit esse molestie consequat, vel illum dolore eu feugiat nulla facilisis at vero eros et accumsan et iusto odio dignissim qui blandit praesent luptatum zzril delenit augue duis dolore te feugait nulla facilisi. Lorem ipsum dolor sit amet, consectetuer adipiscing elit, sed diam nonummy nibh euismod tincidunt ut laoreet dolore magna aliquam erat volutpat.  

### Malicious Conent
<script />
