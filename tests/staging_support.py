"""Opt-in PostgreSQL fixtures with exact target validation and rollback cleanup."""

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from api.config import settings
from api.database import get_db
from api.main import app
from api.models.agent import Agent
from api.models.billing import Invoice, InvoiceStatus
from api.models.conversation import Conversation
from api.models.document import Document, DocumentStatus
from api.models.evaluation import EvaluationDataset
from api.models.mcp_server import MCPServerConfig, MCPToolCache
from api.models.media import MediaAsset, MediaStatus, MediaType
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.models.workflow import Workflow
from api.security.jwt import create_access_token
from scripts.staging_target import staging_url, validate_staging_url


@pytest_asyncio.fixture
async def staging_resources():
    if os.environ.get("RAG_STAGING_TESTS") != "YES":
        pytest.skip("Live staging tests require RAG_STAGING_TESTS=YES and the guarded staging runner.")
    target = staging_url()
    assert validate_staging_url(settings.DATABASE_URL) == target
    assert not settings.DATABASE_URL_TRANSACTION, "Transaction pooler override is forbidden for staging tests."
    assert os.environ.get("RAG_ENV_FILE", "").endswith(".env.staging")
    engine = create_async_engine(
        target, poolclass=NullPool,
        connect_args={"ssl": "require", "timeout": 10},
    )
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async with AsyncSession(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint",
            ) as session:
                tenants = []
                browser_ids = [
                    (os.environ.get(f"RAG_STAGING_USER_{suffix}"), os.environ.get(f"RAG_STAGING_ORG_{suffix}"))
                    for suffix in ("A", "B")
                ]
                use_browser_tenants = any(value for pair in browser_ids for value in pair)
                if use_browser_tenants:
                    assert all(value for pair in browser_ids for value in pair), "Both browser user/org pairs are required."
                    assert browser_ids[0][0] != browser_ids[1][0] and browser_ids[0][1] != browser_ids[1][1]
                for index, suffix in enumerate(("a", "b")):
                    tag = uuid.uuid4().hex
                    if use_browser_tenants:
                        user_id, org_id = browser_ids[index]
                        user = await session.get(User, uuid.UUID(user_id))
                        org = await session.get(Organization, uuid.UUID(org_id))
                        assert user is not None and org is not None, "Browser tenant does not exist on staging."
                        membership = await session.scalar(select(OrganizationMember).where(
                            OrganizationMember.organization_id == org.id,
                            OrganizationMember.user_id == user.id,
                        ))
                        assert membership is not None and membership.role == OrganizationRole.owner
                    else:
                        user = User(
                            email=f"staging-idor-{tag}@example.invalid",
                            is_email_verified=True, terms_version=settings.TERMS_VERSION,
                        )
                        org = Organization(name=f"Staging IDOR {suffix}", slug=f"staging-idor-{tag}")
                        session.add_all([user, org])
                        await session.flush()
                        session.add(OrganizationMember(
                            organization_id=org.id, user_id=user.id, role=OrganizationRole.owner,
                        ))
                    doc = Document(
                        organization_id=org.id, name=f"private-{suffix}.txt",
                        file_key=f"staging-test/{tag}", file_size=1, file_type="text/plain",
                        status=DocumentStatus.completed.value,
                    )
                    agent = Agent(
                        organization_id=org.id, name=f"agent-{suffix}",
                        system_prompt="Staging isolation test only", model_config_json={},
                    )
                    workflow = Workflow(organization_id=org.id, name=f"workflow-{suffix}", nodes=[], edges=[])
                    conversation = Conversation(
                        user_id=user.id, organization_id=org.id, agent_id=f"test-agent-{suffix}",
                        title=f"private-{suffix}", is_public=False,
                    )
                    dataset = EvaluationDataset(organization_id=org.id, name=f"dataset-{suffix}")
                    media = MediaAsset(
                        organization_id=org.id, uploaded_by=user.id, media_type=MediaType.video,
                        status=MediaStatus.completed, filename=f"{suffix}.mp4",
                        file_key=f"staging-test/{tag}.mp4", file_size=1, mime_type="video/mp4",
                    )
                    mcp = MCPServerConfig(
                        organization_id=org.id, name=f"mcp-{suffix}", transport="streamable_http",
                        url="https://staging-test.invalid/mcp",
                    )
                    invoice = Invoice(
                        organization_id=org.id, number=f"STAGING-{tag}", status=InvoiceStatus.pending,
                        subtotal_cents=100, total_cents=100,
                    )
                    session.add_all([doc, agent, workflow, conversation, dataset, media, mcp, invoice])
                    await session.flush()
                    session.add(MCPToolCache(server_id=mcp.id, name="test-tool", input_schema={}))
                    token, _ = create_access_token(user.id)
                    tenants.append({
                        "org": org, "user": user, "document": doc, "agent": agent,
                        "workflow": workflow, "conversation": conversation, "evaluation": dataset,
                        "media": media, "mcp": mcp, "billing": invoice,
                        "headers": {"Authorization": "Bearer " + token},
                    })
                await session.flush()

                async def override_db():
                    yield session

                previous = app.dependency_overrides.get(get_db)
                app.dependency_overrides[get_db] = override_db
                try:
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://staging-test") as client:
                        yield client, session, tenants, connection
                finally:
                    if previous is None:
                        app.dependency_overrides.pop(get_db, None)
                    else:
                        app.dependency_overrides[get_db] = previous
            await transaction.rollback()
    finally:
        await engine.dispose()
