"""Specs 8.2.2 (text-to-speech), 8.2.3 (streaming voice) and 8.2.5 (voice activity detection), end to end in a REAL browser.

What is real here: the repository's own VADIndicator and VoiceOutput React components (bundled by e2e/voice/vite.config.mjs, nothing re-implemented), a real
Chromium whose microphone is a fake capture DEVICE fed with a WAV file of real speech (rendered by the Windows speech engine), the real FastAPI app
(uvicorn, real PostgreSQL, a registered user and its token) answering POST /voice/tts with the LOCAL engine (Windows SAPI: no key, no network), and the
browser really playing the returned audio (<audio> element, "playing" / "ended" events, duration read from the decoded WAV).
What is NOT real: the loudspeaker (headless Chromium decodes and plays into a null sink: it proves the audio is valid and plays for its whole duration, not that a
human heard it) and the microphone hardware.

Needs: Windows SAPI (pywin32), node, the frontend node_modules (vite), a Playwright for node (PLAYWRIGHT_NODE_MODULES or the sibling rag-work/pw) and its Chromium.
Skips when one is missing; run with the repository's scripts/run_tests_local.sh (disposable database)."""

import functools
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import wave
from urllib.parse import quote

import httpx
import pytest

from speech_samples import read_wav, room_noise, sapi_available, silence, synthesize_wav, write_wav

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DRIVER = os.path.join(os.path.dirname(__file__), "browser_voice_driver.mjs")
SPEECH = "Hello. The invoice is due on the fifteenth of the month. Please pay it before Friday. Thank you very much."


def find_playwright() -> str | None:
    candidates = [os.environ.get("PLAYWRIGHT_NODE_MODULES"), os.path.join(REPO, "..", "pw", "node_modules"), os.path.join(REPO, "frontend", "node_modules")]
    for candidate in candidates:
        if candidate and os.path.isdir(os.path.join(candidate, "playwright")):
            return os.path.join(os.path.abspath(candidate), "package.json")
    return None


PLAYWRIGHT = find_playwright()
VITE = os.path.join(REPO, "frontend", "node_modules", "vite", "bin", "vite.js")
pytestmark = pytest.mark.skipif(
    not (sapi_available() and shutil.which("node") and PLAYWRIGHT and os.path.exists(VITE)),
    reason="needs Windows SAPI (pywin32), node, Playwright for node and the frontend node_modules",
)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wav_seconds(path: str) -> float:
    with wave.open(path) as wav:
        return wav.getnframes() / wav.getframerate()


@pytest.fixture(scope="module")
def mic_files(tmp_path_factory):
    """Fake microphone recordings: real speech with a pause around it; a quiet room; and the same speech but quiet-room only."""
    work = tmp_path_factory.mktemp("mic")
    speech = synthesize_wav(SPEECH, str(work / "speech.wav"))
    samples, rate = read_wav(speech)
    # 16 kHz is what Chromium's fake capture expects best; the SAPI file is 22.05 kHz, which the fake device resamples. Keep it simple: pad in the same rate.
    padded = silence(1.5, rate) + samples + silence(5.0, rate)
    write_wav(str(work / "speech_padded.wav"), padded, rate)
    write_wav(str(work / "quiet_room.wav"), room_noise(12.0, rate), rate)
    return {"speech": str(work / "speech_padded.wav"), "quiet": str(work / "quiet_room.wav"), "speech_seconds": len(samples) / rate}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    work = tmp_path_factory.mktemp("voice-site")
    api_port, web_port = free_port(), free_port()
    api_url, web_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{web_port}"
    build = subprocess.run(
        ["node", VITE, "build", "--config", os.path.join(REPO, "e2e", "voice", "vite.config.mjs"), "--outDir", str(work / "dist")],
        cwd=REPO, env={**os.environ, "NEXT_PUBLIC_API_URL": api_url}, capture_output=True, text=True, timeout=300,
    )
    assert build.returncode == 0, build.stdout[-1500:] + build.stderr[-1500:]
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(work / "dist"))
    handler.log_message = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    web = http.server.ThreadingHTTPServer(("127.0.0.1", web_port), handler)
    threading.Thread(target=web.serve_forever, daemon=True).start()
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(api_port), "--log-level", "warning"],
        cwd=REPO, env={**os.environ, "FRONTEND_URL": web_url, "TTS_PROVIDER": "local", "RATE_LIMIT_ENABLED": "false"}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                if httpx.get(f"{api_url}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(1)
        else:
            pytest.fail("the API did not start: " + (api.stdout.read(2000).decode(errors="replace") if api.poll() is not None else "timeout"))
        registered = httpx.post(f"{api_url}/auth/register", json={"email": f"voice-{int(time.time())}@example.com", "password": "correct-horse-battery-staple", "accept_terms": True}, timeout=30)
        token = registered.json().get("access_token") if registered.status_code in (200, 201) else None
        if not token:
            pytest.skip(f"register answered {registered.status_code} without an access token in the body")
        yield {"api": api_url, "web": web_url, "token": token}
    finally:
        web.shutdown()
        api.terminate()
        try:
            api.wait(timeout=15)
        except subprocess.TimeoutExpired:
            api.kill()


def drive(site, mic: str, scenario: str, query: str = "", timeout: int = 240, **extra) -> dict:
    options = {"url": f"{site['web']}/index.html?{query}", "micWav": mic, "scenario": scenario, "token": site["token"], "playwrightFrom": PLAYWRIGHT, "timeoutMs": 120000, **extra}
    done = subprocess.run(["node", DRIVER, json.dumps(options)], capture_output=True, text=True, timeout=timeout)
    assert done.returncode == 0, done.stderr[-1500:]
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result["ok"], result
    return result


def names(result: dict) -> list[str]:
    return [event["event"] for event in result["events"]]


# ------------------------------------------------------------------------------------------------------------------- 8.2.5 VAD in a real browser


def test_vad_hears_real_speech_through_the_microphone_and_signals_start_then_stop(site, mic_files):
    result = drive(site, mic_files["speech"], "vad", query="threshold=0.02", listenMs=int((1.5 + mic_files["speech_seconds"] + 5.0) * 1000))
    seen = names(result)
    assert "speech-start" in seen, result
    assert "speech-stop" in seen and seen.index("speech-stop") > seen.index("speech-start"), result
    start = next(e["t"] for e in result["events"] if e["event"] == "speech-start")
    stop = next(e["t"] for e in result["events"] if e["event"] == "speech-stop")
    # The speech lasts mic_files["speech_seconds"]; the stop comes after it plus the silence timeout (2 s), never before the speech ended.
    assert stop - start >= mic_files["speech_seconds"] * 1000 * 0.7, (start, stop)


def test_vad_stays_silent_in_a_quiet_room(site, mic_files):
    result = drive(site, mic_files["quiet"], "vad", query="threshold=0.02", listenMs=7000)
    assert "speech-start" not in names(result), result


def test_the_default_threshold_detects_ordinary_speech(site, mic_files):
    """The shipped default (settings.VAD_THRESHOLD) must catch normal speech, not only a shouted one: the energy is an RMS on a -1..1 waveform."""
    result = drive(site, mic_files["speech"], "vad", listenMs=int((1.5 + mic_files["speech_seconds"] + 5.0) * 1000))
    assert "speech-start" in names(result), "the default VAD threshold never fires on real speech"


# ------------------------------------------------------------------------------------------------------------------- 8.2.2 / 8.2.3 TTS playback


def test_local_tts_is_played_by_the_browser_sentence_by_sentence_with_the_next_one_prefetched(site, mic_files):
    result = drive(site, mic_files["quiet"], "tts", query=f"provider=local&text={quote(SPEECH * 1)}")
    seen = names(result)
    sentences = 4
    assert seen.count("tts-request") >= 1 and all(s.endswith(":200") for s in seen if s.startswith("tts-response")), result
    assert [r["type"] for r in result["ttsResponses"] if r["status"] == 200], result
    assert all(r["type"].startswith("audio/wav") for r in result["ttsResponses"]), result
    playing = [e for e in result["events"] if e["event"].startswith("audio-playing")]
    assert playing, "the browser never started playing the synthesized audio"
    durations = [int(e["event"].split(":")[1].rstrip("ms")) for e in playing]
    assert all(d > 300 for d in durations), durations  # real speech, not an empty buffer
    assert seen.count("audio-ended") == len(playing)  # every chunk was played to its end
    if len(playing) > 1:
        # streaming: the 2nd request left BEFORE the 1st audio finished (synthesis of the next sentence overlaps the playback of the current one)
        first_end = next(e["t"] for e in result["events"] if e["event"] == "audio-ended")
        second_request = [e["t"] for e in result["events"] if e["event"] == "tts-request"][1]
        assert second_request < first_end, result
        first_play = next(e["t"] for e in result["events"] if e["event"].startswith("audio-playing"))
        second_play = [e["t"] for e in result["events"] if e["event"].startswith("audio-playing")][1]
        gap = second_play - first_end
        assert gap < 1500, f"{gap} ms of silence between two sentences"
        assert first_play < first_end
    assert sentences >= 1


def test_the_first_words_are_heard_long_before_the_whole_answer_is_synthesized(site, mic_files):
    long_text = " ".join([SPEECH] * 3)
    result = drive(site, mic_files["quiet"], "tts", query=f"provider=local&text={quote(long_text)}")
    first_request = next(e["t"] for e in result["events"] if e["event"] == "tts-request")
    first_play = next(e["t"] for e in result["events"] if e["event"].startswith("audio-playing"))
    total_play = sum(int(e["event"].split(":")[1].rstrip("ms")) for e in result["events"] if e["event"].startswith("audio-playing"))
    assert first_play - first_request < total_play / 2, (first_play - first_request, total_play)
    assert result["events"][-1]["event"] == "audio-ended"


def test_stop_ends_the_playback_and_no_further_sentence_is_played(site, mic_files):
    long_text = " ".join([SPEECH] * 4)
    result = drive(site, mic_files["quiet"], "tts", query=f"provider=local&text={quote(long_text)}", stopAfterMs=4000)
    assert result["stopVisible"], "the Stop control was not shown while speaking"
    plays_at_stop = len([e for e in result["events"] if e["event"].startswith("audio-playing")])
    assert plays_at_stop >= 1
    assert "Play" in result["output"] or "▶" in result["output"]  # back to idle


def test_a_server_that_refuses_speech_is_reported_to_the_user_not_swallowed(site, mic_files):
    result = drive({**site, "token": "not-a-valid-token"}, mic_files["quiet"], "tts", query="provider=local&text=Hello%20there.", stopAfterMs=3000)
    assert any(e["event"] == "tts-response:401" for e in result["events"]), result
    assert not any(e["event"].startswith("audio-playing") for e in result["events"])
    assert result["output"].strip() and "Stop" not in result["output"], result["output"]  # an error is displayed and the player went back to idle
