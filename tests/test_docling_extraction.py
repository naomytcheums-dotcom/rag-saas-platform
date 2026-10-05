"""
api/services/docling_extraction.py -- Docling's own real `convert()`
downloads real ML models (layout/table-structure) on first use, a
genuinely different category from this codebase's own "no mocking"
precedent for pure, offline-cached extraction (PyMuPDF/python-docx/etc,
tests/test_document_extraction.py): a real conversion here would need
real network access this environment cannot guarantee, and would make
every future test run pay that cost again. Same real, documented
exception this codebase already makes for litellm.acompletion
(tests/test_llm_providers.py's own docstring) -- `DocumentConverter.convert`
is mocked, but every mock RETURNS the exact real shape verified directly
against the installed `docling-core` package before writing these tests
(DoclingDocument.model_fields, TableItem.export_to_dataframe's own real
signature, ProvenanceItem.page_no) -- never a fabricated shape.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from api.services.document_extraction import extract_document_content
from api.services.docling_extraction import extract_pdf_with_docling


def _fake_text_item(text: str, page_no: int) -> MagicMock:
    prov = MagicMock()
    prov.page_no = page_no
    item = MagicMock()
    item.text = text
    item.prov = [prov]
    return item


def _fake_table_item(dataframe: pd.DataFrame) -> MagicMock:
    table = MagicMock()
    table.export_to_dataframe.return_value = dataframe
    return table


def _fake_docling_document(texts, tables, pictures, name="report.pdf"):
    doc = MagicMock()
    doc.name = name
    doc.texts = texts
    doc.tables = tables
    doc.pictures = pictures
    doc.pages = {1: MagicMock(), 2: MagicMock()}
    return doc


def test_extract_pdf_with_docling_groups_text_by_real_page_number(monkeypatch):
    """Validation criterion: sections stay per-page (the same real
    granularity api/services/pdf_extraction.py's own extract_pdf_pages_text
    already gives), so the rest of the pipeline (per-page chunk metadata)
    needs no changes to consume either engine."""
    fake_doc = _fake_docling_document(
        texts=[
            _fake_text_item("Intro paragraph.", page_no=1),
            _fake_text_item("Second paragraph, same page.", page_no=1),
            _fake_text_item("Page two content.", page_no=2),
        ],
        tables=[],
        pictures=[],
    )
    fake_result = MagicMock(document=fake_doc)
    mock_converter = MagicMock()
    mock_converter.convert.return_value = fake_result
    monkeypatch.setattr(
        "docling.document_converter.DocumentConverter", lambda: mock_converter
    )

    extracted = extract_pdf_with_docling("/tmp/fake.pdf")

    assert extracted["sections"] == [
        {"text": "Intro paragraph.\n\nSecond paragraph, same page.", "metadata": {"page": 1}},
        {"text": "Page two content.", "metadata": {"page": 2}},
    ]
    assert extracted["metadata"]["extraction_engine"] == "docling"
    assert extracted["metadata"]["page_count"] == 2
    assert extracted["image_count"] == 0
    mock_converter.convert.assert_called_once_with("/tmp/fake.pdf")


def test_extract_pdf_with_docling_exports_real_tables_as_dataframes(monkeypatch):
    df = pd.DataFrame({"Name": ["Alice", "Bob"], "Score": [1, 2]})
    fake_doc = _fake_docling_document(texts=[], tables=[_fake_table_item(df)], pictures=[MagicMock(), MagicMock()])
    fake_result = MagicMock(document=fake_doc)
    mock_converter = MagicMock()
    mock_converter.convert.return_value = fake_result
    monkeypatch.setattr(
        "docling.document_converter.DocumentConverter", lambda: mock_converter
    )

    extracted = extract_pdf_with_docling("/tmp/fake.pdf")

    assert len(extracted["tables"]) == 1
    pd.testing.assert_frame_equal(extracted["tables"][0], df)
    assert extracted["image_count"] == 2


def test_extract_document_content_dispatches_to_docling_when_requested(monkeypatch):
    """Validation criterion: an organization that opts into
    pdf_extraction_engine="docling" gets routed through Docling, not
    PyMuPDF -- and one that never sets it (every other test in
    tests/test_document_extraction.py) is completely unaffected."""
    sentinel = {"metadata": {"extraction_engine": "docling"}, "sections": [], "tables": [], "image_count": 0}
    monkeypatch.setattr(
        "api.services.docling_extraction.extract_pdf_with_docling", lambda file_path: sentinel
    )

    result = extract_document_content("/tmp/fake.pdf", "application/pdf", pdf_engine="docling")

    assert result is sentinel


def test_extract_document_content_defaults_to_pymupdf_when_engine_not_passed():
    """No `pdf_engine` argument at all -- every pre-existing caller of
    this dispatcher -- must keep using PyMuPDF, never Docling."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Real PyMuPDF text, unaffected by Docling.")
    doc.save("/tmp/_docling_default_engine_test.pdf")
    doc.close()

    result = extract_document_content("/tmp/_docling_default_engine_test.pdf", "application/pdf")

    assert result["metadata"].get("extraction_engine") != "docling"
    assert "Real PyMuPDF text" in result["sections"][0]["text"]
