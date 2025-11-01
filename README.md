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

- **Multi-Agent Architecture**: Modular design with specialized agents for different tasks
- **Natural Language Processing**: Parse reservation requests from conversational input
- **Voice Integration**: Real phone calls using Twilio and OpenAI Realtime API
- **Guardrails**: Input and output validation for security and compliance
- **Flexible Configuration**: Works with or without Twilio (simulates calls if not configured)

## Architecture

```
┌─────────────┐
│  CLI Input  │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  Triage Agent       │  ← Parses request, validates input
│  (Orchestrator)     │    Looks up restaurant
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Voice Agent        │  ← Makes phone call via Twilio
│  (Realtime)         │    Conducts reservation conversation
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Result Display     │  ← Formatted confirmation
└─────────────────────┘
```

### Components

- **Triage Agent**: Orchestrates workflow, parses requests, validates input
- **Voice Agent**: Makes phone calls using OpenAI Realtime API + Twilio
- **Restaurant Service**: Mock service that returns demo restaurant data
- **Guardrails**: Input/output validation for security
- **CLI**: Terminal-based user interface

## Setup

### Prerequisites

- Python 3.13+
- OpenAI API key
- (Optional) Twilio account with phone number

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
# Copy the template
cp ENV_TEMPLATE.txt .env

# Edit .env and add your credentials
# At minimum, set OPENAI_API_KEY
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

### Starting the Application

```bash
python -m concierge
```

### Example Interactions

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
│   │   ├── triage_agent.py
│   │   └── voice_agent.py
│   ├── services/          # External service integrations
│   │   ├── restaurant_service.py
│   │   └── twilio_service.py
│   ├── guardrails/        # Input/output validation
│   │   ├── input_validator.py
│   │   └── output_validator.py
│   ├── models/            # Data models
│   │   └── reservation.py
│   ├── config.py          # Configuration management
│   └── cli.py             # CLI interface
├── tests/                 # Test suite
├── main.py               # Entry point
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
2. **Simplified Voice Integration**: Basic Twilio integration; full Realtime API WebSocket streaming not yet implemented
3. **No WhatsApp Integration**: Uses CLI instead (planned for future)
4. **Limited Error Handling**: Basic error handling for demo purposes
5. **No Persistence**: Results are not saved to a database

## Future Enhancements

- [ ] Full WebSocket integration for real-time audio streaming
- [ ] WhatsApp Business API integration
- [ ] Real restaurant database/API integration
- [ ] Multi-language support
- [ ] Conversation history and persistence
- [ ] Advanced monitoring with Langfuse/Datadog
- [ ] News bot and other specialized agents
- [ ] Visualization dashboard

## Resources

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)
- [Twilio Voice](https://www.twilio.com/docs/voice)
- [Twilio + OpenAI Example](https://github.com/openai/openai-agents-python/tree/main/examples/realtime/twilio)

## License

MIT

