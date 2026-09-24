"""Real tests for the DB-backed notification template CRUD + preview
+ test endpoints (P2 #6, session SSRF épinglé).

Uses an in-memory SQLite DB with the real schema for
notification_templates, so the real lookup order (org-specific ->
global -> code default) is genuinely exercised, not mocked.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.models.notification_template import NotificationTemplate
from api.security import notifications as svc
from api.database import Base


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        # Only the table we need -- full Base.metadata.create_all pulls
        # in FKs to tables we don't need here.
        await conn.run_sync(lambda sync_conn: NotificationTemplate.__table__.create(sync_conn, checkfirst=True))
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_get_template(db):
    org_id = uuid.uuid4()
    created = await svc.create_notification_template(
        db, org_id, "workflow_completed", "Done!", "Workflow {{ workflow_name }} done.",
        email_subject="Done: {{ workflow_name }}",
    )
    await db.commit()
    fetched = await svc.get_notification_template(db, org_id, created.id)
    assert fetched.notification_type == "workflow_completed"
    assert fetched.title == "Done!"


@pytest.mark.asyncio
async def test_get_template_wrong_org_raises(db):
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    created = await svc.create_notification_template(db, org_a, "workflow_completed", "T", "B")
    await db.commit()
    with pytest.raises(svc.NotificationTemplateNotFoundError):
        await svc.get_notification_template(db, org_b, created.id)


@pytest.mark.asyncio
async def test_update_template(db):
    org_id = uuid.uuid4()
    created = await svc.create_notification_template(db, org_id, "workflow_completed", "Old", "Old body")
    await db.commit()
    updated = await svc.update_notification_template(db, org_id, created.id, title="New", is_active=False)
    await db.commit()
    assert updated.title == "New"
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_delete_template(db):
    org_id = uuid.uuid4()
    created = await svc.create_notification_template(db, org_id, "workflow_completed", "T", "B")
    await db.commit()
    await svc.delete_notification_template(db, org_id, created.id)
    await db.commit()
    with pytest.raises(svc.NotificationTemplateNotFoundError):
        await svc.get_notification_template(db, org_id, created.id)


@pytest.mark.asyncio
async def test_preview_uses_code_default_when_no_db_row(db):
    org_id = uuid.uuid4()
    rendered = await svc.preview_notification_template(
        db, org_id, "workflow_completed", {"workflow_name": "Ingest"},
    )
    assert "Ingest" in rendered["body"]
    assert "Ingest" in rendered["email_subject"]


@pytest.mark.asyncio
async def test_preview_uses_org_override_when_present(db):
    org_id = uuid.uuid4()
    await svc.create_notification_template(
        db, org_id, "workflow_completed",
        "Custom title", "Custom body for {{ workflow_name }}",
        email_subject="Custom subject {{ workflow_name }}",
    )
    await db.commit()
    rendered = await svc.preview_notification_template(
        db, org_id, "workflow_completed", {"workflow_name": "Ingest"},
    )
    assert rendered["title"] == "Custom title"
    assert rendered["body"] == "Custom body for Ingest"
    assert rendered["email_subject"] == "Custom subject Ingest"


@pytest.mark.asyncio
async def test_preview_falls_back_to_code_default_when_inactive(db):
    org_id = uuid.uuid4()
    await svc.create_notification_template(
        db, org_id, "workflow_completed",
        "Custom title", "Custom body",
        is_active=False,
    )
    await db.commit()
    rendered = await svc.preview_notification_template(
        db, org_id, "workflow_completed", {"workflow_name": "Ingest"},
    )
    # Inactive row is ignored -> code default used
    assert rendered["title"] == "Workflow completed"


@pytest.mark.asyncio
async def test_list_templates_scoped_to_org(db):
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    await svc.create_notification_template(db, org_a, "workflow_completed", "A", "A body")
    await svc.create_notification_template(db, org_b, "workflow_failed", "B", "B body")
    await db.commit()
    listed_a = await svc.list_notification_templates(db, org_a)
    assert len(listed_a) == 1
    assert listed_a[0].title == "A"
