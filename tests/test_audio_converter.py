"""Tests for audio format conversion."""

import base64

import numpy as np
import pytest

from concierge.services.audio_converter import (
    decode_twilio_audio,
    encode_openai_audio,
    linear_to_mulaw,
    mulaw_to_linear,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
)


class TestMulawConversion:
    """Test mulaw encoding and decoding."""

    def test_mulaw_to_linear_zero(self):
        """Test mulaw decode of zero value."""
        result = mulaw_to_linear(0xFF)  # Mulaw zero (inverts to 0x00)
        assert isinstance(result, int)
        # Zero case - should be small due to bias
        assert abs(result) < 50

    def test_mulaw_to_linear_positive(self):
        """Test mulaw decode of positive value."""
        # 0xFF inverted is 0x00 (sign bit 0 = positive)
        result = mulaw_to_linear(0xFF)
        assert isinstance(result, int)
        assert result >= 0

    def test_mulaw_to_linear_negative(self):
        """Test mulaw decode of negative value."""
        # 0x7F inverted is 0x80 (sign bit 1 = negative)
        result = mulaw_to_linear(0x7F)
        assert isinstance(result, int)
        assert result <= 0

    def test_linear_to_mulaw_zero(self):
        """Test mulaw encode of zero value."""
        result = linear_to_mulaw(0)
        assert isinstance(result, int)
        assert 0 <= result <= 255

    def test_linear_to_mulaw_positive(self):
        """Test mulaw encode of positive value."""
        result = linear_to_mulaw(16384)
        assert isinstance(result, int)
        assert 0 <= result <= 255

    def test_linear_to_mulaw_negative(self):
        """Test mulaw encode of negative value."""
        result = linear_to_mulaw(-16384)
        assert isinstance(result, int)
        assert 0 <= result <= 255

    def test_mulaw_roundtrip(self):
        """Test that encoding and decoding preserves sign.

        Note: Mulaw is lossy, so we only verify sign preservation,
        not exact value preservation.
        """
        for value in [0, 1000, -1000, 16384, -16384]:
            mulaw = linear_to_mulaw(value)
            decoded = mulaw_to_linear(mulaw)

            # Check sign is preserved (mulaw is lossy, so exact value won't match)
            if value > 0:
                assert decoded > 0, f"Positive value {value} decoded to {decoded}"
            elif value < 0:
                assert decoded < 0, f"Negative value {value} decoded to {decoded}"
            else:
                # Zero case - should be small but may not be exactly 0 due to bias
                assert abs(decoded) < 100, f"Zero value decoded to {decoded}"


class TestPCM16Conversion:
    """Test PCM16 and mulaw conversion."""

    def test_mulaw_to_pcm16_empty(self):
        """Test conversion of empty data."""
        result = mulaw_to_pcm16(b"")
        assert result == b""

    def test_mulaw_to_pcm16_basic(self):
        """Test basic mulaw to PCM16 conversion."""
        # Create simple mulaw data (1 second of data at 8kHz)
        mulaw_data = bytes([0xFF] * 8000)  # Silence

        result = mulaw_to_pcm16(mulaw_data, target_sample_rate=24000)

        # Should have resampled from 8kHz to 24kHz
        # Expected output: 24000 samples * 2 bytes per sample
        assert len(result) == 24000 * 2

    def test_pcm16_to_mulaw_empty(self):
        """Test conversion of empty data."""
        result = pcm16_to_mulaw(b"")
        assert result == b""

    def test_pcm16_to_mulaw_basic(self):
        """Test basic PCM16 to mulaw conversion."""
        # Create simple PCM16 data (1 second at 24kHz)
        pcm16_data = np.zeros(24000, dtype=np.int16).tobytes()

        result = pcm16_to_mulaw(pcm16_data, source_sample_rate=24000)

        # Should have resampled from 24kHz to 8kHz
        # Expected output: 8000 mulaw bytes
        assert len(result) == 8000

    def test_audio_roundtrip(self):
        """Test that converting PCM16 → mulaw → PCM16 works."""
        # Create a simple sine wave in PCM16 (24kHz, 0.1 seconds)
        sample_rate = 24000
        duration = 0.1
        frequency = 440  # A4 note

        t = np.linspace(0, duration, int(sample_rate * duration))
        sine_wave = (np.sin(2 * np.pi * frequency * t) * 16384).astype(np.int16)
        pcm16_data = sine_wave.tobytes()

        # Convert to mulaw
        mulaw_data = pcm16_to_mulaw(pcm16_data, source_sample_rate=24000)

        # Convert back to PCM16
        result = mulaw_to_pcm16(mulaw_data, target_sample_rate=24000)

        # Length should be approximately the same (within resampling tolerance)
        assert abs(len(result) - len(pcm16_data)) < 1000


class TestTwilioIntegration:
    """Test Twilio-specific audio handling."""

    def test_decode_twilio_audio(self):
        """Test decoding base64 mulaw from Twilio."""
        # Create sample mulaw data
        mulaw_data = bytes([0xFF] * 160)  # 20ms of silence at 8kHz

        # Encode to base64 (as Twilio would send it)
        base64_payload = base64.b64encode(mulaw_data).decode("utf-8")

        # Decode
        result = decode_twilio_audio(base64_payload)

        # Should return PCM16 data
        assert len(result) > 0
        assert len(result) % 2 == 0  # PCM16 is 2 bytes per sample

    def test_encode_openai_audio(self):
        """Test encoding PCM16 to base64 mulaw for Twilio."""
        # Create sample PCM16 data (24kHz, 20ms = 480 samples)
        pcm16_data = np.zeros(480, dtype=np.int16).tobytes()

        # Encode for Twilio
        result = encode_openai_audio(pcm16_data)

        # Should return base64 string
        assert isinstance(result, str)
        assert len(result) > 0

        # Should be valid base64
        try:
            decoded = base64.b64decode(result)
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"Invalid base64: {e}")

    def test_decode_invalid_base64(self):
        """Test handling of invalid base64 data."""
        result = decode_twilio_audio("not-valid-base64!!!")

        # Should handle gracefully and return empty
        assert result == b""

    def test_encode_invalid_pcm16(self):
        """Test handling of invalid PCM16 data."""
        # Odd number of bytes (invalid for PCM16)
        result = encode_openai_audio(b"abc")

        # Should handle gracefully
        assert isinstance(result, str)


class TestResample:
    """Test audio resampling."""

    def test_upsample_8khz_to_24khz(self):
        """Test upsampling from 8kHz to 24kHz."""
        # Create 1 second of mulaw silence
        mulaw_data = bytes([0xFF] * 8000)

        result = mulaw_to_pcm16(mulaw_data, target_sample_rate=24000)

        # Should have 3x samples (8kHz → 24kHz)
        # 8000 samples → 24000 samples → 48000 bytes (2 bytes per sample)
        assert len(result) == 24000 * 2

    def test_downsample_24khz_to_8khz(self):
        """Test downsampling from 24kHz to 8kHz."""
        # Create 1 second of PCM16 silence
        pcm16_data = np.zeros(24000, dtype=np.int16).tobytes()

        result = pcm16_to_mulaw(pcm16_data, source_sample_rate=24000)

        # Should have 1/3 samples (24kHz → 8kHz)
        # 24000 samples → 8000 samples → 8000 bytes (1 byte per mulaw sample)
        assert len(result) == 8000

    def test_no_resample_needed(self):
        """Test when source and target sample rates are the same."""
        # 8kHz mulaw, converting to 8kHz PCM16 (no resample)
        mulaw_data = bytes([0xFF] * 8000)

        # Explicitly test with same rate
        result = mulaw_to_pcm16(mulaw_data, target_sample_rate=8000)

        # Should have same number of samples
        # 8000 mulaw samples → 8000 PCM16 samples → 16000 bytes
        assert len(result) == 8000 * 2
