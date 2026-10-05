"""Hardening Mission, Phase 2 -- REGRESSION for a real, confirmed audit
gap: OPA/policy-aware retrieval (api.services.policy_aware_retrieval)
was already correctly wired INSIDE api.services.retrieval_pipeline.search
(gated on `user_context is not None`), but no real HTTP caller ever
built and passed a `user_context` at all -- so the feature had zero
observable effect in production for ANY organization, configured or
not. This test proves the real, concrete fix: `/chat/stream`'s own
`_stream_response` now builds a real `user_context` from the
authenticated caller's own real membership and passes it through to
`search_with_context`.

Mocked at the same clean boundary tests/test_streaming.py already
established for this router (litellm's own real streaming call, the
genuinely external part) -- the real thing under test here is the
`user_context` argument `_stream_response` passes, not retrieval or
generation themselves (both already covered elsewhere)."""

import uuid
from unittest.mock import AsyncMock, patch

from api.models.agent import Agent
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.routers.chat_stream import _stream_response


async def _make_org_agent_and_member(db_session, role: OrganizationRole = OrganizationRole.member):
    org = Organization(name="Policy Org", slug=f"policy-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    agent = Agent(organization_id=org.id, name="Bot", system_prompt="You are helpful.")
    db_session.add(agent)
    await db_session.flush()
    return org, agent


async def test_stream_response_passes_a_real_user_context_to_search_with_context(db_session, register_payload):
    """AUDIT REGRESSION -- user_context used to never be built/passed at
    all from this real, authenticated HTTP route."""
    from sqlalchemy import select

    from api.models.user import User

    email = register_payload["email"]
    # A real, committed user row is required (FK), reusing this
    # project's own existing register_payload fixture shape rather than
    # going through the full /auth/register HTTP flow (out of scope for
    # this focused wiring test -- auth itself is covered elsewhere).
    user = User(email=email, hashed_password="x", full_name="Test User", is_email_verified=True)
    db_session.add(user)
    await db_session.flush()

    org, agent = await _make_org_agent_and_member(db_session)
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrganizationRole.manager))
    await db_session.commit()

    fake_search = AsyncMock(return_value=[])
    with (
        patch("api.routers.chat_stream.search_with_context", fake_search),
        patch("api.routers.chat_stream.stream_agent_response", lambda *a, **k: _empty_async_gen()),
    ):
        response = await _stream_response(agent.id, "hello", None, user, db_session)
        assert response is not None

    fake_search.assert_awaited_once()
    _, kwargs = fake_search.await_args
    assert kwargs["user_context"] == {"user_id": str(user.id), "organization_id": str(org.id), "role": "manager"}


async def _empty_async_gen():
    return
    yield  # pragma: no cover -- makes this a real async generator
