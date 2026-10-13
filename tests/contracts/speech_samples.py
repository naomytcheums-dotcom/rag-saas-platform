"""Real speech for the voice tests: Windows SAPI (the speech engine of the OS) renders text to a WAV file. Nothing recorded, nothing downloaded, no key.
Only available on Windows with pywin32; the tests that need it skip elsewhere (CI on Linux can use espeak-ng the same way)."""

import math
import os
import struct
import wave


def sapi_available() -> bool:
    if os.name != "nt":
        return False
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    return True


def synthesize_wav(text: str, path: str, voice_index: int = 0) -> str:
    """22.05 kHz 16-bit mono PCM WAV of `text` spoken by the installed Windows voice number `voice_index`."""
    import win32com.client

    voice = win32com.client.Dispatch("SAPI.SpVoice")
    voice.Voice = voice.GetVoices().Item(min(voice_index, voice.GetVoices().Count - 1))
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")
    audio_format.Type = 22  # SAFT22kHz16BitMono
    stream.Format = audio_format
    stream.Open(path, 3)  # SSFMCreateForWrite
    voice.AudioOutputStream = stream
    voice.Speak(text)
    stream.Close()
    return path


def write_wav(path: str, samples: list[float], rate: int = 16000) -> str:
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples))
    return path


def silence(seconds: float, rate: int = 16000) -> list[float]:
    return [0.0] * int(seconds * rate)


def room_noise(seconds: float, rate: int = 16000, level: float = 0.004) -> list[float]:
    """Low steady noise (deterministic pseudo-random): what a quiet room sounds like to a microphone."""
    state = 12345
    out = []
    for _ in range(int(seconds * rate)):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        out.append((state / 0x7FFFFFFF - 0.5) * 2 * level)
    return out


def tone(seconds: float, frequency: float = 440.0, rate: int = 16000, level: float = 0.5) -> list[float]:
    return [level * math.sin(2 * math.pi * frequency * i / rate) for i in range(int(seconds * rate))]


def read_wav(path: str) -> tuple[list[float], int]:
    with wave.open(path) as wav:
        rate, frames = wav.getframerate(), wav.readframes(wav.getnframes())
    return [value / 32768.0 for value in struct.unpack(f"<{len(frames) // 2}h", frames)], rate
