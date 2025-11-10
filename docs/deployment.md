# AI Concierge Deployment Guide

This guide covers local development setup with Twilio Media Streams and OpenAI Realtime API for making actual phone calls to restaurants.

## Overview

The AI Concierge uses a **two-process architecture** for real-time voice calls:

1. **CLI Process**: User interface that sends reservation requests
2. **Server Process**: FastAPI WebSocket server that handles Twilio Media Streams

```
User → CLI → Orchestrator → Reservation Agent → Voice Agent (triggers call)
                                                       ↓
                                      Server receives Twilio webhook
                                                       ↓
                                           WebSocket connection
                                                       ↓
                                      RealtimeAgent ↔ Restaurant
```

## Prerequisites

- Python 3.13+
- OpenAI API key
- Twilio account with phone number
- ngrok (for local development) or public server

## Installation

### 1. Clone and Install Dependencies

```bash
cd ai-concierge
uv sync --extra dev
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# OpenAI (REQUIRED)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Twilio (Required for real calls)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+15555551234

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
PUBLIC_DOMAIN=  # Will be set after ngrok setup

# Voice Configuration
REALTIME_VOICE=alloy  # Options: alloy, echo, fable, onyx, nova, shimmer

# Demo Restaurant
DEMO_RESTAURANT_NAME=Demo Restaurant
DEMO_RESTAURANT_PHONE=+1234567890

# Logging
LOG_LEVEL=INFO
```

## Local Development with ngrok

For local development, you need to expose your WebSocket server to the internet so Twilio can connect to it. ngrok provides a secure tunnel.

### 1. Install ngrok

**macOS:**
```bash
brew install ngrok
```

**Linux:**
```bash
# Download from https://ngrok.com/download
sudo snap install ngrok
```

**Windows:**
Download from https://ngrok.com/download

### 2. Create ngrok Account (Free)

1. Sign up at https://dashboard.ngrok.com/signup
2. Get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken
3. Configure ngrok:

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### 3. Start the Development Environment

**Terminal 1 - Start the Server:**

```bash
# Option 1: Use the helper script
bash scripts/start_server.sh

# Option 2: Run directly
python -m concierge.api
```

You should see:
```
INFO: Starting AI Concierge Voice Server on 0.0.0.0:8080
INFO: Public domain: NOT CONFIGURED
INFO: Application startup complete.
```

**Terminal 2 - Start ngrok:**

```bash
ngrok http 8080
```

You should see output like:
```
ngrok

Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.x.x
Region                        United States (us)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123.ngrok.io -> http://localhost:8080

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

**Copy the HTTPS URL** (e.g., `abc123.ngrok.io` - WITHOUT the `https://` prefix).

**Terminal 3 - Update Your .env:**

Add the ngrok domain to your `.env`:

```bash
PUBLIC_DOMAIN=abc123.ngrok.io
```

**Restart the server** (Terminal 1) so it picks up the new configuration.

### 4. Test the Server

```bash
# Health check
curl http://localhost:8080/health

# Expected response:
{"status":"healthy","service":"ai-concierge-voice"}
```

### 5. Run the CLI

**Terminal 4 - Start the CLI:**

```bash
python -m concierge
```

Try a reservation:
```
Your request: Book a table at Demo Restaurant for 4 people tomorrow at 7pm
```

## How It Works

### Call Flow

1. **User sends request** via CLI
2. **Orchestrator** routes to Reservation Agent
3. **Reservation Agent** parses details and calls `initiate_reservation_call` tool
4. **Voice Agent** creates a call in CallManager and initiates Twilio call
5. **Twilio** receives call request and fetches TwiML from server
6. **Server** generates TwiML that routes call to WebSocket endpoint
7. **Twilio** connects to WebSocket at `wss://your-domain.ngrok.io/media-stream`
8. **Server** creates RealtimeAgent and connects to OpenAI Realtime API
9. **Audio streams** bidirectionally:
   - Restaurant audio → Twilio → Server → OpenAI
   - OpenAI → Server → Twilio → Restaurant
10. **RealtimeAgent** conducts conversation and makes reservation
11. **Server** extracts confirmation number from transcript
12. **CLI** polls server for completion and displays result

### Architecture Diagram

```
┌─────────────┐
│     CLI     │
│  (Terminal) │
└──────┬──────┘
       │
       │ 1. Book reservation
       ▼
┌─────────────────┐
│  Orchestrator   │
│     Agent       │
└──────┬──────────┘
       │
       │ 2. Route to reservation
       ▼
┌─────────────────┐
│  Reservation    │
│     Agent       │
└──────┬──────────┘
       │
       │ 3. Parse details, trigger call
       ▼
┌─────────────────┐
│  Voice Agent    │
│ (make_call)     │
└──────┬──────────┘
       │
       │ 4. POST to Twilio API
       ▼
┌─────────────────┐
│  Twilio Cloud   │
└──────┬──────────┘
       │
       │ 5. Fetch TwiML
       ▼
┌─────────────────┐    6. WebSocket     ┌──────────────────┐
│  FastAPI Server │◄──────────────────►│  Twilio Cloud    │
│  (localhost)    │                     │  (calls phone)   │
└──────┬──────────┘                     └────────┬─────────┘
       │                                          │
       │ 7. Audio conversion                      │ 8. Phone call
       │    (mulaw ↔ PCM16)                      │
       ▼                                          ▼
┌─────────────────┐                     ┌──────────────────┐
│  RealtimeAgent  │                     │   Restaurant     │
│  (OpenAI API)   │◄────────────────────│   Phone Staff    │
└─────────────────┘   9. Voice conversation
```

## Testing Without Making Real Calls

### Option 1: Use Simulation Mode

If you don't configure Twilio credentials, the system will simulate calls:

```bash
# Don't set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_PHONE_NUMBER
python -m concierge
```

You'll see:
```
[SIMULATED] Reservation confirmed at Demo Restaurant...
```

### Option 2: Use Twilio Test Credentials

Twilio provides test credentials that don't make real calls or charge your account:

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (test SID)
TWILIO_AUTH_TOKEN=test_token
TWILIO_PHONE_NUMBER=+15005550006  # Twilio's magic test number
```

See: https://www.twilio.com/docs/iam/test-credentials

## Production Deployment

For production, you'll want to deploy the server to a platform with a public URL instead of using ngrok.

### Recommended Platforms

1. **Railway.app** (Easiest)
   - Deploy with one command
   - Free tier available
   - Automatic HTTPS

2. **Fly.io**
   - Free tier available
   - Good for WebSocket apps

3. **Google Cloud Run / AWS Lambda**
   - For serverless deployment
   - Note: WebSocket support varies

### Railway Deployment Example

1. Install Railway CLI:
```bash
npm install -g @railway/cli
```

2. Create `railway.toml`:
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python -m concierge.api"
```

3. Deploy:
```bash
railway login
railway init
railway up
```

4. Set environment variables in Railway dashboard

5. Get your public URL (e.g., `your-app.railway.app`)

6. Update `.env`:
```bash
PUBLIC_DOMAIN=your-app.railway.app
```

## Monitoring and Debugging

### Server Endpoints

- `GET /health` - Health check
- `GET /metrics` - Server metrics
- `GET /calls` - List all calls
- `GET /calls/{call_id}/status` - Get call status
- `POST /twiml?call_id={id}` - Generate TwiML (called by Twilio)
- `WebSocket /media-stream?call_id={id}` - Media stream handler

### View ngrok Requests

ngrok provides a web interface to inspect requests:

```
http://127.0.0.1:4040
```

This shows all HTTP requests and WebSocket connections to your server.

### View Server Logs

The server logs all events:

```bash
# Set DEBUG level for verbose logging
LOG_LEVEL=DEBUG python -m concierge.api
```

### Common Issues

#### 1. "PUBLIC_DOMAIN not configured"

**Problem:** Server doesn't know its public URL.

**Solution:** Set `PUBLIC_DOMAIN` in `.env` to your ngrok domain (without `https://`).

#### 2. "Twilio not configured"

**Problem:** Twilio credentials not set.

**Solution:** Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER` to `.env`.

#### 3. WebSocket connection fails

**Problem:** Twilio can't connect to your WebSocket.

**Solutions:**
- Verify ngrok is running
- Check `PUBLIC_DOMAIN` is correct
- Ensure server is running on port 8080
- Check firewall settings

#### 4. "Call timed out"

**Problem:** Call took longer than 180 seconds.

**Solution:** This is normal for long calls. The timeout is configured in `voice_agent.py`.

#### 5. No confirmation number extracted

**Problem:** Restaurant staff gave confirmation verbally but wasn't extracted.

**Solution:** 
- Check server logs for transcript
- Improve regex patterns in `call_manager.py`
- Restaurant may not have provided confirmation number

## Architecture Notes

### Why Two Processes?

The CLI and server are separate because:
- **CLI**: Synchronous, user-facing interface
- **Server**: Asynchronous, handles WebSocket connections
- **Separation**: Allows server to run independently for webhooks

### Call State Management

Calls are tracked in memory using `CallManager`. For production, consider:
- Redis for distributed systems
- PostgreSQL for persistence
- Proper session management

### Audio Conversion

The server converts between:
- **Twilio**: 8kHz mulaw (G.711)
- **OpenAI**: 24kHz PCM16

This is handled by `audio_converter.py` using numpy and scipy.

## Security Considerations

1. **Never commit `.env`** - It contains secrets
2. **Use HTTPS** - Twilio requires secure webhooks in production
3. **Validate webhooks** - Verify requests come from Twilio
4. **Rate limiting** - Prevent abuse of your endpoints
5. **Secure credentials** - Use environment variables or secret managers

## Next Steps

1. ✅ Configure `.env` with your credentials
2. ✅ Start server and ngrok
3. ✅ Test with a real phone call
4. 🚀 Deploy to production platform
5. 📊 Add monitoring and analytics
6. 🔒 Implement security best practices

## Support

For issues or questions:
- Check server logs (`LOG_LEVEL=DEBUG`)
- Review ngrok requests (http://127.0.0.1:4040)
- Verify Twilio console for call logs
- Check OpenAI API usage

## Resources

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [OpenAI Realtime API](https://openai.github.io/openai-agents-python/realtime/guide/)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/twiml/stream)
- [ngrok Documentation](https://ngrok.com/docs)

