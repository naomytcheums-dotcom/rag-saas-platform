"""Second all-routes sweep: with REAL data.

tests/test_no_unhandled_errors_sweep.py calls every route with random ids, so most handlers answer 404 before they reach the code
that serializes a real row. Here the sweep first CREATES data through the API itself (every `POST /organizations/{org_id}/<collection>`
that accepts a schema-valid body), remembers the ids that come back, and then calls every operation substituting those real ids
into the path parameters: GETs first, then writes, then DELETEs. A 5xx or an exception escaping the application is a bug a real client
can trigger on real data."""

import asyncio
import re
import uuid
from contextlib import aclosing

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from api.database import Base, get_db
from api.config import settings
from api.main import app
from test_no_unhandled_errors_sweep import EXCLUDED, OPERATIONS, _request_kwargs, is_expected_501

REQUEST_TIMEOUT_SECONDS = 25

# Operations that would end the sweep's own session or delete the tenant it works in.
SKIP = re.compile(
    r"^(DELETE /organizations/\{org_id\}$|DELETE /account|POST /auth/logout|POST /account/|DELETE /auth/sessions|POST /auth/sessions/revoke|"
    r"POST /auth/password/change|POST /auth/2fa/disable|DELETE /auth/2fa)"
)


def _singular(segment: str) -> str:
    segment = segment.replace("-", "_")
    if segment.endswith("ies"):
        return segment[:-3] + "y"
    if segment.endswith("sses"):
        return segment[:-2]
    return segment[:-1] if segment.endswith("s") else segment


def _fill(path: str, ids: dict[str, str], org_id: str) -> str:
    out = path.replace("{org_id}", org_id)
    for name in re.findall(r"\{(\w+)\}", out):
        out = out.replace("{" + name + "}", ids.get(name) or str(uuid.uuid4()), 1)
    return out


async def _call(client, method, url, kwargs):
    try:
        return await asyncio.wait_for(client.request(method, url, **kwargs), REQUEST_TIMEOUT_SECONDS), None
    except asyncio.TimeoutError:
        return None, "no answer within the time limit"
    except Exception as exc:  # noqa: BLE001 -- an exception escaping the ASGI app IS the finding
        return None, f"EXC {type(exc).__name__}: {str(exc)[:200]}"


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    """A client whose every request gets its OWN database session AND its own connection, as in production. The shared fixtures use one
    in-memory SQLite connection for everything: a request cancelled by the sweep's time limit closes it and the whole database vanishes
    ("no such table"), which would turn one slow route into hundreds of bogus failures. A file database with no connection pooling
    keeps every request independent."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sweep.db'}", poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    # This sweep looks for unhandled errors in the API, not for broker or e-mail behaviour: never reach a real Resend account, and never
    # let a Celery dispatch wait on a broker. (Finding, measured: with the broker unreachable `.delay()` blocks the event loop for ~64 s,
    # see docs/FINAL_STATUS.md.)
    monkeypatch.setattr(settings, "RESEND_API_KEY", None)

    from celery.app.task import Task

    def _no_dispatch(self, *args, **kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(id=str(uuid.uuid4()))

    monkeypatch.setattr(Task, "apply_async", _no_dispatch)

    async def _fake_run_agent(self, *args, **kwargs):
        from types import SimpleNamespace
        from api.models.agent_run import AgentRunStatus

        return SimpleNamespace(status=AgentRunStatus.completed.value, result="A deterministic test answer.", error=None)

    async def _fake_chat_completion(*args, **kwargs):
        return "What would you like to know next?\nWhat should we explore?"

    challenges = {}

    async def _store_challenge(key, challenge):
        challenges[key] = challenge

    async def _pop_challenge(key):
        return challenges.pop(key, None)

    def _fake_stream_document_file(_file_key):
        return iter((b"offline sweep preview",))

    monkeypatch.setattr("api.services.agent_orchestrator.AgentOrchestrator.run_agent", _fake_run_agent)
    monkeypatch.setattr("api.services.llm_providers.chat_completion", _fake_chat_completion)
    monkeypatch.setattr("api.routers.documents.stream_document_file", _fake_stream_document_file)
    monkeypatch.setattr("api.security.webauthn._store_challenge", _store_challenge)
    monkeypatch.setattr("api.security.webauthn._pop_challenge", _pop_challenge)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def _register_with_org(client, email, password, org_name):
    token = (await client.post("/auth/register", json={"email": email, "password": password, "accept_terms": True})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org_id = (await client.post("/organizations", json={"name": org_name}, headers=headers)).json()["id"]
    return headers, org_id


async def _create_world(client, spec, headers, org_id, problems):
    """Create data through the API as the organization's owner and return the real ids that came back."""
    ids: dict[str, str] = {}

    def judge(method, path, response, error):
        if error:
            problems.append(f"{method} {path} -> {error}")
        elif response.status_code >= 500 and not is_expected_501(method, path, response):
            problems.append(f"{method} {path} -> {response.status_code} {response.text[:200]}")

    # 1. every collection-create route under the organization
    creates = [
        (m, p) for m, p in OPERATIONS
        if m == "POST" and re.fullmatch(r"/organizations/\{org_id\}/[a-z0-9\-_]+", p) and (m, p) not in EXCLUDED
    ]
    for method, path in creates:
        kwargs = {"headers": headers, **_request_kwargs(spec["paths"][path][method.lower()], spec)}
        response, error = await _call(client, method, _fill(path, ids, org_id), kwargs)
        judge(method, path, response, error)
        if response is not None and response.status_code in (200, 201):
            try:
                created = response.json()
            except ValueError:
                continue
            if isinstance(created, dict) and created.get("id"):
                ids[f"{_singular(path.rsplit('/', 1)[1])}_id"] = str(created["id"])
                ids.setdefault("id", str(created["id"]))

    # 2. ids that only exist as items of a list (documents, conversations, ...)
    for method, path in OPERATIONS:
        if method == "GET" and re.fullmatch(r"/organizations/\{org_id\}/[a-z0-9\-_]+", path):
            response, error = await _call(client, method, _fill(path, ids, org_id), {"headers": headers})
            if response is not None and response.status_code == 200:
                payload = response.json()
                items = payload if isinstance(payload, list) else next((v for v in payload.values() if isinstance(v, list)), []) if isinstance(payload, dict) else []
                if items and isinstance(items[0], dict) and items[0].get("id"):
                    ids.setdefault(f"{_singular(path.rsplit('/', 1)[1])}_id", str(items[0]["id"]))
    await _seed_direct_world(ids, org_id)
    return ids, judge


async def _seed_direct_world(ids, org_id):
    """Persist real tenant rows without S3, using this test's file-SQLite session."""
    from api.models.citation import Citation
    from api.models.conversation import Conversation, ConversationMessage
    from api.models.document import Document, DocumentChunk
    from api.models.evaluation import EvaluationDataset, EvaluationJob, EvaluationQuestion
    from api.models.organization import OrganizationMember, OrganizationRole
    from api.models.response import Response

    async with aclosing(app.dependency_overrides[get_db]()) as dependency:
        session = await anext(dependency)
        organization_id = uuid.UUID(org_id)
        owner_id = await session.scalar(select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role == OrganizationRole.owner,
        ))
        assert owner_id is not None
        document = Document(
            organization_id=organization_id, created_by=owner_id, name="seeded.txt",
            file_key="offline-sweep/seeded.txt", file_size=36, file_type="text/plain",
            status="completed", metadata_json={},
        )
        conversation = Conversation(
            organization_id=organization_id, user_id=owner_id,
            agent_id=ids.get("agent_id", "offline-sweep"), title="Seeded conversation",
        )
        response = Response(
            organization_id=organization_id, created_by=owner_id,
            query="When is support available?", answer="Monday at 09:00.",
        )
        dataset = EvaluationDataset(
            organization_id=organization_id, created_by=owner_id, name="Seeded dataset",
        )
        session.add_all([document, conversation, response, dataset])
        await session.flush()
        chunks = [
            DocumentChunk(
                document_id=document.id, organization_id=organization_id,
                content=f"Support is available Monday at 09:00. Section {index}.",
                chunk_index=index, metadata_json={},
            ) for index in (1, 2)
        ]
        message = ConversationMessage(
            conversation_id=conversation.id, role="user", content="When is support available?",
        )
        questions = [
            EvaluationQuestion(
                dataset_id=dataset.id, question=f"When is support available? Section {index}",
                expected_answer="Monday at 09:00.",
                expected_documents=[{"document_id": str(document.id), "relevance_score": 1}],
            ) for index in (1, 2)
        ]
        job = EvaluationJob(dataset_id=dataset.id, created_by=owner_id, status="pending", total_questions=2)
        session.add_all([*chunks, message, *questions, job])
        await session.flush()
        citation = Citation(
            response_id=response.id, document_id=document.id, chunk_id=chunks[0].id,
            text=chunks[0].content, source_title=document.name, relevance_score=0.9, citation_number=1,
        )
        session.add(citation)
        await session.commit()
        ids.update({
            "document_id": str(document.id), "chunk_id": str(chunks[0].id),
            "conversation_id": str(conversation.id), "message_id": str(message.id),
            "response_id": str(response.id), "citation_id": str(citation.id),
            "dataset_id": str(dataset.id), "question_id": str(questions[0].id),
            "job_id": str(job.id), "evaluation_job_id": str(job.id),
        })


ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 2, "DELETE": 3}


def _sweepable():
    return [op for op in sorted(OPERATIONS, key=lambda op: (ORDER[op[0]], op[1])) if not (SKIP.match(f"{op[0]} {op[1]}") or op in EXCLUDED)]


async def test_no_operation_fails_with_an_unhandled_error_on_real_data(client, register_payload):
    spec = app.openapi()
    headers, org_id = await _register_with_org(client, register_payload["email"], register_payload["password"], "Real Data Sweep")
    problems: list[str] = []
    ids, judge = await _create_world(client, spec, headers, org_id, problems)

    # 3. every operation, real ids substituted: reads, then writes, then deletes
    for method, path in _sweepable():
        kwargs = {"headers": headers, **_request_kwargs(spec["paths"][path][method.lower()], spec)}
        response, error = await _call(client, method, _fill(path, ids, org_id), kwargs)
        judge(method, path, response, error)

    assert len(ids) >= 3, f"the sweep created too little real data to be meaningful: {sorted(ids)}"
    assert not problems, f"{len(problems)} operations failed with an unhandled error (ids known: {sorted(ids)}):\n  " + "\n  ".join(problems)


async def test_another_tenant_never_succeeds_on_the_real_ids_of_this_one(client, register_payload):
    """Cross-tenant isolation with REAL ids. Tenant A creates data; tenant B (its own, fully valid account and organization) then calls every
    operation that takes an identifier, with A's organization id and A's real resource ids in the path. B must never get a 2xx: a success
    would mean B read, changed or deleted something of A's -- or reached A's handler at all."""
    from test_no_unhandled_errors_sweep import PUBLIC_BY_DESIGN

    spec = app.openapi()
    headers_a, org_a = await _register_with_org(client, register_payload["email"], register_payload["password"], "Tenant A")
    problems: list[str] = []
    ids, judge = await _create_world(client, spec, headers_a, org_a, problems)
    headers_b, _org_b = await _register_with_org(client, "tenant-b@example.com", "correct-horse-battery-staple", "Tenant B")

    leaks = []
    for method, path in _sweepable():
        params = re.findall(r"\{(\w+)\}", path)
        if not params or f"{method} {path}" in PUBLIC_BY_DESIGN:
            continue
        # only operations that address something of A's: A's org id, or an id that A's own data produced
        if not any(name == "org_id" or name in ids for name in params):
            continue
        kwargs = {"headers": headers_b, **_request_kwargs(spec["paths"][path][method.lower()], spec)}
        response, error = await _call(client, method, _fill(path, ids, org_a), kwargs)
        judge(method, path, response, error)
        if response is not None and 200 <= response.status_code < 300:
            leaks.append(f"{method} {path} -> {response.status_code} {response.text[:120]}")

    assert len(ids) >= 3, f"too little data was created for this test to mean anything: {sorted(ids)}"
    assert not leaks, f"{len(leaks)} operations let tenant B succeed on tenant A's real ids (ids: {sorted(ids)}):\n  " + "\n  ".join(leaks)
    assert not problems, "Cross-tenant operations escaped or returned server errors:\n" + "\n".join(problems)


@pytest.mark.parametrize("role", ["member", "viewer"])
async def test_real_data_operations_by_organization_role(client, register_payload, role):
    from api.models.organization import OrganizationMember, OrganizationRole
    from api.models.user import User
    from api.security.jwt import create_access_token
    from test_no_unhandled_errors_sweep import PUBLIC_BY_DESIGN

    spec = app.openapi()
    headers_owner, org_id = await _register_with_org(
        client, register_payload["email"], register_payload["password"], "Role Sweep",
    )
    problems = []
    ids, judge = await _create_world(client, spec, headers_owner, org_id, problems)
    async with aclosing(app.dependency_overrides[get_db]()) as dependency:
        session = await anext(dependency)
        user = User(email=f"sweep-{role}@example.com", hashed_password="unused-in-token-test",
                    is_email_verified=True)
        session.add(user)
        await session.flush()
        session.add(OrganizationMember(
            organization_id=uuid.UUID(org_id), user_id=user.id, role=OrganizationRole(role),
        ))
        await session.commit()
        token, _ = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}
    writes = []
    for method, path in _sweepable():
        kwargs = {"headers": headers, **_request_kwargs(spec["paths"][path][method.lower()], spec)}
        response, error = await _call(client, method, _fill(path, ids, org_id), kwargs)
        judge(method, path, response, error)
        # Public operations are role-independent; auth/account writes control
        # the caller's own identity, not the organization's writable resources.
        personal_or_public = f"{method} {path}" in PUBLIC_BY_DESIGN or path.startswith(("/auth/", "/account/"))
        if role == "viewer" and method != "GET" and not personal_or_public:
            if response is not None and 200 <= response.status_code < 300:
                writes.append(f"{method} {path} -> {response.status_code}")
    assert not problems, f"{role} server failures:\n" + "\n".join(problems)
    assert not writes, "Viewer mutation successes requiring contract review:\n" + "\n".join(writes)
