"""PDFs are built from HTML by WeasyPrint, which fetches whatever the markup points to (and embeds `<link rel="attachment">` files).
User-controlled values must be escaped and no external fetch may be possible. WeasyPrint's native libraries are not installed on every
machine, so a fake `weasyprint` module records exactly what the application hands it."""

import datetime as dt
import sys
import types
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from api.services.pdf_safety import deny_all_url_fetcher, esc

ATTACK = '</title><link rel="attachment" href="file:///etc/passwd"><img src="http://169.254.169.254/latest/meta-data/">'


@pytest.fixture
def fake_weasyprint(monkeypatch):
    seen = {}

    class _HTML:
        def __init__(self, string=None, url_fetcher=None, **kwargs):
            seen["html"], seen["url_fetcher"], seen["kwargs"] = string, url_fetcher, kwargs

        def write_pdf(self):
            return b"%PDF-fake"

    module = types.ModuleType("weasyprint")
    module.HTML = _HTML
    monkeypatch.setitem(sys.modules, "weasyprint", module)
    return seen


def test_esc_neutralises_markup_and_handles_none():
    assert esc(ATTACK) == "&lt;/title&gt;&lt;link rel=&quot;attachment&quot; href=&quot;file:///etc/passwd&quot;&gt;&lt;img src=&quot;http://169.254.169.254/latest/meta-data/&quot;&gt;"
    assert esc(None) == "" and esc(12) == "12"


def test_the_fetcher_refuses_every_resource():
    for url in ("file:///etc/passwd", "http://localhost:8000/admin", "https://example.com/a.css", "data:text/plain,hi"):
        with pytest.raises(ValueError, match="disabled"):
            deny_all_url_fetcher(url)


async def test_a_conversation_pdf_escapes_the_title_and_blocks_external_fetches(fake_weasyprint, monkeypatch):
    from api.services import conversation_export

    conversation = SimpleNamespace(id=uuid.uuid4(), title=ATTACK, created_at=dt.datetime(2026, 1, 1), updated_at=dt.datetime(2026, 1, 1), agent_id="a")
    message = SimpleNamespace(id=uuid.uuid4(), role="user", content="hello", created_at=dt.datetime(2026, 1, 1), tool_calls=None, tool_call_id=None)
    monkeypatch.setattr(conversation_export, "_load_owned_conversation_with_messages", AsyncMock(return_value=(conversation, [message])))

    pdf = await conversation_export.export_to_pdf(None, conversation.id, uuid.uuid4())

    assert pdf == b"%PDF-fake"
    assert 'rel="attachment"' not in fake_weasyprint["html"] and "<link" not in fake_weasyprint["html"]
    assert "&lt;/title&gt;" in fake_weasyprint["html"]
    assert fake_weasyprint["url_fetcher"] is deny_all_url_fetcher


async def test_an_invoice_pdf_escapes_the_organization_name_and_line_descriptions(fake_weasyprint, monkeypatch):
    from api.models.billing import InvoiceStatus
    from api.services import billing_invoices

    invoice = SimpleNamespace(
        number="INV-1", status=InvoiceStatus.paid if hasattr(InvoiceStatus, "paid") else SimpleNamespace(value="paid"), due_date=dt.date(2026, 2, 1),
        subtotal_cents=1000, currency="EUR", vat_rate=20, vat_cents=200, total_cents=1200,
    )
    line = SimpleNamespace(description=ATTACK, quantity=1, unit_price_cents=1000, total_cents=1000)
    monkeypatch.setattr(billing_invoices, "get_invoice", AsyncMock(return_value=invoice))
    monkeypatch.setattr(billing_invoices, "get_invoice_lines", AsyncMock(return_value=[line]))
    db = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(name=ATTACK)))

    pdf = await billing_invoices.generate_invoice_pdf(db, uuid.uuid4(), uuid.uuid4())

    assert pdf == b"%PDF-fake"
    assert "<link" not in fake_weasyprint["html"] and "<img src=" not in fake_weasyprint["html"]
    assert fake_weasyprint["html"].count("&lt;link") == 2  # once in the organization name, once in the line description
    assert fake_weasyprint["url_fetcher"] is deny_all_url_fetcher
