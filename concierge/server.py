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
from contextlib import asynccontextmanager, suppress

import uvicorn
from agents.realtime import RealtimeRunner
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, Query
from fastapi.responses import JSONResponse

from concierge.agents.voice_agent import VoiceAgent
from concierge.config import get_config
from concierge.services.audio_converter import (
    decode_twilio_audio,
    encode_openai_audio,
)
from concierge.services.call_manager import get_call_manager, CallState

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager."""
    config = get_config()
    logger.info(
        f"Starting AI Concierge Voice Server on {config.server_host}:{config.server_port}"
    )
    logger.info(f"Public domain: {config.public_domain or 'NOT CONFIGURED'}")
    yield
    logger.info("Shutting down AI Concierge Voice Server")


app = FastAPI(
    title="AI Concierge Voice Server",
    description="WebSocket server for Twilio Media Streams and OpenAI Realtime API",
    version="0.1.0",
    lifespan=lifespan,
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
    return {"status": "healthy", "service": "ai-concierge-voice"}


@app.post("/twiml")
async def generate_twiml(call_id: str = Query(..., description="Unique call ID")):
    """Generate TwiML to route Twilio call to Media Stream WebSocket.

    Args:
        call_id: Unique identifier for this call

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

    # Use wss:// for secure WebSocket connection
    websocket_url = f"wss://{config.public_domain}/media-stream?call_id={call_id}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}" />
    </Connect>
</Response>"""

    logger.info(f"Generated TwiML for call {call_id}")
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


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket, call_id: str = Query(...)):
    """Handle Twilio Media Stream WebSocket connection.

    This endpoint:
    1. Accepts WebSocket connection from Twilio
    2. Gets reservation details for this call
    3. Creates RealtimeAgent configured for the reservation
    4. Creates RealtimeRunner to manage the agent session
    5. Bridges audio bidirectionally between Twilio and OpenAI

    Args:
        websocket: WebSocket connection from Twilio
        call_id: Unique identifier for this call
    """
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for call {call_id}")

    call_manager = get_call_manager()
    call_state = call_manager.get_call(call_id)

    if not call_state:
        logger.error(f"Call {call_id} not found in call manager")
        await websocket.close(code=1008, reason="Call not found")
        return

    # Update status to in_progress
    call_manager.update_status(call_id, "in_progress")

    try:
        # Create RealtimeAgent for this call
        voice_agent_instance = VoiceAgent(call_state.reservation_details)
        voice_agent = voice_agent_instance.create()
        logger.info(f"Created RealtimeAgent for call {call_id}")

        # Get configuration
        config = get_config()

        # Create RealtimeRunner with proper configuration
        # Reference: https://openai.github.io/openai-agents-python/ref/realtime/runner/
        runner = RealtimeRunner(
            starting_agent=voice_agent,
            config={
                "model_settings": {
                    "model_name": config.realtime_model,
                    "voice": config.realtime_voice,
                    "modalities": ["audio", "text"],
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                    },
                    "temperature": 0.8,
                }
            },
        )
        logger.info(
            f"Created RealtimeRunner for call {call_id} with voice: {config.realtime_voice}"
        )

        # Bridge audio streams between Twilio and OpenAI
        await bridge_audio_streams(websocket, runner, call_state, call_manager)

        # Call completed successfully
        call_manager.update_status(call_id, "completed")
        logger.info(f"Call {call_id} completed successfully")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_id}")
        call_manager.update_status(call_id, "completed")

    except Exception as e:
        logger.exception(f"Error in media stream for call {call_id}")
        call_manager.set_error(call_id, str(e))
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
