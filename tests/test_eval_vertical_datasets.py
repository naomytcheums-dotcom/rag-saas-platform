"""Spec 7.1.8 - the vertical Eval Lab datasets (FastAPI, Legal, HR, Finance) are well-formed and importable."""

import csv
from pathlib import Path

import pytest

DIR = Path(__file__).resolve().parents[1] / "eval_datasets" / "verticals"
NAMES = ["fastapi", "legal", "hr", "finance"]


@pytest.mark.parametrize("name", NAMES)
def test_the_file_has_the_columns_the_importer_expects_and_enough_questions(name):
    with (DIR / f"{name}.csv").open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert reader.fieldnames == ["question", "expected_answer", "difficulty", "category"]
    assert len(rows) >= 15


@pytest.mark.parametrize("name", NAMES)
def test_every_row_is_complete_unique_and_uses_known_difficulties(name):
    with (DIR / f"{name}.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    questions = [r["question"].strip().lower() for r in rows]
    assert len(set(questions)) == len(questions), "duplicate question"
    for r in rows:
        assert None not in r.values() and r.get(None) is None, f"malformed row (unquoted comma?): {r}"
        assert r["question"].strip().endswith("?"), r["question"]
        assert len(r["expected_answer"].strip()) >= 15, r
        assert r["difficulty"] in {"easy", "medium", "hard"}, r
        assert r["category"].strip(), r


@pytest.mark.parametrize("name", NAMES)
async def test_the_dataset_imports_through_the_real_endpoint(name, client, db_session, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org = (await client.post("/organizations", json={"name": f"Vertical {name}"}, headers=headers)).json()["id"]
    dataset = (await client.post(f"/organizations/{org}/datasets", json={"name": name}, headers=headers)).json()
    content = (DIR / f"{name}.csv").read_bytes()
    response = await client.post(f"/datasets/{dataset['id']}/questions/import?format=csv", files={"file": (f"{name}.csv", content, "text/csv")}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported"] == 15 and body.get("errors", []) in ([], None)
    listing = (await client.get(f"/datasets/{dataset['id']}/questions?limit=50", headers=headers)).json()
    assert listing["total"] == 15 and {q["difficulty"] for q in listing["items"]} <= {"easy", "medium", "hard"}
