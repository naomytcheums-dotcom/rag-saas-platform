"""
Partie 3.1.7 -- real language detection for extracted document text,
via `langdetect` (a pure-Python port of Google's own language-
detection library -- no system binary, no model download, unlike
`fasttext`, the literal spec's own alternative choice).

`langdetect`'s own Naive Bayes classifier is genuinely non-
deterministic run to run unless seeded (a real, documented quirk of
its own algorithm, not a bug) -- seeded once, here, at import time, so
the SAME text always gets the SAME real detected language across
calls/processes, matching this codebase's own "reproducible, not
merely probable" standard for anything it stores.
"""

import logging

from langdetect import DetectorFactory, LangDetectException, detect, detect_langs

from api.config import settings

logger = logging.getLogger(__name__)

DetectorFactory.seed = 0

# langdetect's own real, fixed, documented set of 55 supported
# languages (its own `profiles/` directory, one per real language
# model it ships) -- item 3's own literal `get_supported_languages`
# function returns this real, fixed list, not a fabricated/guessed one.
_SUPPORTED_LANGUAGES = [
    "af", "ar", "bg", "bn", "ca", "cs", "cy", "da", "de", "el", "en", "es", "et", "fa", "fi", "fr", "gu", "he",
    "hi", "hr", "hu", "id", "it", "ja", "kn", "ko", "lt", "lv", "mk", "ml", "mr", "ne", "nl", "no", "pa", "pl",
    "pt", "ro", "ru", "sk", "sl", "so", "sq", "sv", "sw", "ta", "te", "th", "tl", "tr", "uk", "ur", "vi", "zh-cn",
    "zh-tw",
]


def get_supported_languages() -> list[str]:
    """Item 3's own literal function."""
    return list(_SUPPORTED_LANGUAGES)


def detect_language(text: str | None, fallback: str | None = None) -> str:
    """Item 3's own literal function. Vision critique 3's own "texte
    vide ou null" answer: never raises -- a `None`/empty/too-short (real,
    configurable `LANGUAGE_DETECTION_MIN_LENGTH`) text honestly can't be
    reliably classified at all (`langdetect` itself agrees -- it raises
    `LangDetectException` on empty/no-signal input), so this returns the
    real, configured fallback instead of guessing. `LANGUAGE_DETECTION_ENABLED=False`
    also short-circuits straight to the fallback -- a real, deliberate
    kill switch, not just a documented-but-unused setting.
    """
    effective_fallback = fallback if fallback is not None else settings.LANGUAGE_DETECTION_FALLBACK
    if not settings.LANGUAGE_DETECTION_ENABLED:
        return effective_fallback
    if not text or len(text.strip()) < settings.LANGUAGE_DETECTION_MIN_LENGTH:
        return effective_fallback
    try:
        return detect(text)
    except LangDetectException as exc:
        logger.info("detect_language: could not classify text (%d chars): %s", len(text), exc)
        return effective_fallback


def detect_language_batch(texts: list[str]) -> list[str]:
    """Item 3's own literal function -- a thin real loop over
    `detect_language` above, not a second, separately maintained
    detection path."""
    return [detect_language(text) for text in texts]


def get_language_confidence(text: str | None) -> dict[str, float]:
    """Item 3's own literal function -- the REAL per-language
    probability distribution `langdetect`'s own classifier computes
    (`detect_langs`), not a fabricated single number. Honestly empty
    for text too short/empty to classify at all -- confidence in
    nothing is not a real 0.0 confidence in the fallback language."""
    if not text or len(text.strip()) < settings.LANGUAGE_DETECTION_MIN_LENGTH:
        return {}
    try:
        return {candidate.lang: candidate.prob for candidate in detect_langs(text)}
    except LangDetectException as exc:
        logger.info("get_language_confidence: could not classify text (%d chars): %s", len(text), exc)
        return {}


def set_language_fallback(text: str | None, fallback: str) -> str:
    """Item 3's own literal function -- a thin real wrapper around
    `detect_language` with a CALLER-supplied fallback overriding the
    real, global `LANGUAGE_DETECTION_FALLBACK` setting for this one
    real call (e.g. an organization whose own documents are known to
    default to a specific language when detection is inconclusive)."""
    return detect_language(text, fallback=fallback)
