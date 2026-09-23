"""Phase 5, Étape 3 -- real email branding, closing a genuine gap the
White Label audit surfaced: OrganizationBranding's email_sender_name/
email_sender_email/logo_url were stored but never consumed by any
actual send_*_email function. api/services/email_branding.py wires
one real, representative call site (organization invitations) to
prove this now works -- see that module's own docstring for why the
other ~29 email functions are traced (ROADMAP.md), not migrated here.
"""

import uuid
from unittest.mock import patch

from api.models.organization import Organization
from api.models.organization_branding import OrganizationBranding
from api.services.email_branding import (
    compose_branded_from_address, get_active_branding, render_branded_footer, render_branded_header,
    send_branded_organization_invitation_email,
)


async def _make_org_with_branding(db_session, **branding_fields) -> uuid.UUID:
    org = Organization(name="Branded Org", slug=f"branded-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    branding = OrganizationBranding(organization_id=org.id, **branding_fields)
    db_session.add(branding)
    await db_session.commit()
    return org.id


async def test_get_active_branding_returns_none_when_no_row_exists(db_session):
    org = Organization(name="No Branding Org", slug=f"no-branding-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.commit()
    assert await get_active_branding(db_session, org.id) is None


async def test_get_active_branding_returns_none_when_is_active_false(db_session):
    org_id = await _make_org_with_branding(db_session, email_sender_name="Acme", email_sender_email="hi@acme.example", is_active=False)
    assert await get_active_branding(db_session, org_id) is None


def test_compose_branded_from_address_falls_back_to_platform_default_when_no_branding():
    from api.config import settings

    assert compose_branded_from_address(None) == settings.EMAIL_FROM_ADDRESS


def test_compose_branded_from_address_uses_real_sender_identity_when_configured():
    branding = OrganizationBranding(email_sender_name="Acme Support", email_sender_email="support@acme.example")
    assert compose_branded_from_address(branding) == "Acme Support <support@acme.example>"


def test_render_branded_header_includes_logo_when_set():
    branding = OrganizationBranding(logo_url="https://acme.example/logo.png")
    assert "https://acme.example/logo.png" in render_branded_header(branding)


def test_render_branded_header_empty_without_a_logo():
    assert render_branded_header(None) == ""


def test_render_branded_footer_includes_org_contact_when_configured():
    branding = OrganizationBranding(company_email="hello@acme.example")
    footer = render_branded_footer(branding)
    assert "hello@acme.example" in footer


async def test_invitation_email_uses_the_orgs_real_branded_sender_and_logo(db_session):
    org_id = await _make_org_with_branding(
        db_session, email_sender_name="Acme Support", email_sender_email="support@acme.example", logo_url="https://acme.example/logo.png",
    )

    with patch("api.services.email_branding._send") as mock_send:
        await send_branded_organization_invitation_email(db_session, org_id, "newmember@example.com", "member", "https://app.example/accept?token=abc")

    mock_send.assert_called_once()
    args = mock_send.call_args.args
    assert args[0] == "newmember@example.com"
    assert "https://acme.example/logo.png" in args[2]
    assert args[3] == "Acme Support <support@acme.example>"


async def test_invitation_email_falls_back_to_platform_default_without_branding(db_session):
    from api.config import settings

    org = Organization(name="Plain Org", slug=f"plain-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.commit()

    with patch("api.services.email_branding._send") as mock_send:
        await send_branded_organization_invitation_email(db_session, org.id, "newmember@example.com", "member", "https://app.example/accept?token=abc")

    assert mock_send.call_args.args[3] == settings.EMAIL_FROM_ADDRESS
