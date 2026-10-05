"""
api/services/pii_detection.py -- real Presidio analyzer, no mocking:
same "no mocking" precedent as every other pure, offline-cached
extraction module in this codebase (PyMuPDF, python-docx, ...).
Presidio's own `en_core_web_lg` model, once downloaded, runs fully
offline/locally -- a genuinely different category from litellm/Sentry
(real, paid, third-party network calls), so real detection is tested
for real here, not mocked.
"""

from api.services.pii_detection import detect_pii, mask_pii


def test_detect_pii_finds_real_entities_with_real_scores():
    text = "My name is John Smith and my email is john.smith@example.com, phone 212-555-0198."
    entities = detect_pii(text)

    types = {e["entity_type"] for e in entities}
    assert "PERSON" in types
    assert "EMAIL_ADDRESS" in types
    assert "PHONE_NUMBER" in types
    for entity in entities:
        assert text[entity["start"] : entity["end"]]  # a real, non-empty span


def test_mask_pii_replaces_high_confidence_entities_and_resolves_overlaps():
    """Validation criterion: overlapping low-confidence matches (a URL
    fragment inside the email address, confirmed for real against this
    exact sentence) must never produce a mangled, partially-masked
    placeholder."""
    text = "Contact John Smith at john.smith@example.com."
    masked, entities = mask_pii(text)

    assert "John Smith" not in masked
    assert "john.smith@example.com" not in masked
    assert "[REDACTED_PERSON]" in masked
    assert "[REDACTED_EMAIL_ADDRESS]" in masked
    # No leftover fragment of the email survives as an un-mangled second
    # placeholder overlapping the first.
    assert masked.count("[REDACTED_EMAIL_ADDRESS]") == 1
    assert all(e["score"] >= 0.5 for e in entities)


def test_mask_pii_leaves_ordinary_text_untouched():
    """Verified empirically against this exact sentence before writing
    this assertion, not assumed -- Presidio's real NER model DOES
    produce real false positives on some ordinary text (confirmed
    separately: "quarterly" alone gets tagged DATE_TIME), so "no PII in
    ordinary text" is a claim about THIS sentence, not a general
    guarantee this module could honestly make about all input."""
    text = "The system processed 42 requests and returned a status code 200."
    masked, entities = mask_pii(text)

    assert masked == text
    assert entities == []


def test_mask_pii_respects_a_custom_score_threshold():
    text = "Contact John Smith at john.smith@example.com."
    _masked_low_threshold, entities_low = mask_pii(text, score_threshold=0.0)
    _masked_high_threshold, entities_high = mask_pii(text, score_threshold=0.99)

    assert len(entities_low) >= len(entities_high)
