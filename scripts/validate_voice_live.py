#!/usr/bin/env python
"""Real validation of 8.2.2 (text-to-speech: ElevenLabs, Google Cloud) and the hosted speech-to-text providers (OpenAI Whisper, Deepgram).

    RUN_LIVE_VENDOR_VALIDATION=1 ELEVENLABS_API_KEY=... GOOGLE_CLOUD_TTS_API_KEY=... OPENAI_API_KEY=... DEEPGRAM_API_KEY=... python scripts/validate_voice_live.py

Synthesizes the sentence "Hello, this is a test." (22 characters) with each TTS vendor that has a key, checks the answer is an MP3, then sends that audio to each
STT vendor that has a key and checks the transcript contains "hello". A wrong key must come back as a VoiceError.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _live_vendor as live  # noqa: E402

TEXT = "Hello, this is a test."


async def main() -> int:
    live.require_opt_in("ElevenLabs, Google Cloud TTS, OpenAI Whisper, Deepgram", "about 22 characters of synthesis and a 2-second transcription per vendor")
    voice = live.product("api.services.voice")
    config = live.product("api.config")
    report = live.Report("voice")
    audio_samples: dict[str, bytes] = {}

    for name, variable, call in (("elevenlabs", "ELEVENLABS_API_KEY", voice.synthesize_with_elevenlabs), ("google_cloud", "GOOGLE_CLOUD_TTS_API_KEY", voice.synthesize_with_google_cloud)):
        if not live.have(variable):
            report.skipped(f"tts:{name}", f"{variable} is not in the process environment")
            continue

        async def tts(name=name, call=call):
            audio = await call(TEXT)
            assert audio[:3] == b"ID3" or audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"), "the answer is not an MP3"
            audio_samples[name] = audio
            return {"mp3_bytes": len(audio)}

        await report.check(f"tts:{name}", tts)

    sample = next(iter(audio_samples.values()), None)
    if sample is None and os.environ.get("LIVE_AUDIO_FILE"):
        sample = open(os.environ["LIVE_AUDIO_FILE"], "rb").read()
    for name, variable in (("whisper", "OPENAI_API_KEY"), ("deepgram", "DEEPGRAM_API_KEY")):
        if not live.have(variable):
            report.skipped(f"stt:{name}", f"{variable} is not in the process environment")
        elif sample is None:
            report.skipped(f"stt:{name}", "no audio: configure a TTS vendor or give LIVE_AUDIO_FILE=<a short spoken clip containing 'hello'>")
        else:
            async def stt(name=name):
                text = await voice.transcribe_audio(sample, filename="sample.mp3", provider=name, language="en")
                assert "hello" in text.lower(), f"transcript was: {text!r}"
                return {"transcript": text[:60]}

            await report.check(f"stt:{name}", stt)

    if "elevenlabs" in audio_samples:
        async def wrong_key():
            config.settings.ELEVENLABS_API_KEY = "invalid-key-for-validation"
            try:
                await voice.synthesize_with_elevenlabs("x")
            except voice.VoiceError as exc:
                assert "401" in str(exc), exc
                return {"mapped": "VoiceError(401)"}
            raise AssertionError("a wrong key was accepted")
        await report.check("tts:elevenlabs-wrong-key", wrong_key)
    return report.finish()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
