# AI Concierge - Restaurant Reservation System

An AI-powered system that makes restaurant reservations through natural voice calls using OpenAI Agents SDK and Twilio. It features a multi-agent architecture with session memory, intelligent routing, and real-time voice conversations.

## Quick Overview

The system uses 3 specialized agents (Reservation, Cancellation, Search) orchestrated by a central router. Users interact via CLI, and the system can make actual phone calls to restaurants using OpenAI's Realtime API and Twilio Media Streams.

## Installation

### Prerequisites

- Python 3.13+
- OpenAI API key
- (Optional) Twilio account for real calls
- (Optional) ngrok for local development with Twilio webhooks

### Setup

1. **Install dependencies:**
```bash
uv sync --extra dev
```

2. **Activate Virtual Environment:**
```bash
source .venv/bin/activate
```

3. **Configure environment:**
```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your OpenAI API key
# For real calls, also add your Twilio credentials
```

**Required:**
- `OPENAI_API_KEY` - Your OpenAI API key

**Optional (for real calls):**
- `TWILIO_ACCOUNT_SID` - Twilio account SID
- `TWILIO_AUTH_TOKEN` - Twilio authentication token
- `TWILIO_PHONE_NUMBER` - Your Twilio phone number
- `PUBLIC_DOMAIN` - Your ngrok domain (see ngrok setup below)

## Running the System

### Simulation Mode (No Twilio Required)

```bash
python -m concierge
```

This will simulate calls without making real phone calls.

### Full Mode (With Real Calls)

For actual phone calls, you need to run both the server and CLI:

**Terminal 1 - Start Server:**
```bash
python -m concierge.api
```

**Terminal 2 - Start ngrok:**
```bash
# Install ngrok if you haven't: https://ngrok.com/download
ngrok http 8080

# or use with custom domain
ngrok http --url=your.ngrok.url.io 8080
```

Copy the ngrok domain (e.g., `abc123.ngrok.io`) and add it to your `.env`:
```bash
PUBLIC_DOMAIN=your.ngrok.url.io
```

Restart the server to pick up the new configuration.

**Terminal 3 - Run CLI:**
```bash
python -m concierge
```

### About ngrok

ngrok creates a secure tunnel to your local server, allowing Twilio to send webhooks to your development machine. 

- **Installation**: Download from [ngrok.com](https://ngrok.com/download) or use `brew install ngrok` on macOS
- **Usage**: Run `ngrok http 8080` to expose your local server on port 8080
- **Free tier**: Provides a random subdomain (changes on restart). For production, use a paid plan with a static domain. **Attention: On free tier there might be issues with the websocket connection**.
- **Security**: ngrok tunnels are HTTPS by default, suitable for Twilio webhooks

## Example Usage

```
Your request: Book a table at Luigi's for 4 people tomorrow at 7pm
→ Parses details, validates, makes voice call, returns confirmation

Your request: Find the best Italian restaurant in Konstanz
→ Generates recommendations using LLM

Your request: Cancel my reservation
→ Looks up booking in session history, cancels via voice call
```

## Development


### Run Tests

```bash
pytest
```

### Code Formatting

```bash
ruff format .
ruff check .
```

## Guardrail Test Cases

Test the input validation guardrails with these examples:

### 1. Party Size Limit (Max 12 people)

```
Book a table at Luigi's Pizza for 30 people tomorrow at 7 pm
```

**Expected:** Request blocked with message about party size limits.

### 2. Input Too Long (Max 1000 characters)

```
Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Duis autem vel eum iriure dolor in hendrerit in vulputate velit esse molestie consequat, vel illum dolore eu feugiat nulla facilisis at vero eros et accumsan et iusto odio dignissim qui blandit praesent luptatum zzril delenit augue duis dolore te feugait nulla facilisi. Lorem ipsum dolor sit amet, consectetuer adipiscing elit, sed diam nonummy nibh euismod tincidunt ut laoreet dolore magna aliquam erat volutpat.
```

**Expected:** Request blocked with message about input length.

### 3. Malicious Content (XSS/Injection Patterns)

```
<script>alert('test')</script>
```

**Expected:** Request blocked with message about suspicious content.

### 4. Valid Request (Should Pass)

```
Book a table at Luigi's Pizza for 4 people tomorrow at 7 pm
```

**Expected:** Request processed successfully.

## Resources

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [OpenAI Realtime API Guide](https://openai.github.io/openai-agents-python/realtime/guide/)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/twiml/stream)
- [ngrok Documentation](https://ngrok.com/docs)

## License

MIT
