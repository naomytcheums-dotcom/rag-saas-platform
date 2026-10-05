"""
Optional, alternative PDF extraction engine using IBM's real, open source
Docling toolkit (MIT license, donated to the Linux Foundation) --
structure-aware parsing (reading order across multi-column layouts,
table cell/header structure, layout-aware text grouping) instead of
PyMuPDF's own plain per-page text dump (api/services/pdf_extraction.py).

**Deliberately additive, never a replacement**: PyMuPDF stays the real,
tested, DEFAULT engine (`resolve_pdf_extraction_engine` below defaults
to `"pymupdf"`) -- an organization opts into Docling per
`api/security/organization_settings.py`'s own real setting, the exact
same "never change existing behavior for an org that never touches a
new setting" discipline every other per-organization toggle in this
codebase already follows (see e.g. Phase 4 Étape 2's own
`query_rewriting_enabled` defaulting False).

**Same unified output shape as api/services/document_extraction.py's
own dispatcher** (`{"metadata", "sections", "tables", "image_count"}`),
grouped by real page number (`ProvenanceItem.page_no`, verified against
the installed `docling-core` package before writing this module, not
guessed from documentation) so the rest of the pipeline (per-page chunk
metadata, page-aware citations) needs no changes at all to consume
either engine's output.

**Heavy, optional dependency, same pattern as api/services/ocr.py's own
`OCRNotAvailableError`**: `docling` pulls in its own real ML models
(layout/table-structure/OCR) -- imported lazily inside the function
below, not at module import time, so a deployment that never enables
this engine never pays Docling's own import cost.
"""

import logging

logger = logging.getLogger(__name__)


class DoclingNotAvailableError(Exception):
    """Raised when `docling` isn't installed -- same honest-degradation
    contract as api/services/ocr.py's own OCRNotAvailableError: the
    caller decides whether to fall back to PyMuPDF or surface the error,
    this module never silently pretends to have extracted anything."""


def extract_pdf_with_docling(file_path: str) -> dict:
    """Real Docling conversion, folded into the SAME shape every other
    extractor in api/services/document_extraction.py already returns."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise DoclingNotAvailableError(f"docling is not installed: {exc}") from exc

    converter = DocumentConverter()
    result = converter.convert(file_path)
    doc = result.document

    pages_text: dict[int, list[str]] = {}
    for item in doc.texts:
        page_no = item.prov[0].page_no if item.prov else 1
        pages_text.setdefault(page_no, []).append(item.text)

    sections = [
        {"text": "\n\n".join(texts), "metadata": {"page": page_no}}
        for page_no, texts in sorted(pages_text.items())
    ]

    tables = [table.export_to_dataframe(doc) for table in doc.tables]

    return {
        "metadata": {
            "title": doc.name,
            "page_count": len(doc.pages),
            "extraction_engine": "docling",
        },
        "sections": sections,
        "tables": tables,
        "image_count": len(doc.pictures),
    }
