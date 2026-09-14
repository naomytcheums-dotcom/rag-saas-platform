"""Partie 24 -- real dataset upload, JSONL validation, and access
control. S3 is stubbed the same way tests/test_documents.py's own
`_stub_s3` does (a plain monkeypatched fake, not moto)."""

import io
import uuid

from sqlalchemy import select

from api.models.fine_tuning import FineTuningDataset
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.services.fine_tuning_storage import validate_jsonl_dataset


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, org_id


def _stub_storage(monkeypatch):
    monkeypatch.setattr("api.services.fine_tuning.upload_finetuning_dataset_file", lambda org_id, dataset_id, filename, content: f"fine-tuning/{org_id}/{dataset_id}/{filename}")
    monkeypatch.setattr("api.services.fine_tuning.download_finetuning_dataset_file", lambda file_key: _VALID_JSONL)
    monkeypatch.setattr("api.services.fine_tuning.delete_finetuning_dataset_file", lambda file_key: None)


_VALID_EXAMPLE = '{"messages": [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]}\n'
_VALID_JSONL = (_VALID_EXAMPLE * 10).encode("utf-8")


# -------------------------------------------------------------- validate_jsonl_dataset (pure, real, no mocking)

def test_validate_jsonl_dataset_accepts_real_valid_examples():
    count, errors = validate_jsonl_dataset(_VALID_JSONL)
    assert count == 10
    assert errors == []


def test_validate_jsonl_dataset_reports_malformed_json_per_line():
    content = _VALID_EXAMPLE.encode() + b"not real json\n" + _VALID_EXAMPLE.encode()
    count, errors = validate_jsonl_dataset(content)
    assert count == 2
    assert len(errors) == 1
    assert errors[0]["line"] == 2
    assert "invalid JSON" in errors[0]["error"]


def test_validate_jsonl_dataset_reports_missing_messages():
    content = b'{"foo": "bar"}\n'
    count, errors = validate_jsonl_dataset(content)
    assert count == 0
    assert "messages" in errors[0]["error"]


def test_validate_jsonl_dataset_reports_unknown_role():
    content = b'{"messages": [{"role": "narrator", "content": "once upon a time"}]}\n'
    count, errors = validate_jsonl_dataset(content)
    assert count == 0
    assert "unknown role" in errors[0]["error"]


def test_validate_jsonl_dataset_skips_blank_lines():
    content = _VALID_EXAMPLE.encode() + b"\n\n" + _VALID_EXAMPLE.encode()
    count, errors = validate_jsonl_dataset(content)
    assert count == 2
    assert errors == []


# -------------------------------------------------------------- endpoints

async def test_create_dataset_requires_admin(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Dataset Org")

    member_token, member = await _register(client, db_session, "ft_dataset_member@example.com")
    owner = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    response = await client.post(
        f"/fine-tuning/datasets?org_id={org_id}",
        data={"name": "Chat dataset"}, files={"file": ("data.jsonl", io.BytesIO(_VALID_JSONL), "application/jsonl")},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403

    response = await client.post(
        f"/fine-tuning/datasets?org_id={org_id}",
        data={"name": "Chat dataset"}, files={"file": ("data.jsonl", io.BytesIO(_VALID_JSONL), "application/jsonl")},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"
    assert body["example_count"] == 10


async def test_create_dataset_rejects_a_non_jsonl_filename(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Bad Ext Org")

    response = await client.post(
        f"/fine-tuning/datasets?org_id={org_id}",
        data={"name": "Bad"}, files={"file": ("data.csv", io.BytesIO(_VALID_JSONL), "text/csv")},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_create_dataset_stores_error_status_for_too_few_examples(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Too Few Org")

    small_jsonl = (_VALID_EXAMPLE * 2).encode("utf-8")
    response = await client.post(
        f"/fine-tuning/datasets?org_id={org_id}",
        data={"name": "Tiny"}, files={"file": ("data.jsonl", io.BytesIO(small_jsonl), "application/jsonl")},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "error"
    assert body["validation_errors"]


async def test_get_dataset_returns_404_for_non_member(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Private FT Org")
    created = (await client.post(
        f"/fine-tuning/datasets?org_id={org_id}", data={"name": "D"}, files={"file": ("data.jsonl", io.BytesIO(_VALID_JSONL), "application/jsonl")},
        headers=_auth_header(owner_token),
    )).json()

    stranger_token, _stranger = await _register(client, db_session, "ft_dataset_stranger@example.com")
    response = await client.get(f"/fine-tuning/datasets/{created['id']}", headers=_auth_header(stranger_token))
    assert response.status_code == 404


async def test_validate_dataset_endpoint_revalidates_the_stored_file(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Revalidate Org")
    created = (await client.post(
        f"/fine-tuning/datasets?org_id={org_id}", data={"name": "D"}, files={"file": ("data.jsonl", io.BytesIO(_VALID_JSONL), "application/jsonl")},
        headers=_auth_header(owner_token),
    )).json()

    response = await client.post(f"/fine-tuning/datasets/{created['id']}/validate", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


async def test_delete_dataset_removes_the_row(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Delete FT Org")
    created = (await client.post(
        f"/fine-tuning/datasets?org_id={org_id}", data={"name": "D"}, files={"file": ("data.jsonl", io.BytesIO(_VALID_JSONL), "application/jsonl")},
        headers=_auth_header(owner_token),
    )).json()

    response = await client.delete(f"/fine-tuning/datasets/{created['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 204
    assert await db_session.get(FineTuningDataset, uuid.UUID(created["id"])) is None
