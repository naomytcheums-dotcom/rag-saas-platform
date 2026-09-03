"""
Partie 2.1.1 -- real PDF text/table/metadata/image extraction via
PyMuPDF, the exact library the master cahier des charges names for this
item ("2.1.1 | PDF | pymupdf (fitz)"). Imported as `pymupdf`, not the
classic `fitz` alias -- the installed version (1.28+) deprecates `fitz`
in favor of the real package name.

**Verified against a real generated PDF before writing a line of
processing code around it** (same discipline as every external
integration in this codebase): `page.find_tables()` genuinely detects
and extracts real tabular data (confirmed against a real drawn grid,
not assumed from the docs), so no separate table-extraction library
(pdfplumber, camelot) is needed -- PyMuPDF alone covers text, tables,
metadata, AND embedded images.

Every function here takes a real file PATH (this step's own literal
function signatures), not bytes -- api/security/documents.py's
process_pdf_document downloads a document's S3 bytes to a temp file
first, then calls these. A corrupt, empty, or non-PDF file raises
`pymupdf.FileDataError` (confirmed for real, including the
EmptyFileError subclass for a zero-byte file) -- translated here into
a plain ValueError, this module's only exception type, so callers never
need to know PyMuPDF's own exception hierarchy.
"""

import pymupdf


def _open(file_path: str) -> pymupdf.Document:
    try:
        return pymupdf.open(file_path)
    except pymupdf.FileDataError as exc:
        raise ValueError(f"'{file_path}' could not be opened as a valid PDF: {exc}") from exc


def extract_pdf_text(file_path: str) -> str:
    """Item 2's literal function -- every page's text, in order,
    separated by a form-feed so a caller can still tell where one page
    ended and the next began without needing extract_pdf_pages_text's
    own per-page list."""
    with _open(file_path) as doc:
        return "\f".join(page.get_text() for page in doc)


def extract_pdf_pages_text(file_path: str) -> list[str]:
    """Not in this step's literal function list, but a necessary
    building block, added deliberately rather than silently inlined:
    process_pdf_document chunks PER PAGE so each chunk's metadata can
    record which page it came from (this step's own DocumentChunk.metadata
    spec: "page, section, etc.") -- extract_pdf_text's single
    concatenated string can't answer that on its own."""
    with _open(file_path) as doc:
        return [page.get_text() for page in doc]


def extract_pdf_tables(file_path: str):
    """
    Item 2's literal function -- one pandas DataFrame per table found,
    across every page, via PyMuPDF's own real table-detection
    (`page.find_tables()`, verified for real above). Returns an empty
    list for a PDF with no tables -- a normal, expected outcome, not an
    error.
    """
    import pandas as pd

    tables = []
    with _open(file_path) as doc:
        for page in doc:
            for table in page.find_tables().tables:
                tables.append(pd.DataFrame(table.extract()))
    return tables


def extract_pdf_metadata(file_path: str) -> dict:
    """Item 2's literal function -- author/title/page count/etc.
    PyMuPDF's own metadata dict (title, author, subject, creator,
    producer, creation/mod dates -- empty string when the PDF's own
    Info dictionary never set a given field, not this function's own
    guess) plus page_count, which isn't part of PyMuPDF's metadata dict
    itself but is exactly the kind of thing this step's own spec asks
    for ("auteur, date, pages, etc.")."""
    with _open(file_path) as doc:
        return {**doc.metadata, "page_count": doc.page_count}


def extract_pdf_images(file_path: str) -> list[bytes]:
    """
    Item 2's literal function, explicitly marked optional in this
    step's own spec ("optionnel, pour OCR") -- every embedded raster
    image's raw bytes, across every page. process_pdf_document below
    only uses this to COUNT images for Document.metadata_json (an
    image_count field), not to store or OCR them -- actually running
    OCR on extracted images is real, separate work this step's spec
    explicitly did not ask to build.
    """
    images = []
    with _open(file_path) as doc:
        for page in doc:
            for image_info in page.get_images(full=True):
                xref = image_info[0]
                images.append(doc.extract_image(xref)["image"])
    return images
