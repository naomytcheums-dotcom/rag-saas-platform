"""E2E finding 2026-10-12: faster-whisper + PyAV 19 raised TypeError on every input; PCM WAV is decoded with the standard library."""

import io
import wave

import numpy as np

from api.services.voice import _decode_pcm_wav


def _wav(rate: int, channels: int = 1, seconds: float = 0.5, width: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
        tone = (np.sin(2 * np.pi * 440 * t) * 0.5 * (2 ** (8 * width - 1) - 1)).astype({1: np.int8, 2: np.int16, 4: np.int32}[width])
        w.writeframes(np.repeat(tone, channels).tobytes() if channels > 1 else tone.tobytes())
    return buf.getvalue()


def test_a_16k_mono_wav_becomes_float_samples_in_range():
    samples = _decode_pcm_wav(_wav(16000))
    assert samples.dtype == np.float32 and len(samples) == 8000 and abs(samples).max() <= 1.0 and abs(samples).max() > 0.4


def test_other_sample_rates_and_stereo_are_resampled_to_16k_mono():
    assert len(_decode_pcm_wav(_wav(44100, channels=2))) == 8000


def test_non_wav_bytes_are_left_to_the_other_decoder():
    assert _decode_pcm_wav(b"ID3\x03\x00 mp3 header") is None
    assert _decode_pcm_wav(b"RIFF....WAVEgarbage") is None
