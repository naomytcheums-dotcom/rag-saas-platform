"""
Phase 08 (optional): a lightweight voice channel for the dashboard --
speech-to-text input and text-to-speech output, both via the browser's
own Web Speech API rather than a telephony stack (Twilio/SIP). That
trade-off is deliberate: it's a real voice interaction for a demo, at a
fraction of the setup cost of a call-routing platform.

Two independently useful pieces:

- prepare_text_for_speech / speak_html -- pure functions, fully tested
  without a browser (see tests/test_voice.py).
- voice_input() -- a Streamlit "static" custom component (a bare HTML/JS
  file, no build step) that wraps SpeechRecognition. This half is NOT
  unit-testable the way the rest of this project is: it needs a real
  browser with microphone access, which this environment doesn't have.
  Same category of gap as the untested Docker build in Phase 06 --
  code-complete, structurally reasonable, not exercised end-to-end.
"""

import json
import re
from pathlib import Path

import streamlit.components.v1 as components

VOICE_INPUT_DIR = Path(__file__).resolve().parent / "components" / "voice_input"

_voice_input_component = components.declare_component("nova_voice_input", path=str(VOICE_INPUT_DIR))

CODE_FENCE_PATTERN = re.compile(r"```[a-zA-Z0-9]*\n?")
INLINE_CODE_PATTERN = re.compile(r"`([^`]*)`")
CITATION_PATTERN = re.compile(r"\[\d+\]")
BOLD_ITALIC_PATTERN = re.compile(r"[*_]{1,3}")
WHITESPACE_PATTERN = re.compile(r"\s+")


def prepare_text_for_speech(text):
    """Strip markup a speech synthesizer would otherwise read aloud
    literally, so "the answer uses `HTTPException` [1]" doesn't come out
    as "backtick H T T P Exception backtick bracket one bracket"."""
    if not text:
        return ""
    stripped = CODE_FENCE_PATTERN.sub("", text)
    stripped = INLINE_CODE_PATTERN.sub(r"\1", stripped)
    stripped = CITATION_PATTERN.sub("", stripped)
    stripped = BOLD_ITALIC_PATTERN.sub("", stripped)
    stripped = WHITESPACE_PATTERN.sub(" ", stripped)
    return stripped.strip()


def speak_html(text, rate=1.0):
    """A `components.v1.html`-ready snippet that speaks `text` aloud via
    the browser's speechSynthesis API. `text` is LLM-generated content --
    the same untrusted-input assumption src/injection_tests.py makes
    about the agent's answers -- so a literal "</script>" substring in
    it must not be able to close this tag early and run as page HTML."""
    spoken = prepare_text_for_speech(text)
    payload = json.dumps(spoken).replace("</script>", "<\\/script>")
    return f"""<script>
if ('speechSynthesis' in window) {{
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance({payload});
  utterance.rate = {rate};
  window.speechSynthesis.speak(utterance);
}}
</script>"""


def voice_input(key=None):
    """Renders the mic button. Returns the transcribed question as a
    string once the browser recognizes speech, or None otherwise. The
    same transcript is returned on every rerun until the user speaks
    again -- callers must dedupe against the last value they consumed
    (see dashboard/app.py) or a voice question re-submits itself on
    every unrelated interaction."""
    return _voice_input_component(key=key, default=None)
