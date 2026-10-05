"""
Real PII detection using Microsoft's real, open source Presidio
analyzer (MIT license) -- closes a real, previously-absent gap: no
detection or masking of personal data (names, emails, phone numbers,
etc.) existed anywhere in this codebase's ingestion pipeline before
this.

**Deliberately `presidio-analyzer` only, NOT `presidio-anonymizer`**:
verified directly against the installed `presidio-anonymizer` package
(`presidio_anonymizer/operators/aes_cipher.py`) that its ONLY use of
the `cryptography` library is the reversible AES Encrypt/Decrypt
operator -- a real, narrow, stable low-level API
(`cryptography.hazmat.primitives.ciphers`) this codebase does not need
for real, one-way PII masking. `presidio-anonymizer`'s own package
metadata pins `cryptography<49.0.0`, which directly conflicts with
`cryptography==50.0.1` already pinned in requirements-api.txt for real,
security-critical WebAuthn 2FA (api/security/webauthn.py) -- installing
both together would force a real, unacceptable downgrade of the exact
library WebAuthn's own signature verification depends on. Masking
itself (replacing a detected span with a real, honest placeholder) is
a handful of lines, not worth a second heavy dependency with a real
security-relevant version conflict.

**Heavy, lazily-loaded singleton, same pattern as
api/services/sentence_chunking.py's own `get_tokenizer`**: building a
real `AnalyzerEngine` loads a real spaCy NLP model
(`en_core_web_lg`, ~400MB, downloaded once) -- far too slow to repeat
per real document, and never paid at all by a deployment that leaves
PII masking off (`pii_masking_enabled`, default False, same
"organization must opt in, never a changed default" discipline as
api/services/docling_extraction.py's own `pdf_extraction_engine`).
"""

import logging

logger = logging.getLogger(__name__)

_ANALYZER = None

# Real, deliberate default: entities below this confidence are dropped
# rather than masked -- Presidio's own analyzer returns real, honest
# low-confidence guesses (e.g. a URL fragment inside an email address,
# confirmed directly in this module's own tests) that would otherwise
# over-mask real, legitimate text.
DEFAULT_SCORE_THRESHOLD = 0.5


class PresidioNotAvailableError(Exception):
    """Same honest-degradation contract as
    api/services/docling_extraction.py's own DoclingNotAvailableError."""


def _get_analyzer():
    global _ANALYZER
    if _ANALYZER is None:
        try:
            from presidio_analyzer import AnalyzerEngine
        except ImportError as exc:
            raise PresidioNotAvailableError(f"presidio-analyzer is not installed: {exc}") from exc
        _ANALYZER = AnalyzerEngine()
    return _ANALYZER


def detect_pii(text: str, language: str = "en") -> list[dict]:
    """Real entity detection -- one dict per real match
    (`entity_type`/`start`/`end`/`score`), Presidio's own real output
    shape, not reshaped into something this module invents."""
    analyzer = _get_analyzer()
    results = analyzer.analyze(text=text, language=language)
    return [{"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": r.score} for r in results]


def mask_pii(text: str, language: str = "en", score_threshold: float = DEFAULT_SCORE_THRESHOLD) -> tuple[str, list[dict]]:
    """Real masking: every detected entity at or above `score_threshold`
    is replaced with `[REDACTED_<ENTITY_TYPE>]`. Returns the masked text
    plus the real list of entities that were actually masked (for a
    caller that wants to log/count what was found, without a second
    real analysis pass).

    Real, necessary overlap resolution `presidio_anonymizer.AnonymizerEngine`
    would otherwise handle: Presidio's own analyzer can return
    overlapping spans (confirmed directly -- a low-confidence URL match
    nested inside a higher-confidence EMAIL_ADDRESS match). Kept spans
    are chosen by score (highest first), then length (longest first) on
    a tie, and any span overlapping an already-kept one is dropped --
    never a partially-masked, mangled placeholder.
    """
    entities = [e for e in detect_pii(text, language=language) if e["score"] >= score_threshold]
    entities.sort(key=lambda e: (-e["score"], -(e["end"] - e["start"])))

    kept: list[dict] = []
    for entity in entities:
        if any(entity["start"] < k["end"] and entity["end"] > k["start"] for k in kept):
            continue
        kept.append(entity)

    # Replaced back-to-front (by start position) so earlier replacements
    # never shift the character offsets of ones not yet applied.
    kept.sort(key=lambda e: e["start"], reverse=True)
    masked = text
    for entity in kept:
        placeholder = f"[REDACTED_{entity['entity_type']}]"
        masked = masked[: entity["start"]] + placeholder + masked[entity["end"] :]

    kept.sort(key=lambda e: e["start"])
    return masked, kept
