"""Item 3.4.2 (vector search): the NATIVE pgvector branch, with real embeddings, on a real PostgreSQL. Opt-in.

tests/test_retrieval_pipeline.py exercises the numpy fallback on SQLite; the audit could not say which branch production takes. This test runs the
pgvector branch (`_pgvector_rank_chunks`: HNSW index, cosine distance, tenant filter) with embeddings produced by the default model, and checks that

  * the native branch answers (it returns None when it does not apply, and the numpy path would silently take over);
  * a paraphrased question finds the right passage first;
  * a passage of ANOTHER organization, worded almost identically, is never returned;
  * the native ranking agrees with the numpy ranking on the same data.

Needs PostgreSQL with pgvector (TEST_DATABASE_URL) and the default embedding model in the local Hugging Face cache.

    PGVECTOR_REAL_TEST=1 HF_HUB_OFFLINE=1 sh scripts/run_tests_local.sh tests/test_pgvector_real_search.py"""

import os
import uuid

import numpy as np
import pytest
from sqlalchemy import delete, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.models.user import User
from api.security.documents import generate_embeddings
from api.services.retrieval_pipeline import _pgvector_rank_chunks

pytestmark = pytest.mark.skipif(os.environ.get("PGVECTOR_REAL_TEST") != "1", reason="set PGVECTOR_REAL_TEST=1 (needs PostgreSQL + pgvector and the embedding model)")


@pytest.fixture
async def db_session():
    """A real PostgreSQL session. The project's usual `db_session` is an in-memory SQLite database, which has no pgvector. Refuses anything that is not a local
    database whose name says it is for tests, so a misconfigured DATABASE_URL can never make this test write to a real database."""
    url = make_url(settings.DATABASE_URL)
    if url.host not in ("127.0.0.1", "localhost", "::1") or not ({"pytest", "test"} & set(part for part in (url.database or "").replace("-", "_").split("_"))):
        pytest.fail("DATABASE_URL must be a local database whose name contains 'pytest' or 'test'")
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"PostgreSQL is not reachable ({type(exc).__name__})")
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session
    await engine.dispose()

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
PASSAGES = {
    "refund": "Customers may request a full refund within 30 days of purchase. After 30 days no refund is possible.",
    "password": "To reset a forgotten password, open the login page, choose 'Forgot password' and follow the link sent by e-mail.",
    "invoice": "Invoices are issued on the first day of each month and can be downloaded as PDF from the billing page.",
    "deletion": "When an account is deleted all personal data is erased after a thirty day grace period.",
    "sso": "Enterprise customers can sign in with their identity provider using OpenID Connect single sign-on.",
    "limits": "API requests are limited to sixty per minute per key; higher limits are available on the Business plan.",
    "hours": "Our support team answers questions on weekdays between nine in the morning and six in the evening.",
    "export": "Every conversation can be exported as a text file from the menu at the top right of the chat.",
}
QUESTION = "How do I get my money back after buying a plan?"


async def _organization(db, name):
    organization = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db.add(organization)
    await db.flush()
    return organization


async def _document_with_chunks(db, organization, owner, passages: dict[str, str]):
    document = Document(
        organization_id=organization.id, name=f"{organization.slug}.txt", file_key=f"documents/{uuid.uuid4().hex}/kb.txt", file_size=1,
        file_type="text/plain", status=DocumentStatus.completed.value, created_by=owner.id,
    )
    db.add(document)
    await db.flush()
    vectors = generate_embeddings(list(passages.values()), MODEL)
    for index, ((_key, text), vector) in enumerate(zip(passages.items(), vectors, strict=True)):
        db.add(DocumentChunk(
            document_id=document.id, organization_id=organization.id, content=text, chunk_index=index,
            embedding=[float(x) for x in vector], embedding_vector=[float(x) for x in vector],
        ))
    await db.flush()


async def test_the_native_pgvector_branch_finds_the_right_passage_and_never_crosses_tenants(db_session):
    db = db_session
    if db.bind is None or db.bind.dialect.name != "postgresql":
        pytest.skip("needs a PostgreSQL TEST_DATABASE_URL")
    owner = User(email=f"pgv-{uuid.uuid4().hex[:8]}@example.com", hashed_password="irrelevant")
    db.add(owner)
    await db.flush()
    org_a = await _organization(db, "Vector Org A")
    org_b = await _organization(db, "Vector Org B")
    await _document_with_chunks(db, org_a, owner, PASSAGES)
    # Another organization holds a passage that is almost word for word the right answer, plus a distractor.
    await _document_with_chunks(db, org_b, owner, {"refund_b": "Customers may request a full refund within 30 days of purchase, no questions asked.", "other": PASSAGES["hours"]})
    await db.commit()
    org_a_id, org_b_id, owner_id = org_a.id, org_b.id, owner.id  # read before any rollback expires the objects

    try:
        query_vector = [float(x) for x in generate_embeddings([QUESTION], MODEL)[0]]
        assert len(query_vector) == settings.EMBEDDING_VECTOR_DIM

        rows = await _pgvector_rank_chunks(db, org_a_id, query_vector, top_k=5)

        assert rows is not None, "the native pgvector branch did not apply (it fell back to numpy)"
        assert rows[0]["content"] == PASSAGES["refund"], [r["content"] for r in rows]
        assert len(rows) == 5
        returned = {row["content"] for row in rows}
        assert "Customers may request a full refund within 30 days of purchase, no questions asked." not in returned, "a passage of another organization was returned"

        # Same ranking as a plain cosine computation over the same stored vectors (the numpy path computes exactly this).
        matrix = np.array(generate_embeddings(list(PASSAGES.values()), MODEL))
        cosine = matrix @ np.array(query_vector) / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vector))
        expected = [list(PASSAGES.values())[i] for i in np.argsort(-cosine)[:5]]
        assert [row["content"] for row in rows] == expected
    finally:
        await db.rollback()
        await db.execute(delete(Organization).where(Organization.id.in_([org_a_id, org_b_id])))
        await db.execute(delete(User).where(User.id == owner_id))
        await db.commit()
