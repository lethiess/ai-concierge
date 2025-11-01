"""Audio format conversion for Twilio Media Streams and OpenAI Realtime API.

Handles conversion between:
- Twilio: 8kHz mulaw audio (G.711)
- OpenAI: 24kHz PCM16 audio
"""

import base64
import logging

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)

# G.711 mulaw constants
MULAW_BIAS = 33
MULAW_MAX = 0x1FFF  # Max 13-bit value


def mulaw_to_linear(mulaw_byte: int) -> int:
    """Decode a single mulaw byte to linear PCM value using G.711 standard.

    Args:
        mulaw_byte: Mulaw encoded byte (0-255)

    Returns:
        Linear PCM value (-32768 to 32767)
    """
    # Invert all bits
    mulaw_byte = ~mulaw_byte & 0xFF

    # Extract sign, exponent, and mantissa
    sign = mulaw_byte & 0x80
    exponent = (mulaw_byte >> 4) & 0x07
    mantissa = mulaw_byte & 0x0F

    # Calculate linear value
    # Add implicit leading 1 to mantissa (33 = 0x21 = bias + 1)
    linear = ((mantissa << 1) + 33) << exponent
    linear -= MULAW_BIAS

    # Apply sign
    if sign:
        return -linear
    return linear


def linear_to_mulaw(linear_value: int) -> int:
    """Encode a linear PCM value to mulaw byte using G.711 standard.

    Args:
        linear_value: Linear PCM value (-32768 to 32767)

    Returns:
        Mulaw encoded byte (0-255)
    """
    # Store sign and get absolute value
    sign = 0x80 if linear_value < 0 else 0x00
    linear_value = abs(linear_value)

    # Add bias
    linear_value += MULAW_BIAS

    # Clip to max value
    linear_value = min(linear_value, MULAW_MAX)

    # Find exponent (position of highest set bit)
    exponent = 7
    for i in range(7, -1, -1):
        if linear_value >= (33 << i):
            exponent = i
            break

    # Extract mantissa (4 bits after implicit leading bit)
    mantissa = (linear_value >> (exponent + 1)) & 0x0F

    # Combine sign, exponent, and mantissa
    mulaw_byte = sign | (exponent << 4) | mantissa

    # Invert all bits (G.711 standard)
    return ~mulaw_byte & 0xFF


def mulaw_to_pcm16(mulaw_data: bytes, target_sample_rate: int = 24000) -> bytes:
    """Convert mulaw audio to PCM16 and resample.

    Twilio sends 8kHz mulaw audio. OpenAI Realtime API expects 24kHz PCM16.

    Args:
        mulaw_data: Raw mulaw encoded audio bytes
        target_sample_rate: Target sample rate (default: 24000 Hz for OpenAI)

    Returns:
        PCM16 encoded audio bytes at target sample rate
    """
    if not mulaw_data:
        return b""

    try:
        # Step 1: Decode mulaw to linear PCM
        mulaw_array = np.frombuffer(mulaw_data, dtype=np.uint8)
        linear_samples = np.array(
            [mulaw_to_linear(byte) for byte in mulaw_array], dtype=np.int16
        )

        # Step 2: Resample from 8kHz to target sample rate (24kHz)
        source_sample_rate = 8000
        if target_sample_rate != source_sample_rate:
            # Calculate resampling ratio
            num_samples = int(
                len(linear_samples) * target_sample_rate / source_sample_rate
            )

            # Resample using scipy
            resampled = signal.resample(linear_samples, num_samples)

            # Convert back to int16
            pcm16_samples = np.clip(resampled, -32768, 32767).astype(np.int16)
        else:
            pcm16_samples = linear_samples

        # Step 3: Convert to bytes
        return pcm16_samples.tobytes()

    except Exception:
        logger.exception("Error converting mulaw to PCM16")
        return b""


def pcm16_to_mulaw(pcm_data: bytes, source_sample_rate: int = 24000) -> bytes:
    """Convert PCM16 audio to mulaw and resample.

    OpenAI Realtime API sends 24kHz PCM16. Twilio expects 8kHz mulaw.

    Args:
        pcm_data: Raw PCM16 encoded audio bytes
        source_sample_rate: Source sample rate (default: 24000 Hz from OpenAI)

    Returns:
        Mulaw encoded audio bytes at 8kHz
    """
    if not pcm_data:
        return b""

    try:
        # Step 1: Parse PCM16 data
        pcm16_samples = np.frombuffer(pcm_data, dtype=np.int16)

        # Step 2: Resample from source rate to 8kHz
        target_sample_rate = 8000
        if source_sample_rate != target_sample_rate:
            # Calculate resampling ratio
            num_samples = int(
                len(pcm16_samples) * target_sample_rate / source_sample_rate
            )

            # Resample using scipy
            resampled = signal.resample(pcm16_samples, num_samples)

            # Convert back to int16
            linear_samples = np.clip(resampled, -32768, 32767).astype(np.int16)
        else:
            linear_samples = pcm16_samples

        # Step 3: Encode to mulaw
        mulaw_bytes = np.array(
            [linear_to_mulaw(int(sample)) for sample in linear_samples], dtype=np.uint8
        )

        return mulaw_bytes.tobytes()

    except Exception:
        logger.exception("Error converting PCM16 to mulaw")
        return b""


def decode_twilio_audio(base64_payload: str) -> bytes:
    """Decode base64 mulaw audio from Twilio and convert to PCM16.

    Args:
        base64_payload: Base64 encoded mulaw audio from Twilio

    Returns:
        PCM16 audio bytes at 24kHz
    """
    try:
        mulaw_data = base64.b64decode(base64_payload)
        return mulaw_to_pcm16(mulaw_data)
    except Exception:
        logger.exception("Error decoding Twilio audio")
        return b""


def encode_openai_audio(pcm16_data: bytes) -> str:
    """Encode PCM16 audio to base64 mulaw for Twilio.

    Args:
        pcm16_data: PCM16 audio bytes at 24kHz

    Returns:
        Base64 encoded mulaw audio for Twilio
    """
    try:
        mulaw_data = pcm16_to_mulaw(pcm16_data)
        return base64.b64encode(mulaw_data).decode("utf-8")
    except Exception:
        logger.exception("Error encoding audio for Twilio")
        return ""
