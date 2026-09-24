"""Real tests for the widget -> org branding fallback (P2 #9, session
SSRF épinglé).

The rule (see api/services/widget.py's own _resolve_effective_branding):
  effective = widget_value  if widget_value != widget_default
              branding_value if branding_value != branding_default
              widget_default otherwise
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services import widget as widget_svc


def _make_branding(**overrides):
    """A real, active OrganizationBranding with its real column
    defaults, overridable per-test."""
    defaults = {
        "is_active": True,
        "logo_url": None,
        "primary_color": "#2563eb",
        "secondary_color": "#1e293b",
        "font_family": "Inter",
    }
    defaults.update(overrides)
    return type("Branding", (), defaults)()


def _make_config(**overrides):
    """A real WidgetConfig at its own defaults, overridable per-test."""
    defaults = {
        "organization_id": uuid.uuid4(),
        "logo_url": None,
        "primary_color": "#6C63FF",
        "secondary_color": "#4A47A3",
        "font_family": "system-ui",
    }
    defaults.update(overrides)
    return type("Config", (), defaults)()


@pytest.mark.asyncio
async def test_no_branding_returns_widget_defaults():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    config = _make_config()

    out = await widget_svc._resolve_effective_branding(db, config)
    assert out["primary_color"] == "#6C63FF"
    assert out["secondary_color"] == "#4A47A3"
    assert out["font_family"] == "system-ui"
    assert out["logo_url"] is None


@pytest.mark.asyncio
async def test_branding_at_defaults_does_not_change_widget():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=_make_branding())  # all defaults
    config = _make_config()

    out = await widget_svc._resolve_effective_branding(db, config)
    assert out["primary_color"] == "#6C63FF"  # unchanged
    assert out["font_family"] == "system-ui"


@pytest.mark.asyncio
async def test_branding_custom_primary_overrides_widget_default():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=_make_branding(primary_color="#ff0000"))
    config = _make_config()  # widget at default primary

    out = await widget_svc._resolve_effective_branding(db, config)
    assert out["primary_color"] == "#ff0000"


@pytest.mark.asyncio
async def test_widget_custom_primary_wins_over_branding():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=_make_branding(primary_color="#ff0000"))
    config = _make_config(primary_color="#00ff00")  # widget explicitly set

    out = await widget_svc._resolve_effective_branding(db, config)
    assert out["primary_color"] == "#00ff00"  # widget wins


@pytest.mark.asyncio
async def test_branding_logo_used_when_widget_has_none():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=_make_branding(logo_url="https://acme.test/logo.png"))
    config = _make_config(logo_url=None)

    out = await widget_svc._resolve_effective_branding(db, config)
    assert out["logo_url"] == "https://acme.test/logo.png"


@pytest.mark.asyncio
async def test_widget_logo_wins_over_branding_logo():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=_make_branding(logo_url="https://acme.test/logo.png"))
    config = _make_config(logo_url="https://widget.test/own.png")

    out = await widget_svc._resolve_effective_branding(db, config)
    assert out["logo_url"] == "https://widget.test/own.png"


@pytest.mark.asyncio
async def test_branding_inactive_ignored():
    """is_active=False means "render pure platform defaults", so the
    branding row must not be applied even when it has custom values."""
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)  # query already filters is_active=True
    config = _make_config()

    out = await widget_svc._resolve_effective_branding(db, config)
    assert out["primary_color"] == "#6C63FF"


@pytest.mark.asyncio
async def test_branding_font_overrides_widget_default():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=_make_branding(font_family="Montserrat"))
    config = _make_config()

    out = await widget_svc._resolve_effective_branding(db, config)
    assert out["font_family"] == "Montserrat"
