"""
Partie 2.1.2/2.1.3/2.1.4, item 3 -- api/services/document_extraction.py's
extract_document_content dispatcher. Real PDF/DOCX/TXT/Markdown
generation and extraction, no mocking -- proves every format really
does come back through the SAME shared shape (vision critique Q1 --
coherence), including Markdown's own real per-section heading metadata.
"""

import docx
import pymupdf
import pytest

from api.services.document_extraction import (
    DOCX_CONTENT_TYPE,
    MARKDOWN_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    TXT_CONTENT_TYPE,
    extract_document_content,
)


@pytest.fixture
def real_pdf_path(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Real PDF dispatcher test content.")
    doc.set_metadata({"title": "Dispatcher PDF", "author": "pytest"})
    path = tmp_path / "dispatch.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def real_docx_path(tmp_path):
    document = docx.Document()
    document.core_properties.title = "Dispatcher DOCX"
    document.core_properties.author = "pytest"
    document.add_paragraph("Real DOCX dispatcher test content.")
    path = tmp_path / "dispatch.docx"
    document.save(str(path))
    return str(path)


@pytest.fixture
def real_txt_path(tmp_path):
    path = tmp_path / "dispatch.txt"
    # A real accented character (not pure ASCII) so encoding detection
    # has genuine UTF-8-specific signal to key off -- pure ASCII text is
    # ALSO trivially valid ASCII, a more specific match
    # charset-normalizer correctly prefers over "utf_8" (confirmed for
    # real: this is not a bug, ASCII is a strict subset of UTF-8).
    path.write_bytes("Réel contenu TXT dispatcher test.\nA second line.".encode("utf-8"))
    return str(path)


@pytest.fixture
def real_markdown_path(tmp_path):
    path = tmp_path / "dispatch.md"
    path.write_bytes((
        "---\ntitle: Dispatcher Markdown\n---\n\n"
        "# First Heading\n\nReal Markdown dispatcher test content.\n\n"
        "## Second Heading\n\nMore content under the second heading.\n"
    ).encode("utf-8"))
    return str(path)


def _assert_shared_shape(result: dict):
    """Every format must return the exact same top-level keys, with
    "sections" a list of {"text": str, "metadata": dict} entries -- this
    is what lets api/security/documents.py's process_document treat
    every format identically from this point on."""
    assert set(result.keys()) == {"metadata", "sections", "tables", "image_count"}
    assert isinstance(result["metadata"], dict)
    assert isinstance(result["sections"], list)
    for section in result["sections"]:
        assert set(section.keys()) == {"text", "metadata"}
        assert isinstance(section["text"], str)
        assert isinstance(section["metadata"], dict)
    assert isinstance(result["tables"], list)
    assert isinstance(result["image_count"], int)


def test_extract_document_content_dispatches_pdf_correctly(real_pdf_path):
    result = extract_document_content(real_pdf_path, PDF_CONTENT_TYPE)
    _assert_shared_shape(result)
    assert result["metadata"]["title"] == "Dispatcher PDF"
    assert len(result["sections"]) == 1  # one page
    assert "Real PDF dispatcher test content." in result["sections"][0]["text"]
    assert result["sections"][0]["metadata"] == {"page": 1}


def test_extract_document_content_dispatches_docx_correctly(real_docx_path):
    result = extract_document_content(real_docx_path, DOCX_CONTENT_TYPE)
    _assert_shared_shape(result)
    assert result["metadata"]["title"] == "Dispatcher DOCX"
    assert len(result["sections"]) == 1  # DOCX has no pages -- always exactly one section
    assert "Real DOCX dispatcher test content." in result["sections"][0]["text"]
    assert result["sections"][0]["metadata"] == {}
    assert result["image_count"] == 0  # no image extraction built for DOCX by this step


def test_extract_document_content_dispatches_txt_correctly(real_txt_path):
    result = extract_document_content(real_txt_path, TXT_CONTENT_TYPE)
    _assert_shared_shape(result)
    assert result["metadata"]["encoding"] == "utf_8"
    assert result["metadata"]["line_count"] == 2
    assert len(result["sections"]) == 1  # TXT has no pages either -- always exactly one section
    assert result["sections"][0]["text"] == "Réel contenu TXT dispatcher test.\nA second line."
    assert result["sections"][0]["metadata"] == {}
    assert result["tables"] == []
    assert result["image_count"] == 0


def test_extract_document_content_dispatches_markdown_correctly(real_markdown_path):
    """Partie 2.1.4's own validation criterion, and its real answer to
    vision critique Q2: Markdown sections carry REAL heading/level
    metadata, unlike DOCX/TXT's empty one -- genuinely wired into
    chunking, not just extracted and left unused."""
    result = extract_document_content(real_markdown_path, MARKDOWN_CONTENT_TYPE)
    _assert_shared_shape(result)
    assert result["metadata"]["title"] == "Dispatcher Markdown"
    assert result["metadata"]["heading_count"] == 2
    assert len(result["sections"]) == 2  # one per heading
    assert result["sections"][0]["metadata"] == {"heading": "First Heading", "level": 1}
    assert "Real Markdown dispatcher test content." in result["sections"][0]["text"]
    assert result["sections"][1]["metadata"] == {"heading": "Second Heading", "level": 2}
    assert "More content under the second heading." in result["sections"][1]["text"]
    assert result["image_count"] == 0


def test_extract_document_content_raises_for_an_unsupported_type(real_pdf_path):
    with pytest.raises(ValueError):
        extract_document_content(real_pdf_path, "text/html")
