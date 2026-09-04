"""
Partie 2.1.2/2.1.3/2.1.4/2.1.5/2.1.6/2.1.7/2.1.8/2.1.9, item 3 --
extract_document_content, the single entry point
api/security/documents.py's process_document calls regardless of
format. Real, structural coherence across every supported format
(vision critique Q1), not just similarly-named functions: each
format's own extraction module returns its own format-specific pieces,
and this dispatcher folds them into ONE shared shape:

    {
        "metadata": dict,          # author/title/page_or_paragraph_count/
                                    # encoding/heading_count/links/
                                    # delimiter/row_count/key_count/
                                    # depth/structure/root/element_count/
                                    # attribute_count/has_nested_elements/
                                    # publisher/language/date/toc/etc.
        "sections": list[dict],    # [{"text": str, "metadata": dict}, ...]
                                    # -- text grouped by the format's own
                                    # natural unit, each carrying its OWN
                                    # per-section metadata: {"page": N}
                                    # for PDF, {"heading": str|None,
                                    # "level": int|None} for Markdown
                                    # (Partie 2.1.4 -- real heading-based
                                    # sectioning, not a single blob),
                                    # {"chapter": str} for EPUB (Partie
                                    # 2.1.9 -- the SAME real, natural-
                                    # boundary sectioning Markdown's
                                    # own heading-based split pioneered,
                                    # applied to EPUB's own real
                                    # chapters), or {} for DOCX/TXT/
                                    # HTML/CSV/JSON/XML's single
                                    # whole-document section (none of
                                    # the six has a natural
                                    # sub-division this codebase's spec
                                    # asked to preserve).
        "tables": list[DataFrame],  # a CSV's own real DataFrame lands
                                    # here too (Partie 2.1.6) -- a CSV
                                    # IS fundamentally one table, not a
                                    # format needing its own separate
                                    # top-level concept. Empty for
                                    # JSON/XML/EPUB -- none of the
                                    # three is generally tabular the
                                    # way a CSV always is, and this
                                    # step's own spec never asked for a
                                    # dict/tree/book -> DataFrame
                                    # conversion.
        "image_count": int,        # 0 for DOCX/TXT/Markdown/HTML/CSV/
                                    # JSON/XML/EPUB -- no image-
                                    # extraction function was asked for
                                    # any of them by this codebase's
                                    # spec.
    }

**A real, deliberate generalization from 2.1.1-2.1.3's own shape**,
motivated directly by Markdown's real structure (see
api/services/markdown_extraction.py's own module docstring): PDF's
"page" and Markdown's "heading"/"level" are now both just entries in a
per-section metadata dict, rather than PDF's page number being a
special-cased top-level concept. process_document chunks each
section's text independently and tags every chunk sliced from it with
that SAME metadata dict, unchanged -- the SAME chunking/embedding code
path handles every format from this point on, never needing to know
which one it's processing.

**HTML's extracted links** (api/services/html_extraction.py's
extract_html_links -- that step's own optional item 2 function) land
under `metadata["links"]`, the same place every other format's
format-specific extras already live (TXT's encoding/line_count,
Markdown's frontmatter/heading_count, CSV's delimiter/row_count/
column_count/columns, JSON's key_count/depth/structure, XML's root/
element_count/attribute_count/depth/has_attributes/has_nested_elements,
EPUB's publisher/language/date/toc) -- not a new top-level key just
for one format.

**EPUB uses `extract_epub_chapters` for its sections, not
`extract_epub_text`** -- the same real, natural-chapter-boundary
sectioning choice Partie 2.1.4 made for Markdown's own heading
boundaries, not the single-whole-document-section treatment every
other format here gets. `api/services/epub_extraction.py`'s own
`extract_epub_text` still exists as its own real, independently useful
function (a single flat string), exactly like `extract_markdown_text`
does alongside `extract_markdown_sections`.
"""

from api.services.csv_extraction import extract_csv_data, extract_csv_metadata, extract_csv_text
from api.services.docx_extraction import extract_docx_metadata, extract_docx_tables, extract_docx_text
from api.services.epub_extraction import extract_epub_chapters, extract_epub_metadata, extract_epub_toc
from api.services.html_extraction import extract_html_content, extract_html_links, extract_html_metadata, extract_tables_html
from api.services.json_extraction import extract_json_metadata, extract_json_text
from api.services.markdown_extraction import (
    extract_markdown_metadata,
    extract_markdown_sections,
    extract_markdown_tables,
)
from api.services.pdf_extraction import extract_pdf_images, extract_pdf_metadata, extract_pdf_pages_text, extract_pdf_tables
from api.services.txt_extraction import detect_encoding, extract_txt_text
from api.services.xml_extraction import extract_xml_metadata, extract_xml_structure, extract_xml_text

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT_CONTENT_TYPE = "text/plain"
MARKDOWN_CONTENT_TYPE = "text/markdown"
HTML_CONTENT_TYPE = "text/html"
CSV_CONTENT_TYPE = "text/csv"
JSON_CONTENT_TYPE = "application/json"
XML_CONTENT_TYPE = "application/xml"
EPUB_CONTENT_TYPE = "application/epub+zip"


def extract_document_content(file_path: str, file_type: str) -> dict:
    """Item 3's literal function. Raises ValueError for a file_type
    none of this codebase's extraction modules handle -- a caller bug
    (this should never happen in practice, since api/services/
    document_storage.py's validate_document_upload only ever accepts
    these same nine types at upload time), not a recoverable
    per-document failure."""
    if file_type == PDF_CONTENT_TYPE:
        return {
            "metadata": extract_pdf_metadata(file_path),
            "sections": [{"text": text, "metadata": {"page": i}} for i, text in enumerate(extract_pdf_pages_text(file_path), start=1)],
            "tables": extract_pdf_tables(file_path),
            "image_count": len(extract_pdf_images(file_path)),
        }
    if file_type == DOCX_CONTENT_TYPE:
        return {
            "metadata": extract_docx_metadata(file_path),
            "sections": [{"text": extract_docx_text(file_path), "metadata": {}}],
            "tables": extract_docx_tables(file_path),
            "image_count": 0,
        }
    if file_type == TXT_CONTENT_TYPE:
        text = extract_txt_text(file_path)
        return {
            "metadata": {"encoding": detect_encoding(file_path), "line_count": text.count("\n") + 1 if text else 0},
            "sections": [{"text": text, "metadata": {}}],
            "tables": [],
            "image_count": 0,
        }
    if file_type == MARKDOWN_CONTENT_TYPE:
        return {
            "metadata": extract_markdown_metadata(file_path),
            "sections": [
                {"text": s["text"], "metadata": {k: v for k, v in (("heading", s["heading"]), ("level", s["level"])) if v is not None}}
                for s in extract_markdown_sections(file_path)
            ],
            "tables": extract_markdown_tables(file_path),
            "image_count": 0,
        }
    if file_type == HTML_CONTENT_TYPE:
        metadata = extract_html_metadata(file_path)
        metadata["links"] = extract_html_links(file_path)
        return {
            "metadata": metadata,
            "sections": [{"text": extract_html_content(file_path), "metadata": {}}],
            # Partie 3.1.4 -- real HTML table extraction, filling in
            "tables": extract_tables_html(file_path),
            "image_count": 0,
        }
    if file_type == CSV_CONTENT_TYPE:
        return {
            "metadata": extract_csv_metadata(file_path),
            "sections": [{"text": extract_csv_text(file_path), "metadata": {}}],
            "tables": [extract_csv_data(file_path)],
            "image_count": 0,
        }
    if file_type == JSON_CONTENT_TYPE:
        return {
            "metadata": extract_json_metadata(file_path),
            "sections": [{"text": extract_json_text(file_path), "metadata": {}}],
            "tables": [],
            "image_count": 0,
        }
    if file_type == XML_CONTENT_TYPE:
        metadata = extract_xml_metadata(file_path)
        structure = extract_xml_structure(file_path)
        metadata["has_attributes"] = structure["has_attributes"]
        metadata["has_nested_elements"] = structure["has_nested_elements"]
        return {
            "metadata": metadata,
            "sections": [{"text": extract_xml_text(file_path), "metadata": {}}],
            "tables": [],
            "image_count": 0,
        }
    if file_type == EPUB_CONTENT_TYPE:
        metadata = extract_epub_metadata(file_path)
        metadata["toc"] = extract_epub_toc(file_path)
        return {
            "metadata": metadata,
            "sections": [
                {"text": chapter["text"], "metadata": {"chapter": chapter["title"]} if chapter["title"] else {}}
                for chapter in extract_epub_chapters(file_path)
            ],
            "tables": [],
            "image_count": 0,
        }
    raise ValueError(f"Unsupported file type for content extraction: {file_type!r}")
