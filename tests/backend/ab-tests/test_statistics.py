"""Partie 21 -- the real statistical additions: confidence intervals,
Cohen's d effect size, statistical power, min_sample_size_reached, and
the /statistics endpoint's real ABTestResult snapshot side effect."""

from sqlalchemy import select

from api.models.user import User


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


async def _create_and_start(client, owner_token, org_id, name="T"):
    test = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": name, "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()
    await client.post(f"/ab-tests/{test['id']}/start", headers=_auth_header(owner_token))
    return test


async def _track(client, owner_token, test_id, variant, values):
    for value in values:
        await client.post(f"/ab-tests/{test_id}/track", json={"variant": variant, "metric": "conversion_rate", "value": value}, headers=_auth_header(owner_token))


async def test_results_are_honestly_none_with_fewer_than_2_samples(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Sparse Org")
    test = await _create_and_start(client, owner_token, org_id)
    await _track(client, owner_token, test["id"], "a", [1.0])
    await _track(client, owner_token, test["id"], "b", [2.0])

    response = await client.get(f"/ab-tests/{test['id']}/results", headers=_auth_header(owner_token))
    row = response.json()["metrics"]["conversion_rate"]
    assert row["p_value"] is None
    assert row["significant"] is None
    assert row["confidence_interval_lower"] is None
    assert row["effect_size_cohens_d"] is None
    assert row["statistical_power"] is None


async def test_results_include_real_statistics_with_enough_samples(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Real Stats Org")
    test = await _create_and_start(client, owner_token, org_id)
    await _track(client, owner_token, test["id"], "a", [1.0, 1.0, 1.0, 1.0, 1.0])
    await _track(client, owner_token, test["id"], "b", [5.0, 5.0, 5.0, 5.0, 5.0])

    response = await client.get(f"/ab-tests/{test['id']}/results", headers=_auth_header(owner_token))
    row = response.json()["metrics"]["conversion_rate"]
    assert row["variant_a"]["mean"] == 1.0
    assert row["variant_b"]["mean"] == 5.0
    assert row["p_value"] is not None
    assert row["significant"] is True  # a huge, real, zero-variance gap between the two groups
    assert row["confidence_interval_lower"] is not None
    assert row["confidence_interval_upper"] is not None
    # Real, honest degenerate case: zero variance in BOTH groups means a
    # zero-width interval (lower == upper), not a bug -- there is
    # genuinely no real uncertainty left to express when every sample
    # in each group was identical.
    assert row["confidence_interval_lower"] == row["confidence_interval_upper"] == 4.0
    assert row["effect_size_cohens_d"] is None  # pooled std is 0 (zero real variance within each group) -- honestly None, not a fabricated infinity


async def test_min_sample_size_reached_reflects_the_real_per_test_threshold(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Sample Size Org")
    test = (await client.post(
        f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}, "min_sample_size": 3}, headers=_auth_header(owner_token),
    )).json()
    await client.post(f"/ab-tests/{test['id']}/start", headers=_auth_header(owner_token))
    await _track(client, owner_token, test["id"], "a", [1.0, 2.0])
    await _track(client, owner_token, test["id"], "b", [1.0, 2.0])

    response = await client.get(f"/ab-tests/{test['id']}/results", headers=_auth_header(owner_token))
    assert response.json()["metrics"]["conversion_rate"]["min_sample_size_reached"] is False  # 2 samples tracked, 3 required

    await _track(client, owner_token, test["id"], "a", [3.0])
    await _track(client, owner_token, test["id"], "b", [3.0])
    response = await client.get(f"/ab-tests/{test['id']}/results", headers=_auth_header(owner_token))
    assert response.json()["metrics"]["conversion_rate"]["min_sample_size_reached"] is True


async def test_statistics_endpoint_persists_a_real_snapshot(client, db_session, register_payload):
    from api.models.evaluation import ABTestResult

    owner_token, org_id = await _make_org(client, db_session, register_payload, "Snapshot Org")
    test = await _create_and_start(client, owner_token, org_id)
    await _track(client, owner_token, test["id"], "a", [1.0, 2.0])
    await _track(client, owner_token, test["id"], "b", [3.0, 4.0])

    response = await client.get(f"/ab-tests/{test['id']}/statistics", headers=_auth_header(owner_token))
    assert response.status_code == 200

    import uuid
    rows = (await db_session.scalars(select(ABTestResult).where(ABTestResult.ab_test_id == uuid.UUID(test["id"])))).all()
    assert len(rows) == 2  # one real row per variant
    assert {row.variant for row in rows} == {"a", "b"}


async def test_export_json_and_csv(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Export Org")
    test = await _create_and_start(client, owner_token, org_id)
    await _track(client, owner_token, test["id"], "a", [1.0, 2.0])
    await _track(client, owner_token, test["id"], "b", [3.0, 4.0])

    json_response = await client.get(f"/ab-tests/{test['id']}/export?format=json", headers=_auth_header(owner_token))
    assert json_response.status_code == 200
    assert "attachment" in json_response.headers["content-disposition"]

    csv_response = await client.get(f"/ab-tests/{test['id']}/export?format=csv", headers=_auth_header(owner_token))
    assert csv_response.status_code == 200
    assert "conversion_rate" in csv_response.text
