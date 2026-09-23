"""Phase 4, Étape 1 -- proves the real, wired chunking-strategy dispatch:
`process_document` (api/security/documents.py) now genuinely selects
among the 6 real, standalone strategies (Partie 3.2.2-3.2.7) plus the
pre-existing `"fixed"` default, per an organization's own real
`chunking_strategy` setting -- not just that the strategy functions
work in isolation (already covered by their own dedicated test modules
and by tests/test_chunk_config.py's own resolver tests).

Fast SQLite suite, same convention as tests/test_document_status.py:
`download_document_file`/`extract_document_content` are mocked (S3/
per-format parsing are real infrastructure this fast suite never runs),
but `chunk_content`/`generate_embeddings`/the real tokenizer are left
real -- tests/test_semantic_chunking.py already establishes that the
real sentence-transformers model is available to this fast suite
without mocking, so there is no real reason to fake the real chunking
math here too."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization_settings import OrganizationSettings
from api.security.documents import MARKDOWN_CONTENT_TYPE, process_document
from api.services.chunk_config import CHUNKING_STRATEGIES

_MARKDOWN_TEXT = (
    "# Introduction\n\nThis is the real introduction paragraph with a bit of extra filler text.\n\n"
    "## Section A\n\nReal content for section A, with enough words to be a genuine chunk on its own.\n\n"
    "## Section B\n\nReal content for section B, also long enough to be its own genuine real chunk."
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _make_document(session, organization_id, section_metadata=None) -> Document:
    document = Document(
        organization_id=organization_id, workspace_id=None, name="doc.md",
        file_key="documents/x/doc.md", file_size=len(_MARKDOWN_TEXT), file_type=MARKDOWN_CONTENT_TYPE,
        status=DocumentStatus.pending.value, created_by=None,
    )
    session.add(document)
    await session.commit()
    return document


async def _set_org_chunking_strategy(session, organization_id, strategy: str, chunk_size: int | None = None) -> None:
    overrides = {"chunking_strategy": strategy}
    if chunk_size is not None:
        overrides["chunk_size"] = chunk_size
    session.add(OrganizationSettings(organization_id=organization_id, settings=overrides))
    await session.commit()


def _mock_extraction(monkeypatch, text: str = _MARKDOWN_TEXT, section_metadata: dict | None = None):
    monkeypatch.setattr("api.security.documents.download_document_file", lambda file_key: b"fake bytes, never really parsed")
    monkeypatch.setattr(
        "api.security.documents.extract_document_content",
        lambda tmp_path, file_type: {
            "metadata": {}, "sections": [{"text": text, "metadata": section_metadata or {}}], "tables": [], "image_count": 0,
        },
    )


async def _get_chunks(session, document_id) -> list[DocumentChunk]:
    return list((await session.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)
    )).all())


# --------------------------------------- Test 1 -- default strategy unchanged --


async def test_default_strategy_is_fixed_and_behavior_is_unchanged(db_session, monkeypatch):
    """Validation criterion: le comportement par défaut (avant cette
    étape) reste identique -- aucun réglage de chunking_strategy créé,
    donc la stratégie effective reste 'fixed'."""
    org_id = uuid.uuid4()
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    assert len(chunks) >= 1
    assert all(c.metadata_json["chunking_strategy"] == "fixed" for c in chunks)


# --------------------------------------- Test 2 -- an advanced strategy is real and selectable --


async def test_an_advanced_strategy_can_really_be_selected_and_runs(db_session, monkeypatch):
    """Validation criterion: une stratégie avancée réellement existante
    (markdown) peut être sélectionnée et est réellement exécutée --
    prouvé par le nombre de chunks (un par en-tête réel) ET par la
    metadata persistée, pas seulement par un appel de fonction isolé."""
    org_id = uuid.uuid4()
    await _set_org_chunking_strategy(db_session, org_id, "markdown")
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    # 3 real headings (#, ##, ##) in _MARKDOWN_TEXT -> 3 real chunks from chunk_markdown_by_headings.
    assert len(chunks) == 3
    assert all(c.metadata_json["chunking_strategy"] == "markdown" for c in chunks)
    assert chunks[0].content.startswith("# Introduction")
    assert chunks[1].content.startswith("## Section A")
    assert chunks[2].content.startswith("## Section B")


@pytest.mark.parametrize("strategy", [s for s in CHUNKING_STRATEGIES if s not in ("fixed", "markdown")])
async def test_every_other_real_strategy_also_runs_and_completes(db_session, monkeypatch, strategy):
    """Validation criterion: chaque stratégie réellement branchée (pas
    seulement markdown) est réellement exécutable via le vrai pipeline,
    sans faire planter l'ingestion."""
    org_id = uuid.uuid4()
    await _set_org_chunking_strategy(db_session, org_id, strategy)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    assert len(chunks) >= 1
    assert all(c.metadata_json["chunking_strategy"] == strategy for c in chunks)


# --------------------------------------- Test 3 -- configuration is really transmitted --


async def test_chunk_size_configuration_is_really_transmitted_to_the_strategy(db_session, monkeypatch):
    """Validation criterion: les paramètres (ici chunk_size) sont
    réellement transmis à la stratégie choisie -- un chunk_size minuscule
    force la stratégie recursive à produire bien plus de chunks qu'un
    chunk_size par défaut ne l'aurait fait."""
    org_id = uuid.uuid4()
    await _set_org_chunking_strategy(db_session, org_id, "recursive", chunk_size=20)
    long_text = " ".join(f"Real sentence number {i} in a longer real document." for i in range(30))
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch, text=long_text)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    assert len(chunks) > 5  # a real, small chunk_size=20 (characters) must produce many real chunks
    assert all(len(c.content) <= 20 for c in chunks)


# --------------------------------------- Test 4 -- metadata is preserved --


async def test_metadata_is_preserved_through_an_advanced_strategy(db_session, monkeypatch):
    """Validation criterion: les métadonnées nécessaires (document_id,
    organization_id, chunk_index, metadata de section, langue) sont
    conservées, pas seulement le texte du chunk."""
    org_id = uuid.uuid4()
    await _set_org_chunking_strategy(db_session, org_id, "markdown")
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch, section_metadata={"page": 3, "source": "unit-test"})

    await process_document(db_session, document.id)

    chunks = await _get_chunks(db_session, document.id)
    for i, chunk in enumerate(chunks, start=1):
        assert chunk.document_id == document.id
        assert chunk.organization_id == org_id
        assert chunk.chunk_index == i
        assert chunk.metadata_json["page"] == 3
        assert chunk.metadata_json["source"] == "unit-test"
        assert chunk.metadata_json["chunking_strategy"] == "markdown"
        assert "language" in chunk.metadata_json


# --------------------------------------- Test 5 -- full pipeline (chunking -> embedding/indexing) --


async def test_full_pipeline_produces_real_embeddings_with_the_selected_strategy(db_session, monkeypatch):
    """Validation criterion: le chemin complet document -> ingestion ->
    chunking -> embedding/indexing fonctionne avec la stratégie
    sélectionnée -- chaque chunk réel a un vrai vecteur d'embedding, pas
    None."""
    org_id = uuid.uuid4()
    await _set_org_chunking_strategy(db_session, org_id, "paragraph")
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    assert len(chunks) >= 1
    assert all(c.embedding is not None and len(c.embedding) > 0 for c in chunks)


# --------------------------------------- Test 6 -- fallback / robustness --


async def test_an_unknown_strategy_value_in_the_database_falls_back_safely(db_session, monkeypatch):
    """Validation criterion: une valeur de stratégie invalide déjà en
    base (ex. un ancien réglage manuel corrompu) ne casse pas
    l'ingestion silencieusement -- resolve_chunking_strategy la rejette
    explicitement plutôt que de produire un résultat incorrect en
    silence."""
    org_id = uuid.uuid4()
    db_session.add(OrganizationSettings(organization_id=org_id, settings={"chunking_strategy": "not-a-real-strategy"}))
    await db_session.commit()
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.failed.value
    assert "chunking_strategy" in updated.indexing_error


async def test_a_strategy_that_fails_at_runtime_falls_back_to_fixed_for_that_section(db_session, monkeypatch):
    """Validation criterion: une stratégie qui échoue réellement à
    l'exécution (ex. un appel d'embedding qui plante en mode semantic)
    ne fait pas échouer tout le document -- repli réel sur 'fixed' pour
    cette section, l'ingestion se termine normalement."""
    org_id = uuid.uuid4()
    await _set_org_chunking_strategy(db_session, org_id, "semantic")
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    monkeypatch.setattr("api.security.documents.chunk_content", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    assert len(chunks) >= 1
    # The org is still configured for "semantic", but THIS run's real
    # per-section fallback means "fixed" is what actually produced these
    # chunks -- the persisted metadata must say so honestly.
    assert all(c.metadata_json["chunking_strategy"] == "fixed" for c in chunks)
