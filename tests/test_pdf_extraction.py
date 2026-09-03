"""
Partie 2.1.1 -- real PDF extraction tests (api/services/pdf_extraction.py).
No mocking here: PyMuPDF itself both GENERATES the test PDFs (drawing
real text/table grids) and EXTRACTS from them, the same way this
module's own docstring was verified before being written -- a real
round trip, not an assumption about what the library returns.
"""

import pymupdf
import pytest

from api.services.pdf_extraction import (
    extract_pdf_images,
    extract_pdf_metadata,
    extract_pdf_pages_text,
    extract_pdf_tables,
    extract_pdf_text,
)


@pytest.fixture
def real_pdf_path(tmp_path):
    """A real, two-page PDF: page 1 has real text plus a real
    grid-drawn table, page 2 has different real text -- built with
    PyMuPDF itself, saved to a real temp file (these functions take a
    file PATH, this step's own literal signature)."""
    doc = pymupdf.open()

    page1 = doc.new_page()
    page1.insert_text((72, 72), "Hello World, this is real page one text.")
    x0, y0, cell_w, cell_h = 72, 120, 100, 20
    rows, cols = 3, 2
    for r in range(rows + 1):
        page1.draw_line((x0, y0 + r * cell_h), (x0 + cols * cell_w, y0 + r * cell_h))
    for c in range(cols + 1):
        page1.draw_line((x0 + c * cell_w, y0), (x0 + c * cell_w, y0 + rows * cell_h))
    labels = [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]
    for r in range(rows):
        for c in range(cols):
            page1.insert_text((x0 + c * cell_w + 5, y0 + r * cell_h + 14), labels[r][c], fontsize=9)

    page2 = doc.new_page()
    page2.insert_text((72, 72), "This is real page two, with different content entirely.")

    doc.set_metadata({"title": "Real Test Document", "author": "pytest"})
    path = tmp_path / "real_test.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def corrupt_pdf_path(tmp_path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"this is not a real pdf, just garbage bytes")
    return str(path)


@pytest.fixture
def empty_pdf_path(tmp_path):
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"")
    return str(path)


# ------------------------------------------------------------------- text --

def test_extract_pdf_text_returns_real_text_from_both_pages(real_pdf_path):
    """Validation criterion: text extraction works."""
    text = extract_pdf_text(real_pdf_path)
    assert "Hello World, this is real page one text." in text
    assert "This is real page two, with different content entirely." in text


def test_extract_pdf_pages_text_returns_one_entry_per_page(real_pdf_path):
    pages = extract_pdf_pages_text(real_pdf_path)
    assert len(pages) == 2
    assert "page one" in pages[0]
    assert "page two" in pages[1]


def test_extract_pdf_text_raises_a_clear_error_for_a_corrupt_pdf(corrupt_pdf_path):
    """Vision critique Q3 -- what happens with a corrupted PDF: a clear
    ValueError, not an unhandled PyMuPDF-specific exception."""
    with pytest.raises(ValueError):
        extract_pdf_text(corrupt_pdf_path)


def test_extract_pdf_text_raises_a_clear_error_for_an_empty_file(empty_pdf_path):
    with pytest.raises(ValueError):
        extract_pdf_text(empty_pdf_path)


# ----------------------------------------------------------------- tables --

def test_extract_pdf_tables_finds_the_real_drawn_table(real_pdf_path):
    """Validation criterion: table extraction works."""
    tables = extract_pdf_tables(real_pdf_path)
    assert len(tables) == 1
    df = tables[0]
    assert df.shape == (3, 2)
    assert df.iloc[0].tolist() == ["Name", "Age"]
    assert df.iloc[1].tolist() == ["Alice", "30"]


def test_extract_pdf_tables_returns_empty_list_when_there_are_none(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Just plain text, no tables here.")
    path = tmp_path / "no_tables.pdf"
    doc.save(str(path))
    doc.close()

    assert extract_pdf_tables(str(path)) == []


def test_extract_pdf_tables_raises_for_a_corrupt_pdf(corrupt_pdf_path):
    with pytest.raises(ValueError):
        extract_pdf_tables(corrupt_pdf_path)


# --------------------------------------------------------------- metadata --

def test_extract_pdf_metadata_returns_the_real_title_author_and_page_count(real_pdf_path):
    """Validation criterion: metadata is extracted (author, title, pages)."""
    metadata = extract_pdf_metadata(real_pdf_path)
    assert metadata["title"] == "Real Test Document"
    assert metadata["author"] == "pytest"
    assert metadata["page_count"] == 2


def test_extract_pdf_metadata_raises_for_a_corrupt_pdf(corrupt_pdf_path):
    with pytest.raises(ValueError):
        extract_pdf_metadata(corrupt_pdf_path)


# ----------------------------------------------------------------- images --

def test_extract_pdf_images_returns_empty_list_when_there_are_none(real_pdf_path):
    """This step's own spec marks image extraction optional -- a PDF
    with no embedded images (text/vector-drawn only, like this fixture)
    is the normal case, not an error."""
    assert extract_pdf_images(real_pdf_path) == []


def test_extract_pdf_images_finds_a_real_embedded_image(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    # A tiny real 1x1 PNG (real magic bytes + minimal valid structure),
    # inserted as a genuine embedded image, not a vector drawing.
    png_1x1 = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    page.insert_image(pymupdf.Rect(10, 10, 60, 60), stream=png_1x1)
    path = tmp_path / "with_image.pdf"
    doc.save(str(path))
    doc.close()

    images = extract_pdf_images(str(path))
    assert len(images) == 1
    assert isinstance(images[0], bytes)
    assert len(images[0]) > 0


def test_extract_pdf_images_raises_for_a_corrupt_pdf(corrupt_pdf_path):
    with pytest.raises(ValueError):
        extract_pdf_images(corrupt_pdf_path)
