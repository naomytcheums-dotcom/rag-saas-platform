"""
Partie 2.1.2, item 3 -- extract_document_content, the single entry
point api/security/documents.py's process_document calls regardless of
format. Real, structural coherence between PDF and DOCX (vision
critique Q1), not just similarly-named functions: both
api/services/pdf_extraction.py and api/services/docx_extraction.py
return their own format-specific pieces, and this dispatcher folds them
into ONE shared shape:

    {
        "metadata": dict,          # author/title/page_or_paragraph_count/etc.
        "sections": list[str],     # text grouped by the format's own
                                    # natural unit -- one entry per PAGE
                                    # for PDF, ONE entry (the whole
                                    # document) for DOCX, since a DOCX
                                    # file has no fixed pages at the
                                    # format level (pagination is a
                                    # Word rendering-time concern, not
                                    # stored in the XML) -- see
                                    # extract_docx_metadata's own
                                    # docstring.
        "tables": list[DataFrame],
        "image_count": int,        # 0 for DOCX -- no image-extraction
                                    # function was asked for DOCX by
                                    # this step's own spec.
    }

process_document chunks each "sections" entry independently (so a PDF's
chunk metadata still records its real page number; a DOCX's chunks
simply don't carry one, honestly, since there isn't one) -- the SAME
chunking/embedding code path handles both from this point on.
"""

from api.services.docx_extraction import extract_docx_metadata, extract_docx_tables, extract_docx_text
from api.services.pdf_extraction import extract_pdf_images, extract_pdf_metadata, extract_pdf_pages_text, extract_pdf_tables

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def extract_document_content(file_path: str, file_type: str) -> dict:
    """Item 3's literal function. Raises ValueError for a file_type
    neither api/services/pdf_extraction.py nor
    api/services/docx_extraction.py handles -- a caller bug (this
    should never happen in practice, since api/services/
    document_storage.py's validate_document_upload only ever accepts
    these same two types at upload time), not a recoverable per-
    document failure."""
    if file_type == PDF_CONTENT_TYPE:
        return {
            "metadata": extract_pdf_metadata(file_path),
            "sections": extract_pdf_pages_text(file_path),
            "tables": extract_pdf_tables(file_path),
            "image_count": len(extract_pdf_images(file_path)),
        }
    if file_type == DOCX_CONTENT_TYPE:
        return {
            "metadata": extract_docx_metadata(file_path),
            "sections": [extract_docx_text(file_path)],
            "tables": extract_docx_tables(file_path),
            "image_count": 0,
        }
    raise ValueError(f"Unsupported file type for content extraction: {file_type!r}")
