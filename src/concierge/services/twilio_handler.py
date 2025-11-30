"""Twilio Media Streams handler for OpenAI Realtime API.

Based on the official OpenAI example:
https://github.com/openai/openai-agents-python/tree/main/examples/realtime/twilio
"""

import asyncio
import base64
import json
import logging
import os
import time
from typing import Any
from starlette.websockets import WebSocketDisconnect
from fastapi import WebSocket

from agents.realtime import (
    RealtimePlaybackTracker,
    RealtimeRunner,
    RealtimeSession,
    RealtimeSessionEvent,
)

from concierge.agents.voice_agent import VoiceAgent
from concierge.config import get_config

logger = logging.getLogger(__name__)


class TwilioHandler:
    """Handler for Twilio Media Streams WebSocket connections.

    This handles the bidirectional audio streaming between Twilio and OpenAI Realtime API.
    Each WebSocket connection gets its own handler instance.
    """

    def __init__(self, twilio_websocket: WebSocket):
        """Initialize the Twilio handler.

        Args:
            twilio_websocket: The WebSocket connection from Twilio
        """
        self.twilio_websocket = twilio_websocket
        self.call_id: str | None = None  # Will be populated from 'start' event
        self._message_loop_task: asyncio.Task[None] | None = None
        self.session: RealtimeSession | None = None
        self.playback_tracker = RealtimePlaybackTracker()
        self._start_event_received = asyncio.Event()  # Wait for 'start' event
        self._openai_connected = asyncio.Event()  # Wait for OpenAI connection

        # Audio buffering configuration
        self.CHUNK_LENGTH_S = 0.05  # 50ms chunks
        self.SAMPLE_RATE = 8000  # Twilio uses 8kHz for g711_ulaw
        self.BUFFER_SIZE_BYTES = int(self.SAMPLE_RATE * self.CHUNK_LENGTH_S)

        self._stream_sid: str | None = None
        self._call_sid: str | None = None
        self._audio_buffer: bytearray = bytearray()
        self._last_buffer_send_time = time.time()

        # Mark event tracking for playback
        self._mark_counter = 0
        self._mark_data: dict[str, tuple[str, int, int]] = {}

    async def start(self) -> None:
        """Start the Twilio Media Streams session."""
        config = get_config()

        logger.info("🎯 Starting Twilio Media Streams Handler")

        # Accept the Twilio WebSocket first
        await self.twilio_websocket.accept()
        logger.info("✓ Twilio WebSocket connection accepted")

        # Start message loop to get the 'start' event with reservation details
        self._message_loop_task = asyncio.create_task(self._twilio_message_loop())

        # Wait for 'start' event to populate call_id
        logger.info("⏳ Waiting for 'start' event...")
        await self._start_event_received.wait()

        if not self.call_id:
            logger.error("❌ No call_id received in start event")
            return

        # Get call details from CallManager
        from concierge.services.call_manager import get_call_manager

        call_manager = get_call_manager()
        call_state = call_manager.get_call(self.call_id)

        if not call_state:
            logger.error(f"❌ Call {self.call_id} not found in CallManager")
            return

        reservation_details = call_state.reservation_details
        call_type = reservation_details.get("call_type", "reservation")

        logger.info("=" * 70)
        logger.info("✓ Got call details from CallManager:")
        logger.info(f"  Restaurant: {reservation_details.get('restaurant_name')}")
        logger.info(f"  Call type: {call_type}")
        logger.info("=" * 70)

        # Determine template based on call type
        template_name = (
            "cancellation_voice_agent"
            if call_type == "cancellation"
            else "reservation_voice_agent"
        )

        # Prepare context for the agent
        # We can pass the whole reservation_details dict as context
        # The VoiceAgent will handle adding current_date
        context = reservation_details.copy()

        # Handle special requests formatting if needed (though VoiceAgent can do this too,
        # let's keep it simple here and pass raw data)
        if context.get("special_requests"):
            context["special_requests"] = (
                f"**Special requests:** {context['special_requests']}"
            )

        if call_type == "cancellation":
            logger.info("✅ SELECTING VoiceAgent (cancellation template)")
            voice_agent_instance = VoiceAgent("cancellation_voice_agent", context)
        else:
            logger.info("✅ SELECTING VoiceAgent (reservation template)")
            voice_agent_instance = VoiceAgent("reservation_voice_agent", context)

        agent = voice_agent_instance.create()

        logger.info(
            f"✅ Agent created: {type(agent).__name__} (name: {getattr(agent, 'name', 'N/A')})"
        )

        # Create RealtimeRunner (no config in constructor - just the agent)
        runner = RealtimeRunner(agent)

        # Get API key
        api_key = config.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")

        # Start the session with model_config (following official OpenAI SDK Twilio example)
        self.session = await runner.run(
            model_config={
                "api_key": api_key,
                "initial_model_settings": {
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "voice": config.realtime_voice,
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                    },
                },
                "playback_tracker": self.playback_tracker,
            }
        )

        await self.session.enter()
        logger.info("✓ RealtimeSession started")

        # Signal that OpenAI is connected and ready to receive audio
        self._openai_connected.set()

        # Start async loops for handling Realtime events and buffer flushing
        # (message loop already started earlier to get 'start' event)
        self._realtime_session_task = asyncio.create_task(self._realtime_session_loop())
        self._buffer_flush_task = asyncio.create_task(self._buffer_flush_loop())

        # Trigger the agent to start speaking immediately
        # This is critical for the agent to begin the conversation
        logger.info("🎬 Triggering agent to start speaking")
        await self.session.send_message("start")  # Trigger initial greeting

    async def wait_until_done(self) -> None:
        """Wait until the session is complete."""
        assert self._message_loop_task is not None
        await self._message_loop_task

    async def _realtime_session_loop(self) -> None:
        """Listen for events from the OpenAI Realtime session."""

        assert self.session is not None
        try:
            async for event in self.session:
                await self._handle_realtime_event(event)
        except WebSocketDisconnect:
            # Normal - happens when call ends but agent still has audio to send
            logger.info("Realtime session ended (WebSocket closed)")
        except Exception:
            logger.exception("Error in realtime session loop")

    async def _twilio_message_loop(self) -> None:
        """Listen for messages from Twilio WebSocket."""
        from starlette.websockets import WebSocketDisconnect

        try:
            while True:
                message_text = await self.twilio_websocket.receive_text()
                message = json.loads(message_text)
                await self._handle_twilio_message(message)
        except WebSocketDisconnect:
            # Normal disconnection when call ends
            logger.info("Twilio WebSocket disconnected (call ended)")
        except json.JSONDecodeError:
            logger.exception("Failed to parse Twilio message")
        except Exception:
            logger.exception("Error in Twilio message loop")

    async def _handle_realtime_event(self, event: RealtimeSessionEvent) -> None:
        """Handle events from the OpenAI Realtime session."""
        # Only log important event types
        if event.type in ("transcript", "history_updated", "audio_end"):
            logger.debug(f"Realtime event: {event.type}")

        # Try to extract and log any text content from ANY event for debugging
        if hasattr(event, "text") and event.text:
            logger.info(f"📝 Event text [{event.type}]: {event.text}")
            if self.call_id:
                from concierge.services.call_manager import get_call_manager

                call_manager = get_call_manager()
                call_manager.append_transcript(
                    self.call_id, f"[{event.type}] {event.text}"
                )

        if event.type == "audio":
            # Send audio to Twilio
            try:
                base64_audio = base64.b64encode(event.audio.data).decode("utf-8")
                logger.debug(
                    f"Sending {len(event.audio.data)} bytes of audio to Twilio"
                )
                await self.twilio_websocket.send_text(
                    json.dumps(
                        {
                            "event": "media",
                            "streamSid": self._stream_sid,
                            "media": {"payload": base64_audio},
                        }
                    )
                )

                # Send mark event for playback tracking
                self._mark_counter += 1
                mark_id = str(self._mark_counter)
                self._mark_data[mark_id] = (
                    event.audio.item_id,
                    event.audio.content_index,
                    len(event.audio.data),
                )

                await self.twilio_websocket.send_text(
                    json.dumps(
                        {
                            "event": "mark",
                            "streamSid": self._stream_sid,
                            "mark": {"name": mark_id},
                        }
                    )
                )
            except Exception as e:
                # WebSocket might be closed if call ended
                logger.debug(
                    f"Could not send audio to Twilio (call may have ended): {e}"
                )

        elif event.type == "audio_interrupted":
            logger.info("Audio interrupted - clearing Twilio buffer")
            await self.twilio_websocket.send_text(
                json.dumps({"event": "clear", "streamSid": self._stream_sid})
            )
        elif event.type == "transcript":
            # Log both role and text to understand who said what
            role = getattr(event, "role", "unknown")
            text = event.text
            logger.info(f"📝 Transcript [{role}]: {text}")

            # Add transcript to CallManager
            if self.call_id:
                from concierge.services.call_manager import get_call_manager

                call_manager = get_call_manager()
                # Include role in transcript for better context
                transcript_line = f"[{role}] {text}"
                call_manager.append_transcript(self.call_id, transcript_line)

        elif event.type == "response.done":
            # Capture the assistant's full response text (less verbose)
            if hasattr(event, "response") and hasattr(event.response, "output"):
                for output_item in event.response.output:
                    if hasattr(output_item, "content"):
                        for content in output_item.content:
                            if hasattr(content, "text") and content.text:
                                if self.call_id:
                                    from concierge.services.call_manager import (
                                        get_call_manager,
                                    )

                                    call_manager = get_call_manager()
                                    call_manager.append_transcript(
                                        self.call_id, f"[assistant] {content.text}"
                                    )

        elif event.type == "conversation.item.created":
            # Also capture conversation items as they're created
            if hasattr(event, "item"):
                item = event.item
                if hasattr(item, "role") and hasattr(item, "content"):
                    role = item.role
                    for content in item.content:
                        if hasattr(content, "text") and content.text:
                            if self.call_id and content.text:
                                from concierge.services.call_manager import (
                                    get_call_manager,
                                )

                                call_manager = get_call_manager()
                                call_manager.append_transcript(
                                    self.call_id, f"[{role}] {content.text}"
                                )

        elif event.type == "history_updated":
            # Extract transcripts from conversation history
            logger.info("📚 History updated - extracting transcripts")
            if hasattr(event, "history"):
                for item in event.history:
                    if hasattr(item, "content") and item.content:
                        role = getattr(item, "role", "unknown")
                        for content in item.content:
                            # Extract transcript from different content types
                            transcript_text = None
                            if hasattr(content, "transcript") and content.transcript:
                                transcript_text = content.transcript
                            elif hasattr(content, "text") and content.text:
                                transcript_text = content.text

                            if transcript_text and self.call_id:
                                logger.info(
                                    f"📝 History transcript [{role}]: {transcript_text}"
                                )
                                from concierge.services.call_manager import (
                                    get_call_manager,
                                )

                                call_manager = get_call_manager()
                                call_manager.append_transcript(
                                    self.call_id, f"[{role}] {transcript_text}"
                                )

        elif event.type == "audio_end":
            logger.debug("Audio stream ended")

    async def _handle_twilio_message(self, message: dict[str, Any]) -> None:
        """Handle incoming messages from Twilio Media Stream."""
        try:
            event = message.get("event")

            if event == "connected":
                logger.info("✓ Twilio media stream connected")
            elif event == "start":
                start_data = message.get("start", {})
                self._stream_sid = start_data.get("streamSid")
                self._call_sid = start_data.get("callSid")

                # Extract custom parameters (only call_id needed now)
                custom_params = start_data.get("customParameters", {})
                self.call_id = custom_params.get("call_id")

                logger.info(
                    f"📞 Stream started - CallID: {self.call_id}, StreamSid: {self._stream_sid}, CallSid: {self._call_sid}"
                )

                # Update CallManager status to in_progress
                if self.call_id:
                    from concierge.services.call_manager import get_call_manager

                    call_manager = get_call_manager()
                    await call_manager.update_status(self.call_id, "in_progress")

                # Signal that we have reservation details
                self._start_event_received.set()
            elif event == "media":
                await self._handle_media_event(message)
            elif event == "mark":
                await self._handle_mark_event(message)
            elif event == "stop":
                logger.info("🛑 Media stream stopped")

                # Mark call as completed in CallManager
                if self.call_id:
                    from concierge.services.call_manager import get_call_manager

                    call_manager = get_call_manager()
                    call_state = call_manager.get_call(self.call_id)

                    # Log summary before marking complete
                    if call_state:
                        logger.info("📊 Call Summary:")
                        logger.info(
                            f"  - Transcript lines: {len(call_state.transcript)}"
                        )
                        logger.debug(
                            f"  - Full transcript: {' | '.join(call_state.transcript)}"
                        )
                        logger.info(
                            f"  - Confirmation number: {call_state.confirmation_number}"
                        )

                    await call_manager.update_status(self.call_id, "completed")
                    logger.info(f"✓ Updated call {self.call_id} status to completed")
        except Exception:
            logger.exception("Error handling Twilio message")

    async def _handle_media_event(self, message: dict[str, Any]) -> None:
        """Handle audio data from Twilio - buffer before sending to OpenAI."""
        media = message.get("media", {})
        payload = media.get("payload", "")

        if payload:
            try:
                # Decode base64 audio from Twilio (µ-law format)
                ulaw_bytes = base64.b64decode(payload)
                logger.debug(
                    f"🎤 Received {len(ulaw_bytes)} bytes from Twilio, buffer size: {len(self._audio_buffer)}"
                )

                # Add to buffer
                self._audio_buffer.extend(ulaw_bytes)

                # Send buffered audio if we have enough data
                if len(self._audio_buffer) >= self.BUFFER_SIZE_BYTES:
                    logger.debug(
                        f"📤 Flushing {len(self._audio_buffer)} bytes to OpenAI"
                    )
                    await self._flush_audio_buffer()

            except Exception:
                logger.exception("Error processing audio from Twilio")

    async def _handle_mark_event(self, message: dict[str, Any]) -> None:
        """Handle mark events from Twilio to update playback tracker."""
        try:
            mark_data = message.get("mark", {})
            mark_id = mark_data.get("name", "")

            # Look up stored data for this mark ID
            if mark_id in self._mark_data:
                item_id, item_content_index, byte_count = self._mark_data[mark_id]

                # Convert byte count back to bytes for playback tracker
                audio_bytes = b"\x00" * byte_count

                # Update playback tracker
                self.playback_tracker.on_play_bytes(
                    item_id, item_content_index, audio_bytes
                )

                # Clean up
                del self._mark_data[mark_id]

        except Exception:
            logger.exception("Error handling mark event")

    async def _flush_audio_buffer(self) -> None:
        """Send buffered audio to OpenAI."""
        if not self._audio_buffer or not self.session:
            return

        # Wait for OpenAI to be connected before sending audio
        if not self._openai_connected.is_set():
            return

        try:
            buffer_data = bytes(self._audio_buffer)
            await self.session.send_audio(buffer_data)

            # Clear buffer
            self._audio_buffer.clear()
            self._last_buffer_send_time = time.time()

        except Exception:
            logger.exception("Error sending buffered audio to OpenAI")

    async def _buffer_flush_loop(self) -> None:
        """Periodically flush audio buffer to prevent stale data."""
        try:
            while True:
                await asyncio.sleep(self.CHUNK_LENGTH_S)

                # If buffer has data and it's been too long, flush it
                current_time = time.time()
                if (
                    self._audio_buffer
                    and current_time - self._last_buffer_send_time
                    > self.CHUNK_LENGTH_S * 2
                ):
                    await self._flush_audio_buffer()

        except Exception:
            logger.exception("Error in buffer flush loop")
