"""Twilio Media Streams handler for OpenAI Realtime API.

Based on the official OpenAI example:
https://github.com/openai/openai-agents-python/tree/main/examples/realtime/twilio
"""

import asyncio
import base64
import json
import logging
import time
from typing import Any

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
        self.reservation_details: dict = {}  # Will be populated from 'start' event
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

        # Wait for 'start' event to populate reservation_details
        logger.info("⏳ Waiting for 'start' event with reservation details...")
        await self._start_event_received.wait()

        logger.info("=" * 70)
        logger.info("✓ Got reservation details:")
        logger.info(f"  Restaurant: {self.reservation_details.get('restaurant_name')}")
        logger.info(f"  Party size: {self.reservation_details.get('party_size')}")
        logger.info(f"  Date: {self.reservation_details.get('date')}")
        logger.info(f"  Time: {self.reservation_details.get('time')}")
        logger.info("=" * 70)

        # Create the voice agent for this call
        voice_agent_instance = VoiceAgent(self.reservation_details)
        agent = voice_agent_instance.create()

        # Create RealtimeRunner
        runner = RealtimeRunner(agent)

        # Start the session with Twilio-compatible audio format
        self.session = await runner.run(
            model_config={
                "initial_model_settings": {
                    "model_name": config.realtime_model,
                    "voice": config.realtime_voice,
                    "modalities": ["audio", "text"],
                    "input_audio_format": "g711_ulaw",  # Twilio format
                    "output_audio_format": "g711_ulaw",  # Twilio format
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                    },
                    "temperature": 0.8,
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
        except Exception:
            logger.exception("Error in realtime session loop")

    async def _twilio_message_loop(self) -> None:
        """Listen for messages from Twilio WebSocket."""
        try:
            while True:
                message_text = await self.twilio_websocket.receive_text()
                message = json.loads(message_text)
                await self._handle_twilio_message(message)
        except json.JSONDecodeError:
            logger.exception("Failed to parse Twilio message")
        except Exception:
            logger.exception("Error in Twilio message loop")

    async def _handle_realtime_event(self, event: RealtimeSessionEvent) -> None:
        """Handle events from the OpenAI Realtime session."""
        if event.type == "audio":
            # Send audio to Twilio
            base64_audio = base64.b64encode(event.audio.data).decode("utf-8")
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

        elif event.type == "audio_interrupted":
            logger.info("Audio interrupted - clearing Twilio buffer")
            await self.twilio_websocket.send_text(
                json.dumps({"event": "clear", "streamSid": self._stream_sid})
            )
        elif event.type == "transcript":
            logger.info(f"📝 Transcript: {event.text}")
        elif event.type == "audio_end":
            logger.info("Audio stream ended")
        else:
            pass  # Other events handled internally

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

                # Extract custom parameters (reservation details)
                custom_params = start_data.get("customParameters", {})

                # Parse party_size safely
                party_size_str = custom_params.get("party_size", "2")
                try:
                    party_size = int(party_size_str) if party_size_str else 2
                except (ValueError, TypeError):
                    party_size = 2

                self.reservation_details = {
                    "restaurant_name": custom_params.get("restaurant_name")
                    or "Unknown Restaurant",
                    "party_size": party_size,
                    "date": custom_params.get("date") or "today",
                    "time": custom_params.get("time") or "7pm",
                    "customer_name": custom_params.get("customer_name") or "",
                }

                logger.info(
                    f"📞 Stream started - StreamSid: {self._stream_sid}, CallSid: {self._call_sid}"
                )
                logger.info(f"📋 Custom parameters: {custom_params}")

                # Signal that we have reservation details
                self._start_event_received.set()
            elif event == "media":
                await self._handle_media_event(message)
            elif event == "mark":
                await self._handle_mark_event(message)
            elif event == "stop":
                logger.info("🛑 Media stream stopped")
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

                # Add to buffer
                self._audio_buffer.extend(ulaw_bytes)

                # Send buffered audio if we have enough data
                if len(self._audio_buffer) >= self.BUFFER_SIZE_BYTES:
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
