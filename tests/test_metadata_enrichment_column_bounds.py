"""E2E finding 2026-10-13 -- keywords and entities must always fit their storage columns.

A text with a long run of non-stopwords and no punctuation (a word list, a NUL-separated blob, a table header) used to give one keyword "phrase" far over the
VARCHAR(200) column; the INSERT failed at commit time, the Celery task died and the document stayed 'pending' forever. A very long URL did the same to
document_entities.entity_value (VARCHAR(500)). The tests prove the extractors now respect the column sizes and that a storage failure of the enrichment cannot
lose the document.
"""

import uuid
from unittest.mock import patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.models.metadata_enrichment import DocumentKeyword
from api.services.metadata_enrichment import (
    MAX_ENTITY_VALUE_CHARS, MAX_KEYWORD_CHARS, MAX_KEYWORD_WORDS, extract_entities, extract_keywords,
)


def test_keyword_phrases_are_bounded_even_without_punctuation_or_stopwords():
    text = " ".join(["abc", "def"] * 300)  # one 1800-character run of non-stopwords
    keywords = extract_keywords(text)
    assert keywords
    assert all(len(k["keyword"]) <= MAX_KEYWORD_CHARS for k in keywords)
    assert all(len(k["keyword"].split()) <= MAX_KEYWORD_WORDS for k in keywords)


def test_a_single_huge_word_is_not_a_keyword():
    assert extract_keywords("A" * 100_000) == []
    assert [k["keyword"] for k in extract_keywords("kiln " + "B" * 500 + " glaze")] != []


def test_normal_text_still_yields_multi_word_keywords():
    keywords = extract_keywords("Machine learning models require large datasets for training. Machine learning is popular.")
    assert any(" " in k["keyword"] for k in keywords)


def test_over_long_entity_values_are_skipped_not_truncated_into_wrong_values():
    long_url = "https://example.com/" + "a" * 700
    entities = extract_entities(f"see {long_url} and https://example.com/short")
    values = [e["entity_value"] for e in entities if e["entity_type"] == "url"]
    assert values == ["https://example.com/short"]
    assert all(len(e["entity_value"]) <= MAX_ENTITY_VALUE_CHARS for e in entities)


async def test_enrichment_storage_failure_does_not_lose_the_document():
    """The keyword/entity inserts run in a SAVEPOINT: when they fail the chunks of the same transaction and the 'completed' status survive."""
    from api.security import documents as documents_module

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        document = Document(organization_id=uuid.uuid4(), workspace_id=None, name="t.txt", file_key="documents/x/t.txt", file_size=10,
                            file_type="text/plain", status=DocumentStatus.pending.value, created_by=None)
        session.add(document)
        await session.commit()
        text = b"The Quarzo kiln fires at 1180 degrees for nine hours. " * 5

        def boom(_text):
            return [{"keyword": "x" * 5, "score": 1.0}]

        real_flush = session.flush
        calls = {"n": 0}

        async def flush_that_fails_once_for_keywords(*args, **kwargs):
            calls["n"] += 1
            if any(isinstance(o, DocumentKeyword) for o in session.new):
                raise RuntimeError("value too long for type character varying(200)")
            return await real_flush(*args, **kwargs)

        with patch.object(documents_module, "download_document_file", return_value=text), \
                patch.object(documents_module, "extract_keywords", side_effect=boom), \
                patch.object(session, "flush", side_effect=flush_that_fails_once_for_keywords):
            updated = await documents_module.process_document(session, document.id)
        assert calls["n"] >= 1
        assert updated.status == DocumentStatus.completed.value, updated.indexing_error
    await engine.dispose()
