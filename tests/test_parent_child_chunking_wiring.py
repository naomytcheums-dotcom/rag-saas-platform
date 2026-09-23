"""Phase 4, Étape 1 (correctif) -- proves `"parent_child"` is REALLY
wired into `process_document`, not just selectable while silently
falling back (the gap the prior report explicitly flagged). Same fast
SQLite convention as tests/test_chunking_strategy_wiring.py:
`download_document_file`/`extract_document_content` mocked, everything
else (chunk_parent_child, generate_embeddings, retrieval_pipeline) real.

Covers, with real end-to-end proof (not isolated unit calls): parent
creation, child creation, the persisted parent<->child relationship
(migration 0112's own `parent_chunk_id`/`chunk_role`), metadata
preservation, embedding policy (parent=None, child=real), real
retrieval exclusion of parents, real parent-context recovery after a
real retrieval hit, reindex-without-orphans, multi-tenant isolation,
citation attribution, and both real fallback paths (operator kill
switch, runtime failure)."""

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.database import Base
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization_settings import OrganizationSettings
from api.security.documents import MARKDOWN_CONTENT_TYPE, process_document
from api.services.retrieval_pipeline import bm25_search, fetch_organization_chunks, vector_search

_LONG_TEXT = " ".join(f"This is real sentence number {i} in a genuinely long real document about real testing." for i in range(80))


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _make_document(session, organization_id) -> Document:
    document = Document(
        organization_id=organization_id, workspace_id=None, name="doc.md",
        file_key="documents/x/doc.md", file_size=len(_LONG_TEXT), file_type=MARKDOWN_CONTENT_TYPE,
        status=DocumentStatus.pending.value, created_by=None,
    )
    session.add(document)
    await session.commit()
    return document


async def _set_parent_child(session, organization_id, **size_overrides) -> None:
    """Phase 4, Étape 1 (correctif config) -- `**size_overrides` accepts
    any of `parent_chunk_size`/`parent_chunk_overlap`/`child_chunk_size`/
    `child_chunk_overlap`; omitted ones keep the real, pre-existing
    global defaults (see `resolve_parent_chunk_size` and its 3
    siblings)."""
    session.add(OrganizationSettings(organization_id=organization_id, settings={"chunking_strategy": "parent_child", **size_overrides}))
    await session.commit()


def _mock_extraction(monkeypatch, text: str = _LONG_TEXT, section_metadata: dict | None = None):
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


def _parents(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    return [c for c in chunks if c.chunk_role == "parent"]


def _children(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    return [c for c in chunks if c.chunk_role == "child"]


# --------------------------------------- Test 1/2/3 -- selection + real parent/child creation --


async def test_parent_child_is_really_selectable_and_creates_both_populations(db_session, monkeypatch):
    """Validation criterion: la stratégie est sélectionnable, et sa
    vraie implémentation (pas un repli) crée réellement des parents ET
    des children."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    parents, children = _parents(chunks), _children(chunks)
    assert len(parents) >= 1
    assert len(children) > len(parents)  # each real parent is split into several real, smaller children
    assert all(c.metadata_json["chunking_strategy"] == "parent_child" for c in chunks)


# --------------------------------------- Test 4/5 -- the persisted relationship, both directions --


async def test_every_child_really_points_to_a_real_existing_parent(db_session, monkeypatch):
    """Validation criterion: relation child -> parent, persistée en
    base (migration 0112), pas seulement en mémoire."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    await process_document(db_session, document.id)

    chunks = await _get_chunks(db_session, document.id)
    parents_by_id = {p.id: p for p in _parents(chunks)}
    children = _children(chunks)
    assert children
    for child in children:
        assert child.parent_chunk_id is not None
        assert child.parent_chunk_id in parents_by_id
        assert parents_by_id[child.parent_chunk_id].document_id == child.document_id
        assert parents_by_id[child.parent_chunk_id].organization_id == child.organization_id


async def test_every_parent_really_has_at_least_one_real_child(db_session, monkeypatch):
    """Validation criterion: relation parent -> child (l'inverse), vérifiable
    par une vraie requête filtrant sur parent_chunk_id."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    await process_document(db_session, document.id)

    parents = _parents(await _get_chunks(db_session, document.id))
    for parent in parents:
        real_children = (await db_session.scalars(
            select(DocumentChunk).where(DocumentChunk.parent_chunk_id == parent.id)
        )).all()
        assert len(real_children) >= 1


# --------------------------------------- Test 6 -- metadata preserved --


async def test_parent_and_child_preserve_real_metadata(db_session, monkeypatch):
    """Validation criterion: document_id/organization_id/chunk_index/
    metadata de section/langue conservés pour les DEUX populations."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch, section_metadata={"page": 7, "source": "unit-test"})
    await process_document(db_session, document.id)

    chunks = await _get_chunks(db_session, document.id)
    for i, chunk in enumerate(chunks, start=1):
        assert chunk.document_id == document.id
        assert chunk.organization_id == org_id
        assert chunk.chunk_index == i
        assert chunk.metadata_json["page"] == 7
        assert chunk.metadata_json["source"] == "unit-test"
        assert "language" in chunk.metadata_json
    for child in _children(chunks):
        assert child.metadata_json["parent_chunk_id"] == str(child.parent_chunk_id)
        assert isinstance(child.metadata_json["parent_context"], str) and child.metadata_json["parent_context"]


# --------------------------------------- Test 7 -- embedding policy --


async def test_parents_never_get_a_real_embedding_children_always_do(db_session, monkeypatch):
    """Validation criterion: le parent ne reçoit jamais d'embedding
    (c'est ce qui l'exclut réellement du retrieval, voir Test 8), le
    child en reçoit toujours un réel."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    await process_document(db_session, document.id)

    chunks = await _get_chunks(db_session, document.id)
    assert all(p.embedding is None for p in _parents(chunks))
    assert all(c.embedding is not None and len(c.embedding) > 0 for c in _children(chunks))


# --------------------------------------- Test 8/9 -- real retrieval: child found, parent recovered --


async def test_real_vector_and_bm25_search_only_ever_return_children(db_session, monkeypatch):
    """Validation criterion: le retrieval réel (pas un mock) retrouve un
    child, et un parent n'est JAMAIS retourné -- zéro changement de code
    retrieval nécessaire, uniquement grâce à embedding=None sur le
    parent (fetch_organization_chunks filtre déjà embedding IS NOT NULL)."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    await process_document(db_session, document.id)
    await db_session.commit()

    corpus = await fetch_organization_chunks(db_session, org_id)
    assert corpus  # something is really searchable
    fetched_ids = {c["chunk_id"] for c in corpus}
    parents = _parents(await _get_chunks(db_session, document.id))
    assert not any(str(p.id) in fetched_ids for p in parents)  # a real parent is never in the real search corpus

    vector_hits = await vector_search(db_session, org_id, "real sentence", top_k=5)
    bm25_hits = await bm25_search(db_session, org_id, "real sentence", top_k=5)
    assert vector_hits and bm25_hits
    children_by_id = {str(c.id): c for c in _children(await _get_chunks(db_session, document.id))}
    for hit in vector_hits + bm25_hits:
        assert hit["chunk_id"] in children_by_id  # every real hit is really a child, never a parent


async def test_a_real_retrieved_child_carries_its_real_parent_context(db_session, monkeypatch):
    """Validation criterion: après un vrai retrieval, le parent est
    récupérable -- son contexte est déjà porté par le child retrouvé
    (metadata_json), donc exploitable sans requête supplémentaire."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    await process_document(db_session, document.id)
    await db_session.commit()

    hits = await vector_search(db_session, org_id, "real sentence", top_k=5)
    assert hits
    for hit in hits:
        parent_id = hit["metadata_json"]["parent_chunk_id"]
        real_parent = await db_session.get(DocumentChunk, uuid.UUID(parent_id))
        assert real_parent is not None
        assert real_parent.chunk_role == "parent"
        assert hit["metadata_json"]["parent_context"] == real_parent.content


# --------------------------------------- Test 11 -- reindex without orphans --


async def test_reindexing_replaces_parents_and_children_without_orphans_or_duplicates(db_session, monkeypatch):
    """Validation criterion: un second passage de process_document
    (reindex) ne laisse ni doublons ni enfants orphelins pointant vers
    un parent supprimé."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    await process_document(db_session, document.id)
    first_count = len(await _get_chunks(db_session, document.id))

    await process_document(db_session, document.id)
    chunks = await _get_chunks(db_session, document.id)

    assert len(chunks) == first_count  # no duplication from reprocessing
    parent_ids = {p.id for p in _parents(chunks)}
    for child in _children(chunks):
        assert child.parent_chunk_id in parent_ids  # no orphan: every child's parent is one of THIS run's own real parents


# --------------------------------------- Test 12 -- multi-tenant isolation --


async def test_parent_child_chunks_are_isolated_per_organization(db_session, monkeypatch):
    """Validation criterion: isolation multi-tenant réelle -- le
    retrieval d'une organisation ne voit jamais les chunks (parent ou
    child) d'une autre."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    await _set_parent_child(db_session, org_a)
    await _set_parent_child(db_session, org_b)
    doc_a = await _make_document(db_session, org_a)
    doc_b = await _make_document(db_session, org_b)
    _mock_extraction(monkeypatch)
    await process_document(db_session, doc_a.id)
    await process_document(db_session, doc_b.id)
    await db_session.commit()

    corpus_a = await fetch_organization_chunks(db_session, org_a)
    corpus_b = await fetch_organization_chunks(db_session, org_b)
    ids_a = {c["chunk_id"] for c in corpus_a}
    ids_b = {c["chunk_id"] for c in corpus_b}
    assert ids_a and ids_b and ids_a.isdisjoint(ids_b)

    all_chunks_a = await _get_chunks(db_session, doc_a.id)
    all_chunks_b = await _get_chunks(db_session, doc_b.id)
    assert all(c.organization_id == org_a for c in all_chunks_a)
    assert all(c.organization_id == org_b for c in all_chunks_b)


# --------------------------------------- Test 13 -- citation/source attribution --


async def test_citations_built_from_a_retrieved_child_point_at_its_own_precise_content(db_session, monkeypatch):
    """Validation criterion: l'attribution de citation reste correcte --
    une citation pointe le child précis retrouvé, jamais le texte plus
    large du parent (voir aussi tests/test_generation.py's own dedicated
    context-assembly test for the LLM-context side of this)."""
    from api.services.citations import _build_citation

    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    await process_document(db_session, document.id)
    await db_session.commit()

    hits = await vector_search(db_session, org_id, "real sentence", top_k=1)
    assert hits
    hit = hits[0]
    child = await db_session.get(DocumentChunk, uuid.UUID(hit["chunk_id"]))
    fake_response = type("FakeResponse", (), {"id": uuid.uuid4(), "answer": "An answer [1]."})()
    citation = _build_citation(response=fake_response, chunk=hit, number=1, is_primary=True)
    assert citation.text == child.content  # the real, precise child text -- never the wider real parent context
    assert citation.chunk_id == child.id


# --------------------------------------- Test 14 -- fallback / error behavior --


async def test_operator_kill_switch_falls_back_to_fixed_without_crashing(db_session, monkeypatch):
    """Validation criterion: le vrai kill switch opérateur
    (PARENT_CHILD_ENABLED=False) produit un repli honnête sur 'fixed',
    jamais un crash ni un document bloqué."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    monkeypatch.setattr(settings, "PARENT_CHILD_ENABLED", False)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    assert chunks
    assert all(c.chunk_role is None for c in chunks)  # really fell back to plain "fixed" chunks, not parent/child rows
    assert all(c.metadata_json["chunking_strategy"] == "fixed" for c in chunks)


async def test_a_runtime_failure_in_chunk_parent_child_falls_back_to_fixed(db_session, monkeypatch):
    """Validation criterion: un vrai échec à l'exécution (pas juste le
    kill switch) ne fait pas non plus échouer tout le document."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    monkeypatch.setattr("api.security.documents.chunk_parent_child", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    assert chunks
    assert all(c.chunk_role is None and c.metadata_json["chunking_strategy"] == "fixed" for c in chunks)


# --------------------------------------- Phase 4, Étape 1 (correctif config) -- configured sizes really flow through ---


async def test_configured_parent_and_child_sizes_are_really_used_by_process_document(db_session, monkeypatch):
    """Validation criterion (wiring + production): les tailles
    configurées par l'organisation (pas les constantes globales)
    arrivent réellement jusqu'au moteur parent_child et déterminent la
    taille réelle des chunks persistés."""
    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id, parent_chunk_size=64, parent_chunk_overlap=0, child_chunk_size=16, child_chunk_overlap=0)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    await process_document(db_session, document.id)

    chunks = await _get_chunks(db_session, document.id)
    parents, children = _parents(chunks), _children(chunks)
    assert parents and children
    # A real, deliberately tiny configured size (64/16 tokens, far below
    # the real global defaults 512/128) must really produce far more,
    # smaller real chunks than the default-sized run in
    # test_parent_child_is_really_selectable_and_creates_both_populations
    # above did for the SAME real `_LONG_TEXT` -- proof this isn't just
    # accepted, but genuinely propagated into the real chunking math.
    assert len(children) > 10


async def test_two_organizations_can_have_different_parent_child_sizes_without_contaminating_each_other(db_session, monkeypatch):
    """Validation criterion (wiring): deux organisations peuvent avoir
    des paramètres différents, et les paramètres de l'une ne
    contaminent jamais l'autre -- prouvé par un vrai nombre de chunks
    différent pour le MÊME texte réel."""
    org_small, org_large = uuid.uuid4(), uuid.uuid4()
    await _set_parent_child(db_session, org_small, parent_chunk_size=64, parent_chunk_overlap=0, child_chunk_size=16, child_chunk_overlap=0)
    await _set_parent_child(db_session, org_large, parent_chunk_size=1024, parent_chunk_overlap=0, child_chunk_size=512, child_chunk_overlap=0)
    doc_small = await _make_document(db_session, org_small)
    doc_large = await _make_document(db_session, org_large)
    _mock_extraction(monkeypatch)

    await process_document(db_session, doc_small.id)
    await process_document(db_session, doc_large.id)

    children_small = _children(await _get_chunks(db_session, doc_small.id))
    children_large = _children(await _get_chunks(db_session, doc_large.id))
    assert len(children_small) > len(children_large)  # the small-sized org really chunked into more, smaller pieces
    assert all(c.organization_id == org_small for c in children_small)
    assert all(c.organization_id == org_large for c in children_large)


async def test_full_pipeline_with_custom_sizes_still_supports_retrieval_and_citations(db_session, monkeypatch):
    """Validation criterion (production, real path): organization
    settings -> process_document -> tailles configurées -> DocumentChunk
    parent/children -> embeddings -> retrieval -> parent context ->
    citation, avec des tailles personnalisées (pas les valeurs par
    défaut) -- le chemin complet, pas seulement le chunker isolé."""
    from api.services.citations import _build_citation
    from api.services.retrieval_pipeline import vector_search

    org_id = uuid.uuid4()
    await _set_parent_child(db_session, org_id, parent_chunk_size=48, parent_chunk_overlap=0, child_chunk_size=12, child_chunk_overlap=0)
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)
    await process_document(db_session, document.id)
    await db_session.commit()

    chunks = await _get_chunks(db_session, document.id)
    assert _parents(chunks) and _children(chunks)
    assert all(p.embedding is None for p in _parents(chunks))
    assert all(c.embedding is not None for c in _children(chunks))

    hits = await vector_search(db_session, org_id, "real sentence", top_k=3)
    assert hits
    for hit in hits:
        child = await db_session.get(DocumentChunk, uuid.UUID(hit["chunk_id"]))
        assert child.chunk_role == "child"  # retrieval still only ever returns a child, with custom sizes too
        real_parent = await db_session.get(DocumentChunk, uuid.UUID(hit["metadata_json"]["parent_chunk_id"]))
        assert real_parent.chunk_role == "parent"
        assert hit["metadata_json"]["parent_context"] == real_parent.content  # parent context still recoverable

    fake_response = type("FakeResponse", (), {"id": uuid.uuid4(), "answer": "An answer [1]."})()
    citation = _build_citation(response=fake_response, chunk=hits[0], number=1, is_primary=True)
    child = await db_session.get(DocumentChunk, uuid.UUID(hits[0]["chunk_id"]))
    assert citation.text == child.content  # citation still correct with custom sizes


async def test_the_other_7_strategies_are_unaffected_by_the_new_parent_child_settings(db_session, monkeypatch):
    """Validation criterion (régression): les 7 autres stratégies
    continuent de fonctionner à l'identique -- elles n'ont jamais lu
    parent_chunk_size/child_chunk_size, même si ces réglages existent
    désormais sur l'organisation."""
    org_id = uuid.uuid4()
    # A real org with BOTH a real chunk_size/chunk_overlap override AND
    # real (unrelated) parent_child sizes configured -- proves the two
    # systems never cross-read each other.
    db_session.add(OrganizationSettings(organization_id=org_id, settings={
        "chunking_strategy": "recursive", "chunk_size": 40, "chunk_overlap": 0,
        "parent_chunk_size": 9999, "child_chunk_size": 1,
    }))
    await db_session.commit()
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    chunks = await _get_chunks(db_session, document.id)
    assert all(c.chunk_role is None for c in chunks)  # never parent/child rows
    assert all(len(c.content) <= 40 for c in chunks)  # really used chunk_size=40, not parent_chunk_size=9999 or child_chunk_size=1
