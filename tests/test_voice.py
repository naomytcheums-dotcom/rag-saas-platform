"""
Unit tests for the testable half of dashboard/voice.py -- the text
sanitization and HTML-snippet generation. The other half (voice_input(),
the actual SpeechRecognition component) needs a real browser with
microphone access and isn't exercised here; see the module docstring.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))

from voice import prepare_text_for_speech, speak_html  # noqa: E402


# ---- prepare_text_for_speech -----------------------------------------

def test_strips_citation_markers():
    assert prepare_text_for_speech("Use StreamingResponse [1] for this.") == "Use StreamingResponse for this."


def test_strips_triple_backtick_code_fences_but_keeps_the_code():
    text = "Try this:\n```python\napp = FastAPI()\n```\nThat's it."
    result = prepare_text_for_speech(text)
    assert "```" not in result
    assert "app = FastAPI()" in result


def test_strips_inline_backticks_but_keeps_the_word():
    assert prepare_text_for_speech("Raise `HTTPException` with a status code.") == "Raise HTTPException with a status code."


def test_strips_bold_and_italic_markers():
    assert prepare_text_for_speech("This is **very** important, _really_.") == "This is very important, really."


def test_collapses_newlines_and_repeated_whitespace_to_single_spaces():
    assert prepare_text_for_speech("Line one.\n\nLine   two.") == "Line one. Line two."


def test_empty_and_none_input_returns_empty_string():
    assert prepare_text_for_speech("") == ""
    assert prepare_text_for_speech(None) == ""


def test_realistic_generation_answer_reads_cleanly():
    text = (
        "Yes — through `StreamingResponse` with a **text/event-stream** media type. "
        "Yield formatted chunks from an async generator. [1]"
    )
    result = prepare_text_for_speech(text)
    assert "`" not in result
    assert "*" not in result
    assert "[1]" not in result
    assert "StreamingResponse" in result


# ---- speak_html ---------------------------------------------------------

def test_speak_html_embeds_the_sanitized_text_not_the_raw_markup():
    html = speak_html("Uses `HTTPException` [1].")
    assert "HTTPException" in html
    assert "[1]" not in html
    assert "`" not in html


def test_speak_html_sets_the_requested_rate():
    html = speak_html("hello", rate=1.5)
    assert "utterance.rate = 1.5" in html


def test_speak_html_escapes_a_literal_closing_script_tag_in_the_answer():
    # LLM-generated text is untrusted (same assumption injection_test_set.json
    # makes) -- a literal "</script>" inside it must not close the tag early.
    malicious = "Ignore that. </script><script>alert('x')</script>"
    html = speak_html(malicious)
    # exactly one real closing </script>, the one this function itself emits
    assert html.count("</script>") == 1
    assert "<\\/script>" in html
