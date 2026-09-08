"""Partie 8.1.14 -- conversation export (PDF/DOCX/JSON/Markdown)."""

import uuid

import pytest

from api.security.conversations import add_message, create_conversation
from api.services.conversation_export import ExportError, export_to_docx, export_to_json, export_to_markdown, export_to_pdf


async def _seed(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Export test")
    await add_message(db_session, conversation.id, "user", "Hello")
    await add_message(db_session, conversation.id, "assistant", "Hi there, **bold** and `code`.")
    await db_session.commit()
    return conversation, user_id


async def test_export_to_markdown_contains_transcript(db_session):
    """Validation criterion: l'export Markdown fonctionne."""
    conversation, user_id = await _seed(db_session)
    markdown = await export_to_markdown(db_session, conversation.id, user_id)
    assert "Export test" in markdown
    assert "Hello" in markdown
    assert "bold" in markdown


async def test_export_to_json_contains_all_messages(db_session):
    """Validation criterion: l'export JSON fonctionne."""
    conversation, user_id = await _seed(db_session)
    data = await export_to_json(db_session, conversation.id, user_id)
    assert data["title"] == "Export test"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"


async def test_export_to_docx_produces_valid_bytes(db_session):
    """Validation criterion: l'export DOCX fonctionne."""
    conversation, user_id = await _seed(db_session)
    docx_bytes = await export_to_docx(db_session, conversation.id, user_id)
    assert docx_bytes[:2] == b"PK"  # DOCX is a zip archive
    assert len(docx_bytes) > 0


async def test_export_rejects_other_users_conversation(db_session):
    conversation, user_id = await _seed(db_session)
    with pytest.raises(ExportError):
        await export_to_json(db_session, conversation.id, uuid.uuid4())


async def test_export_to_pdf_raises_honest_error_without_native_libs_or_succeeds(db_session):
    """Validation criterion: robustesse -- dépendance système manquante.
    This real test passes either way: a real PDF is produced where
    WeasyPrint's native libraries are installed (CI), or a real, honest
    `ExportError` is raised where they are not (this local dev
    machine) -- never a raw, unhandled `OSError` reaching the caller."""
    conversation, user_id = await _seed(db_session)
    try:
        pdf_bytes = await export_to_pdf(db_session, conversation.id, user_id)
        assert pdf_bytes[:4] == b"%PDF"
    except ExportError as exc:
        assert "WeasyPrint" in str(exc)


async def test_export_endpoints_return_correct_content_types(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User

    payload = {"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True}
    token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "Export"}, headers=headers)
    conversation_id = created.json()["id"]
    await client.post(f"/conversations/{conversation_id}/messages", json={"role": "user", "content": "hi"}, headers=headers)

    json_export = await client.get(f"/conversations/{conversation_id}/export/json", headers=headers)
    assert json_export.status_code == 200
    assert json_export.json()["title"] == "Export"

    markdown_export = await client.get(f"/conversations/{conversation_id}/export/markdown", headers=headers)
    assert markdown_export.status_code == 200
    assert markdown_export.headers["content-type"].startswith("text/markdown")

    docx_export = await client.get(f"/conversations/{conversation_id}/export/docx", headers=headers)
    assert docx_export.status_code == 200
