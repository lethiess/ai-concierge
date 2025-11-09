"""FastAPI server for handling Twilio Media Streams and OpenAI Realtime API.

This server:
1. Accepts Twilio call webhooks
2. Generates TwiML to route calls to Media Streams
3. Handles WebSocket connections from Twilio
4. Bridges audio between Twilio and OpenAI Realtime API
5. Manages call state and transcripts
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager, suppress

import uvicorn
from agents import Agent, Runner
from agents.realtime import RealtimeRunner
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from concierge.agents import (
    OrchestratorAgent,
    ReservationAgent,
    format_reservation_result,
)
from concierge.agents.tools import find_restaurant
from concierge.config import get_config
from concierge.guardrails.input_validator import (
    input_validation_guardrail,
    party_size_guardrail,
)
from concierge.guardrails.output_validator import output_validation_guardrail
from concierge.services.audio_converter import (
    decode_twilio_audio,
    encode_openai_audio,
)
from concierge.services.call_manager import get_call_manager, CallState

logger = logging.getLogger(__name__)

# Global agent instances (initialized on startup)
orchestrator_agent: Agent | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager."""
    global orchestrator_agent

    config = get_config()
    logger.info(
        f"Starting AI Concierge Voice Server on {config.server_host}:{config.server_port}"
    )
    logger.info(f"Public domain: {config.public_domain or 'NOT CONFIGURED'}")

    # Ensure OpenAI API key is available to the SDK via environment variable
    if config.openai_api_key and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = config.openai_api_key
        logger.info("✓ OpenAI API key loaded into environment")

    # Initialize agents
    logger.info("Initializing AI agents...")

    # Tier 2: Reservation Agent (handles reservation logic + voice calls)
    reservation_agent_instance = ReservationAgent(find_restaurant)
    reservation_agent = reservation_agent_instance.create()

    # Tier 1: Orchestrator (routes requests)
    orchestrator_instance = OrchestratorAgent(reservation_agent)
    orchestrator_agent = orchestrator_instance.create()

    # Add guardrails to the orchestrator
    orchestrator_agent.guardrails = [
        input_validation_guardrail,
        party_size_guardrail,
        output_validation_guardrail,
    ]

    logger.info("✓ AI agents initialized successfully")
    logger.info(
        "  Architecture: Orchestrator → Reservation Agent → Realtime Voice Call"
    )

    yield

    logger.info("Shutting down AI Concierge Voice Server")


app = FastAPI(
    title="AI Concierge Voice Server",
    description="WebSocket server for Twilio Media Streams and OpenAI Realtime API",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware to allow WebSocket connections from browsers
# This is needed for testing with test_websocket.html and for Twilio webhooks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development/testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with server info."""
    config = get_config()
    return {
        "service": "AI Concierge Voice Server",
        "version": "0.1.0",
        "status": "running",
        "public_domain": config.public_domain,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "ai-concierge-api"}


@app.post("/process-request")
async def process_request(request: Request):
    """Process a reservation request through the agent pipeline.

    This endpoint accepts user input text, runs it through the orchestrator
    and reservation agents, and returns the result.

    Request body:
        {
            "user_input": "Book a table at Demo Restaurant for 4 people tomorrow at 7pm"
        }

    Returns:
        {
            "success": true,
            "message": "Reservation confirmed at Demo Restaurant...",
            "final_output": "...",
            "formatted_result": "..."
        }
    """
    global orchestrator_agent

    if orchestrator_agent is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Agents not initialized yet"},
        )

    try:
        data = await request.json()
        user_input = data.get("user_input")

        if not user_input:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing user_input field"},
            )

        logger.info("=" * 70)
        logger.info(f"📥 Processing request: {user_input}")
        logger.info("=" * 70)

        # Run the orchestrator using the SDK Runner (async version)
        # We use await runner.run() instead of run_sync() because we're already
        # in an async context (FastAPI). run_sync() would try to create a new
        # event loop which conflicts with the existing one.
        runner = Runner()
        result = await runner.run(starting_agent=orchestrator_agent, input=user_input)

        # Extract the final output
        final_output = ""
        if hasattr(result, "final_output"):
            final_output = result.final_output
        else:
            final_output = str(result)

        # Format the result
        formatted_result = format_reservation_result(result)

        logger.info("=" * 70)
        logger.info("✓ Request processed successfully")
        logger.info(f"Final output: {final_output}")
        logger.info("=" * 70)

        return {
            "success": True,
            "message": "Request processed successfully",
            "final_output": final_output,
            "formatted_result": formatted_result,
        }

    except Exception as e:
        logger.exception("Error processing request")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "message": f"Error processing request: {e}",
            },
        )


@app.post("/register-call")
async def register_call(request: Request):
    """Register a call with reservation details before initiating it.

    This allows the CLI (separate process) to register call details
    that the server can later retrieve.
    """
    try:
        data = await request.json()
        call_id = data.get("call_id")
        reservation_details = data.get("reservation_details")

        if not call_id or not reservation_details:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing call_id or reservation_details"},
            )
        call_manager = get_call_manager()
        call_state = call_manager.create_call(
            reservation_details=reservation_details, call_id=call_id
        )

        logger.info(f"✓ Registered call {call_id} with reservation details")
        logger.info(f"  Restaurant: {reservation_details.get('restaurant_name')}")

        return {"status": "registered", "call_id": call_state.call_id}

    except Exception as e:
        logger.exception("Error registering call")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.api_route("/twiml", methods=["GET", "POST"])
async def generate_twiml(
    call_id: str = Query(..., description="Unique call ID"),
    test_mode: bool = Query(False, description="Use simple test TwiML"),
):
    """Generate TwiML to route Twilio call to Media Stream WebSocket.

    Args:
        call_id: Unique identifier for this call
        test_mode: If True, return simple test TwiML without WebSocket

    Returns:
        TwiML XML response
    """
    config = get_config()

    if not config.public_domain:
        logger.error("PUBLIC_DOMAIN not configured - cannot generate TwiML")
        return Response(
            content="Error: Server not configured",
            media_type="text/plain",
            status_code=500,
        )

    # Test mode: Simple TwiML without WebSocket to verify basic functionality
    if test_mode:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Hello, this is a test from AI Concierge. The webhook is working correctly.</Say>
    <Pause length="2"/>
    <Say>If you hear this message, your server is reachable from Twilio.</Say>
</Response>"""
        logger.info(f"Generated TEST TwiML for call {call_id}")
        logger.info(f"TwiML Response:\n{twiml}")
        return Response(content=twiml, media_type="text/xml")

    # Get reservation details from CallManager to pass as custom parameters
    call_manager = get_call_manager()
    call_state = call_manager.get_call(call_id)

    # Prepare custom parameters to send to WebSocket handler
    # These will be available in the 'start' event
    custom_params = {"call_id": call_id}  # Always include call_id
    if call_state:
        reservation_details = call_state.reservation_details
        custom_params.update(
            {
                "restaurant_name": reservation_details.get("restaurant_name", ""),
                "party_size": str(reservation_details.get("party_size", "")),
                "date": reservation_details.get("date", ""),
                "time": reservation_details.get("time", ""),
                "customer_name": reservation_details.get("customer_name", ""),
            }
        )
        logger.info(
            f"Passing reservation details via custom parameters: {custom_params}"
        )

    # Build parameter string for TwiML
    " ".join([f'{k}="{v}"' for k, v in custom_params.items() if v])

    # Use wss:// for secure WebSocket connection
    websocket_url = f"wss://{config.public_domain}/media-stream"

    # TwiML with Stream parameters:
    # - track="inbound_track" is the only valid value for <Connect> verb
    # - Custom parameters are sent in the 'start' event to the WebSocket
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting you to our reservation system.</Say>
    <Connect>
        <Stream url="{websocket_url}" track="inbound_track">
            <Parameter name="call_id" value="{custom_params.get('call_id', '')}" />
            <Parameter name="restaurant_name" value="{custom_params.get('restaurant_name', '')}" />
            <Parameter name="party_size" value="{custom_params.get('party_size', '')}" />
            <Parameter name="date" value="{custom_params.get('date', '')}" />
            <Parameter name="time" value="{custom_params.get('time', '')}" />
            <Parameter name="customer_name" value="{custom_params.get('customer_name', '')}" />
        </Stream>
    </Connect>
</Response>"""

    logger.info("=" * 70)
    logger.info(f"📞 Generated TwiML for call {call_id}")
    logger.info(f"🔗 WebSocket URL: {websocket_url}")
    logger.info(f"📄 TwiML Response:\n{twiml}")
    logger.info("=" * 70)
    return Response(content=twiml, media_type="text/xml")


@app.get("/calls/{call_id}/status")
async def get_call_status(call_id: str):
    """Get status of a specific call.

    Args:
        call_id: Unique identifier for the call

    Returns:
        Call state information
    """
    call_manager = get_call_manager()
    call_state = call_manager.get_call(call_id)

    if not call_state:
        return JSONResponse(
            status_code=404,
            content={"error": f"Call {call_id} not found"},
        )

    duration = None
    if call_state.end_time:
        duration = (call_state.end_time - call_state.start_time).total_seconds()

    return {
        "call_id": call_state.call_id,
        "status": call_state.status,
        "confirmation_number": call_state.confirmation_number,
        "start_time": call_state.start_time.isoformat(),
        "end_time": call_state.end_time.isoformat() if call_state.end_time else None,
        "duration": duration,
        "transcript_lines": len(call_state.transcript),
        "error": call_state.error_message,
    }


@app.get("/calls")
async def list_calls():
    """List all active and recent calls."""
    call_manager = get_call_manager()
    calls = call_manager.get_all_calls()

    return {
        "total": len(calls),
        "calls": [
            {
                "call_id": call.call_id,
                "status": call.status,
                "confirmation_number": call.confirmation_number,
                "start_time": call.start_time.isoformat(),
            }
            for call in calls
        ],
    }


@app.get("/metrics")
async def get_metrics():
    """Get server metrics for monitoring."""
    call_manager = get_call_manager()
    calls = call_manager.get_all_calls()

    status_counts = {}
    for call in calls:
        status_counts[call.status] = status_counts.get(call.status, 0) + 1

    return {
        "total_calls": len(calls),
        "status_counts": status_counts,
        "server": "ai-concierge-voice",
    }


@app.api_route("/twilio-status", methods=["GET", "POST"])
async def twilio_status_callback(request: Request):
    """Handle Twilio status callbacks for debugging.

    This endpoint receives updates about call status from Twilio.
    """
    # Get all data from the request
    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
    else:
        data = dict(request.query_params)

    # Log all received data for debugging
    logger.info("=" * 70)
    logger.info("Twilio status callback received")
    logger.info(f"  Method: {request.method}")
    logger.info(f"  All data: {data}")
    logger.info("=" * 70)

    # Extract key fields
    call_sid = data.get("CallSid")
    call_status = data.get("CallStatus")
    error_code = data.get("ErrorCode")
    error_message = data.get("ErrorMessage")

    if call_sid:
        logger.info(f"📞 Call {call_sid}: Status={call_status}")

    if error_code:
        logger.error(f"❌ Twilio error {error_code}: {error_message}")

    return Response(content="OK", media_type="text/plain")


@app.websocket("/ws-test")
async def test_websocket(websocket: WebSocket):
    """Simple WebSocket endpoint for testing connectivity."""
    try:
        logger.info("🔌 Test WebSocket connection attempt")
        logger.info(f"  Client: {websocket.client}")
        logger.info(f"  Headers: {dict(websocket.headers)}")

        await websocket.accept()
        logger.info("✓ Test WebSocket connected successfully")

        await websocket.send_text("Hello from AI Concierge server!")
        await websocket.close()
        logger.info("✓ Test WebSocket closed")

    except Exception as e:
        logger.error(f"❌ Test WebSocket error: {e}", exc_info=True)


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle Twilio Media Stream WebSocket connection.

    Based on the official OpenAI example:
    https://github.com/openai/openai-agents-python/tree/main/examples/realtime/twilio

    Reservation details are passed via Twilio custom parameters in the 'start' event.
    """
    logger.info("=" * 70)
    logger.info("🔌 Twilio Media Stream WebSocket connection received")
    logger.info(f"  Client: {websocket.client}")
    logger.info("=" * 70)

    try:
        # Import TwilioHandler
        from concierge.twilio_handler import TwilioHandler

        # Create handler - it will extract reservation details from 'start' event
        handler = TwilioHandler(websocket)

        # Start and wait for completion
        await handler.start()
        await handler.wait_until_done()

        logger.info("✓ Call completed")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception:
        logger.exception("Error in media stream handler")
        with suppress(Exception):
            await websocket.close(code=1011, reason="Internal error")


async def bridge_audio_streams(
    twilio_ws: WebSocket,
    runner: RealtimeRunner,
    call_state: CallState,
    call_manager,
):
    """Bridge audio between Twilio WebSocket and RealtimeRunner.

    This function:
    1. Starts a RealtimeSession via runner.run()
    2. Listens for Twilio Media Stream events (start, media, stop)
    3. Converts Twilio audio (mulaw 8kHz) to OpenAI format (PCM16 24kHz)
    4. Sends audio to RealtimeSession
    5. Receives events from RealtimeSession (audio, transcript)
    6. Converts OpenAI audio to Twilio format
    7. Sends audio back to Twilio
    8. Captures transcript for confirmation number extraction

    Args:
        twilio_ws: Twilio WebSocket connection
        runner: RealtimeRunner instance
        call_state: CallState object
        call_manager: CallManager instance

    References:
        - https://openai.github.io/openai-agents-python/ref/realtime/runner/
        - https://openai.github.io/openai-agents-python/ref/realtime/session/
    """
    logger.info(f"Starting audio bridge for call {call_state.call_id}")

    try:
        # Start RealtimeSession
        session = await runner.run()

        async with session:
            logger.info(f"RealtimeSession started for call {call_state.call_id}")

            # Create tasks for bidirectional streaming
            twilio_task = asyncio.create_task(
                handle_twilio_to_realtime(twilio_ws, session, call_state, call_manager)
            )
            realtime_task = asyncio.create_task(
                handle_realtime_to_twilio(twilio_ws, session, call_state, call_manager)
            )

            # Wait for either task to complete (call ends)
            _done, pending = await asyncio.wait(
                [twilio_task, realtime_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

            logger.info(f"Audio bridge completed for call {call_state.call_id}")

    except WebSocketDisconnect:
        logger.info(f"Twilio WebSocket disconnected for call {call_state.call_id}")
    except Exception:
        logger.exception(f"Error in audio bridge for call {call_state.call_id}")


async def handle_twilio_to_realtime(
    twilio_ws: WebSocket,
    session,
    call_state: CallState,
    _call_manager,
):
    """Handle audio from Twilio → RealtimeSession.

    Args:
        twilio_ws: Twilio WebSocket connection
        session: RealtimeSession instance
        call_state: CallState object
        _call_manager: CallManager instance (unused, for future use)
    """
    try:
        # Listen for Twilio events
        async for message in twilio_ws.iter_text():
            try:
                data = json.loads(message)
                event_type = data.get("event")

                if event_type == "start":
                    stream_sid = data["start"]["streamSid"]
                    call_state.call_sid = stream_sid
                    logger.info(f"Twilio media stream started: {stream_sid}")
                    # Trigger the agent to start speaking by sending initial audio (silence)
                    # This ensures the agent begins the conversation
                    logger.info("Stream connected - agent should start speaking")

                elif event_type == "dtmf":
                    # Handle DTMF (keypress) events - important for trial accounts
                    digit = data.get("dtmf", {}).get("digit")
                    logger.info(f"DTMF keypress received: {digit}")
                    # Don't end the call on keypress - continue with the stream

                elif event_type == "media":
                    # Audio data from Twilio (base64 encoded mulaw)
                    payload = data["media"]["payload"]

                    # Convert Twilio audio (mulaw 8kHz) to OpenAI format (PCM16 24kHz)
                    pcm16_audio = decode_twilio_audio(payload)

                    # Send audio to RealtimeSession
                    await session.send_audio(pcm16_audio)

                elif event_type == "stop":
                    logger.info(f"Twilio media stream stopped: {call_state.call_sid}")
                    break

                elif event_type == "mark":
                    # Mark events for synchronization
                    logger.debug(f"Mark event: {data.get('mark', {}).get('name')}")

            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from Twilio")
            except Exception:
                logger.exception("Error processing Twilio event")

    except WebSocketDisconnect:
        logger.info(f"Twilio disconnected for call {call_state.call_id}")
    except Exception:
        logger.exception(
            f"Error in Twilio→Realtime handler for call {call_state.call_id}"
        )


async def handle_realtime_to_twilio(
    twilio_ws: WebSocket,
    session,
    call_state: CallState,
    call_manager,
):
    """Handle events from RealtimeSession → Twilio.

    This function listens for events from the RealtimeSession (audio output,
    transcripts) and forwards them appropriately.

    Args:
        twilio_ws: Twilio WebSocket connection
        session: RealtimeSession instance
        call_state: CallState object
        call_manager: CallManager instance
    """
    try:
        # Listen for events from RealtimeSession
        async for event in session:
            try:
                # Handle audio output events
                if event.type == "audio":
                    # Get audio data from OpenAI (PCM16 24kHz)
                    audio_data = event.audio

                    # Convert to Twilio format (mulaw 8kHz)
                    twilio_audio = encode_openai_audio(audio_data)

                    # Send to Twilio
                    await send_audio_to_twilio(
                        twilio_ws, call_state.call_sid, twilio_audio
                    )

                # Handle transcript events
                elif event.type == "transcript":
                    transcript_text = event.text
                    logger.info(f"Transcript: {transcript_text}")

                    # Append to call transcript for confirmation extraction
                    call_manager.append_transcript(call_state.call_id, transcript_text)

                # Handle response completion
                elif event.type == "response.done":
                    logger.debug(f"Response completed for call {call_state.call_id}")

                # Handle errors
                elif event.type == "error":
                    logger.error(f"RealtimeSession error: {event.error}")
                    call_manager.set_error(call_state.call_id, str(event.error))
                    break

            except Exception:
                logger.exception("Error processing Realtime event")

    except Exception:
        logger.exception(
            f"Error in Realtime→Twilio handler for call {call_state.call_id}"
        )


async def send_audio_to_twilio(
    websocket: WebSocket, stream_sid: str, audio_payload: str
):
    """Send audio from OpenAI back to Twilio.

    Args:
        websocket: Twilio WebSocket connection
        stream_sid: Twilio stream SID
        audio_payload: Base64 encoded mulaw audio
    """
    if not stream_sid:
        logger.warning("Cannot send audio - stream not started")
        return

    message = json.dumps(
        {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": audio_payload,
            },
        }
    )

    try:
        await websocket.send_text(message)
    except Exception:
        logger.exception("Error sending audio to Twilio")


def run_server():
    """Run the FastAPI server using uvicorn.

    This is the main entry point for the server.
    """
    from concierge.config import setup_logging

    # Setup logging
    setup_logging()

    # Get config
    config = get_config()

    # Ensure OpenAI API key is available to the SDK via environment variable
    # The SDK reads directly from os.environ, not from our Config
    import os

    if config.openai_api_key and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = config.openai_api_key
        logger.info("✓ OpenAI API key loaded into environment")

    # Run server
    uvicorn.run(
        "concierge.server:app",
        host=config.server_host,
        port=config.server_port,
        log_level=config.log_level.lower(),
        reload=False,  # Set to True for development
    )


if __name__ == "__main__":
    run_server()
