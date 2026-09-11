"""Partie 16 (ter) -- reviews: submit/upsert, rating summary, list,
delete (owner-only). See tests/test_plugins.py's own top docstring for
the file-split rationale."""

import pytest

from plugin_test_helpers import _auth_header, _mock_s3_fixture, _publish_and_approve, _register_and_create_org

_mock_s3 = pytest.fixture(autouse=True)(_mock_s3_fixture)


async def test_submit_review_and_rating_summary(client, db_session, register_payload):
    token, org_id, plugin_id = await _publish_and_approve(client, db_session, register_payload, name="Reviewed Plugin")

    review = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/reviews", json={"rating": 4, "comment": "Pretty good"}, headers=_auth_header(token))
    assert review.status_code == 201

    # Re-reviewing the SAME plugin as the SAME user updates in place, not a second row.
    updated_review = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/reviews", json={"rating": 5, "comment": "Actually great"}, headers=_auth_header(token))
    assert updated_review.status_code == 201

    reviews = await client.get(f"/marketplace/plugins/{plugin_id}/reviews")
    assert len(reviews.json()) == 1
    assert reviews.json()[0]["rating"] == 5

    summary = await client.get(f"/marketplace/plugins/{plugin_id}/rating")
    assert summary.json() == {"average_rating": 5.0, "review_count": 1}


async def test_submit_review_rejects_invalid_rating(client, db_session, register_payload):
    token, org_id, plugin_id = await _publish_and_approve(client, db_session, register_payload, name="Rating Bounds Plugin")

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/reviews", json={"rating": 9}, headers=_auth_header(token))
    assert response.status_code == 400


async def test_rating_summary_averages_multiple_real_reviewers(client, db_session, register_payload):
    token, org_id, plugin_id = await _publish_and_approve(client, db_session, register_payload, name="Multi Reviewer Plugin")
    await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/reviews", json={"rating": 3}, headers=_auth_header(token))

    other_token, other_org_id = await _register_and_create_org(client, {**register_payload, "email": "reviewer2@example.com"})
    await client.post(f"/organizations/{other_org_id}/plugins/{plugin_id}/reviews", json={"rating": 5}, headers=_auth_header(other_token))

    summary = await client.get(f"/marketplace/plugins/{plugin_id}/rating")
    assert summary.json() == {"average_rating": 4.0, "review_count": 2}


async def test_delete_review_requires_ownership(client, db_session, register_payload):
    token, org_id, plugin_id = await _publish_and_approve(client, db_session, register_payload, name="Deletable Review Plugin")
    review = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/reviews", json={"rating": 3, "comment": "meh"}, headers=_auth_header(token))
    review_id = review.json()["id"]

    other_token, _other_org_id = await _register_and_create_org(client, {**register_payload, "email": "not-the-owner@example.com"})
    forbidden = await client.delete(f"/marketplace/reviews/{review_id}", headers=_auth_header(other_token))
    assert forbidden.status_code == 403

    allowed = await client.delete(f"/marketplace/reviews/{review_id}", headers=_auth_header(token))
    assert allowed.status_code == 204

    reviews_after = await client.get(f"/marketplace/plugins/{plugin_id}/reviews")
    assert reviews_after.json() == []
