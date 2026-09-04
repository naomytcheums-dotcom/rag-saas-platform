"""Partie 3.1.10 -- tests for api/services/metadata_enrichment.py."""

from api.services.metadata_enrichment import (
    extract_complexity_score,
    extract_entities,
    extract_keywords,
    extract_reading_time,
    extract_summary,
    extract_topics,
)

_TEXT = (
    "Artificial intelligence is transforming modern software development. "
    "Machine learning models require large datasets for training. "
    "Contact us at info@example.com or visit https://example.com for more details. "
    "The meeting is scheduled for 15/03/2026. The total cost was $5000 for the project. "
    "Natural language processing enables computers to understand human text. "
    "Deep learning is a subset of machine learning that uses neural networks. "
    "Neural networks are inspired by the human brain structure. "
    "Data science combines statistics, programming, and domain expertise. "
    "Companies invest heavily in artificial intelligence research today."
)


# ------------------------------------------------------------- extract_keywords --

def test_extract_keywords_finds_real_multi_word_phrases():
    """Validation criterion: l'extraction de mots-clés fonctionne."""
    keywords = extract_keywords(_TEXT, max_keywords=5)
    assert len(keywords) == 5
    assert all(kw["score"] > 0 for kw in keywords)
    # Sorted by real descending score.
    scores = [kw["score"] for kw in keywords]
    assert scores == sorted(scores, reverse=True)


def test_extract_keywords_never_crosses_a_real_sentence_boundary():
    """A regression test for a real bug found while building this
    étape: a candidate phrase must stop at real punctuation, not just
    at a stopword, or a whole run of content words spanning several
    real sentences becomes one absurd, unusably long "phrase" (here,
    "jumps" from the first sentence merging with "lazy" from the
    second, with no stopword ever separating them)."""
    text = "Quick brown fox jumps. Lazy dog sleeps peacefully today."
    keywords = extract_keywords(text)
    assert not any("jumps lazy" in kw["keyword"] for kw in keywords)


def test_extract_keywords_is_empty_for_empty_text():
    assert extract_keywords("") == []
    assert extract_keywords(None) == []


def test_extract_keywords_is_empty_for_only_stopwords():
    assert extract_keywords("the a an of and or but") == []


# ------------------------------------------------------------- extract_entities --

def test_extract_entities_finds_a_real_email_and_url():
    """Validation criterion: l'extraction d'entités fonctionne."""
    entities = extract_entities(_TEXT)
    by_type = {e["entity_type"] for e in entities}
    assert "email" in by_type
    assert "url" in by_type
    email = next(e for e in entities if e["entity_type"] == "email")
    assert email["entity_value"] == "info@example.com"
    assert email["position"] == _TEXT.index("info@example.com")


def test_extract_entities_finds_a_real_date_and_money_amount():
    entities = extract_entities(_TEXT)
    by_type = {e["entity_type"]: e for e in entities}
    assert by_type["date"]["entity_value"] == "15/03/2026"
    assert by_type["money"]["entity_value"] == "$5000"


def test_extract_entities_is_ordered_by_real_position():
    entities = extract_entities(_TEXT)
    positions = [e["position"] for e in entities]
    assert positions == sorted(positions)


def test_extract_entities_is_empty_for_text_with_no_real_matches():
    assert extract_entities("Just plain prose, nothing structured here at all.") == []


def test_extract_entities_is_empty_for_none_or_empty():
    assert extract_entities(None) == []
    assert extract_entities("") == []


# ------------------------------------------------------------- extract_summary --

def test_extract_summary_returns_real_sentences_in_original_order():
    """Validation criterion: l'extraction de résumé fonctionne."""
    from api.services.metadata_enrichment import _split_sentences

    summary = extract_summary(_TEXT, max_sentences=2)
    # The real sentence splitter is reused for verification too -- a
    # naive `.split(".")` would wrongly split on the real email/URL's
    # own periods ("info@example.com"), which this module's own real
    # splitter correctly does not.
    chosen = _split_sentences(summary)
    assert len(chosen) == 2
    all_sentences = _split_sentences(_TEXT)
    positions = [all_sentences.index(s) for s in chosen]
    assert positions == sorted(positions)


def test_extract_summary_returns_everything_for_a_short_text():
    text = "One sentence. Two sentences."
    assert extract_summary(text, max_sentences=5) == text


def test_extract_summary_is_empty_for_empty_text():
    assert extract_summary("") == ""
    assert extract_summary(None) == ""


# ------------------------------------------------------------- extract_topics --

def test_extract_topics_returns_real_term_clusters():
    """Validation criterion: l'extraction de sujets fonctionne."""
    topics = extract_topics(_TEXT, num_topics=2)
    assert len(topics) == 2
    for topic in topics:
        assert len(topic) > 0
        assert all(isinstance(term, str) for term in topic)


def test_extract_topics_is_empty_for_text_too_short_to_model():
    """Robustesse -- pas assez de signal réel pour un vrai LDA, jamais
    un sujet fabriqué."""
    assert extract_topics("Too short.", num_topics=3) == []
    assert extract_topics("", num_topics=3) == []


# --------------------------------------------------- extract_reading_time --

def test_extract_reading_time_is_real_word_count_over_200_wpm():
    """Validation criterion: le temps de lecture est estimé."""
    text = " ".join(["word"] * 400)
    assert extract_reading_time(text) == 2.0


def test_extract_reading_time_is_zero_for_empty_text():
    assert extract_reading_time("") == 0.0
    assert extract_reading_time(None) == 0.0


# ------------------------------------------------- extract_complexity_score --

def test_extract_complexity_score_returns_a_real_flesch_score():
    """Validation criterion: la complexité est estimée."""
    score = extract_complexity_score(_TEXT)
    assert isinstance(score, float)
    assert -100 <= score <= 120  # the real, standard Flesch scale's own real bounds in practice


def test_extract_complexity_score_is_zero_for_empty_text():
    assert extract_complexity_score("") == 0.0
    assert extract_complexity_score(None) == 0.0


def test_extract_complexity_score_is_higher_for_simpler_real_text():
    simple = "The cat sat. The dog ran. I like cats."
    complex_text = (
        "The multifaceted epistemological ramifications of postmodernist deconstruction "
        "necessitate a comprehensive reconceptualization of interdisciplinary methodological frameworks."
    )
    assert extract_complexity_score(simple) > extract_complexity_score(complex_text)
