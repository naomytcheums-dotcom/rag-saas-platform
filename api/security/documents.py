"""
Partie 2.1.1/2.1.2/2.1.3/2.1.4/2.1.5/2.1.6/2.1.7/2.1.8 -- uploading a
PDF, DOCX, TXT, Markdown, HTML, CSV, JSON, or XML document and
processing it (real text/table/metadata extraction, real chunking,
real embeddings) into searchable DocumentChunk rows.

**One shared pipeline for every supported format, not a parallel one
per format** (2.1.2's own vision critique Q1 -- coherence, reconfirmed
by every format since): process_document below calls
api/services/document_extraction.py's extract_document_content
dispatcher, which returns the SAME shape (metadata/sections/tables/
image_count) regardless of underlying format -- chunking, embedding,
and DocumentChunk creation below never need to know which.

**Chunking** reimplements the same token-sliding-window algorithm
src/indexing.py already uses (character offsets from the tokenizer's
own offset_mapping, not decode() -- decode() re-joins sub-word pieces
with single spaces and destroys whitespace/indentation) -- independently,
not imported from src/, preserving this codebase's established
api/<->src/ boundary (api/ has zero import dependency on src/, see
api/security/organization_settings.py's own module docstring). Chunked
per SECTION -- each carrying its OWN per-section metadata dict (a PDF's
real page number; a Markdown section's real heading/level, Partie
2.1.4's own real semantic-chunking answer; DOCX/TXT/HTML/CSV/JSON/XML's
single whole-document section, empty metadata) rather than a document-wide
concatenated blob, so a chunk's metadata reflects exactly where in the
source document it came from, whatever that means for its own format.

**Embeddings, a real, deliberately bounded piece of Partie 4's own
scope**: organization_settings.embedding_model (Partie 1.3.9) already
defaults to "sentence-transformers/all-MiniLM-L6-v2" -- the exact model
src/indexing.py already uses -- but until this step, NOTHING in api/
ever read it (that gap was explicitly documented at 1.3.9's own
delivery). process_document below is the first real consumer:
it loads whichever model an organization has configured and generates
real embeddings for real. This is NOT the full multi-provider LLM/
Embedding abstraction Partie 4 specifies (4.1/4.2/4.3, still ⬜) --
swapping providers today still means changing this one function, not
calling a configured client through an abstraction layer -- but it is
real, working, per-organization-configurable embedding generation, not
a hardcoded stand-in.

sentence-transformers/torch are DEFERRED imports (inside the functions
that need them, not at module load time) -- importing this module (for
upload_document, or for anything that merely reads/lists documents)
should never force-load a multi-hundred-MB ML stack that a given call
path doesn't need.
"""

import datetime as dt
import logging
import os
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.workspace import Workspace
from api.security.organization_settings import get_org_settings
from api.services.document_extraction import (
    CSV_CONTENT_TYPE,
    DOCX_CONTENT_TYPE,
    HTML_CONTENT_TYPE,
    JSON_CONTENT_TYPE,
    MARKDOWN_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    TXT_CONTENT_TYPE,
    XML_CONTENT_TYPE,
    extract_document_content,
)
from api.services.document_storage import download_document_file, upload_document_file, validate_document_upload

_TEMP_FILE_SUFFIXES = {
    PDF_CONTENT_TYPE: ".pdf", DOCX_CONTENT_TYPE: ".docx", TXT_CONTENT_TYPE: ".txt",
    MARKDOWN_CONTENT_TYPE: ".md", HTML_CONTENT_TYPE: ".html", CSV_CONTENT_TYPE: ".csv",
    JSON_CONTENT_TYPE: ".json", XML_CONTENT_TYPE: ".xml",
}

logger = logging.getLogger(__name__)

# A model is loaded once per worker process and reused -- loading one
# is a real, multi-second disk/network operation (the first call for a
# given model downloads its weights from HuggingFace Hub if not
# already cached), far too slow to repeat per document.
_EMBEDDER_CACHE: dict[str, object] = {}


def _get_embedder(model_name: str):
    """Deferred import -- see this module's own docstring for why.
    Same USE_TF=0 trick as src/retrieval.py: transformers otherwise
    tries to also detect/load a TensorFlow backend that isn't installed
    here, which crashes the import outright."""
    if model_name not in _EMBEDDER_CACHE:
        os.environ.setdefault("USE_TF", "0")
        from sentence_transformers import SentenceTransformer

        _EMBEDDER_CACHE[model_name] = SentenceTransformer(model_name)
    return _EMBEDDER_CACHE[model_name]


def chunk_text(tokenizer, text: str, chunk_size: int, overlap: int) -> list[str]:
    """Same sliding-window-by-token-offsets algorithm as
    src/indexing.py's chunk_text_by_tokens, reimplemented independently
    here (see this module's own docstring on why, not imported)."""
    encoding = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = encoding["offset_mapping"]
    if not offsets:
        return []

    pieces = []
    step = max(chunk_size - overlap, 1)
    total_tokens = len(offsets)
    start = 0
    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        char_start = offsets[start][0]
        char_end = offsets[end - 1][1]
        piece = text[char_start:char_end].strip()
        if piece:
            pieces.append(piece)
        if end >= total_tokens:
            break
        start += step
    return pieces


def generate_embeddings(texts: list[str], model_name: str) -> list[list[float]]:
    """Real embeddings, via whichever model an organization has
    configured (organization_settings.embedding_model) -- see this
    module's own docstring for the honest scope of what this is (and
    isn't) relative to Partie 4."""
    embedder = _get_embedder(model_name)
    return embedder.encode(texts, batch_size=64).tolist()


async def upload_document(
    db: AsyncSession, organization_id: uuid.UUID, workspace_id: uuid.UUID | None,
    created_by: uuid.UUID, filename: str, content: bytes,
) -> Document:
    """
    Item 3's literal function. Real validation (size, actual PDF/DOCX/
    TXT/Markdown/HTML/CSV/JSON/XML content -- see api/services/document_storage.py's
    validate_document_upload, including why Markdown and CSV also need
    this call's own `filename`) BEFORE anything touches S3 or the
    database, so a bad upload never leaves a half-created row or an
    orphaned S3 object behind. A workspace_id, if given, must belong to
    this SAME organization -- otherwise an Owner of org A could file a
    document under org B's workspace_id, a real cross-tenant data-
    modeling risk this function closes at the point of creation, not
    left to a later query to accidentally get right.

    Does not commit -- same convention as every other security-layer
    write function in this codebase (the caller decides the transaction
    boundary). Dispatches the real Celery processing task best-effort
    (a broker hiccup must never fail the upload itself, same reasoning
    as api/security/custom_domains.py's schedule_domain_verification).
    """
    content_type = validate_document_upload(content, filename)

    if workspace_id is not None:
        workspace = await db.scalar(select(Workspace).where(Workspace.id == workspace_id, Workspace.organization_id == organization_id))
        if workspace is None:
            raise ValueError("workspace_id does not belong to this organization")

    document = Document(
        organization_id=organization_id, workspace_id=workspace_id, name=filename,
        file_key="", file_size=len(content), file_type=content_type,
        status=DocumentStatus.pending.value, created_by=created_by,
    )
    db.add(document)
    await db.flush()  # assigns document.id, needed for the S3 key below

    document.file_key = upload_document_file(organization_id, document.id, filename, content, content_type)
    await db.flush()

    schedule_document_processing(document.id)
    return document


def schedule_document_processing(document_id: uuid.UUID) -> None:
    """Real Celery dispatch, wrapped best-effort -- a broker hiccup at
    upload time must never fail the upload itself; the document simply
    stays `pending` until reprocessed (no automatic retry sweep exists
    for this in 2.1.1's own scope, unlike Partie 1.4.4's periodic
    domain-verification sweep -- a manual re-trigger is real future
    work, e.g. Partie 2.2.9's "Réindexation manuelle")."""
    from api.tasks.document_processing import process_document_task

    try:
        process_document_task.delay(str(document_id))
    except Exception as exc:  # noqa: BLE001 -- a broker hiccup must never break document upload
        logger.warning("schedule_document_processing: could not schedule processing for document '%s': %s", document_id, exc)


async def process_document(db: AsyncSession, document_id: uuid.UUID) -> Document:
    """
    Item 3's literal function (named process_pdf_document in 2.1.1,
    renamed here now that a second format exists -- a function still
    called "process_PDF_document" while actually processing a DOCX file
    would be actively misleading, not just imprecise) -- the real
    extraction + chunking + embedding pipeline, run by api/tasks/
    document_processing.py's Celery task, for EVERY supported format
    through the SAME code path (api/services/document_extraction.py's
    dispatcher). Transitions status pending -> processing -> completed/
    failed for real (never left stuck at `processing` forever): ANY
    failure along the way (a corrupt file, an S3 download error, an
    embedding error) is caught, recorded in Document.metadata_json, and
    ends in `failed` -- exactly this step's own vision critique answer
    to "que se passe-t-il si le fichier est corrompu" -- rather than
    crashing the Celery worker or leaving the document silently stuck.
    """
    document = await db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise ValueError(f"'{document_id}' is not a registered document")

    document.status = DocumentStatus.processing.value
    await db.flush()

    try:
        content = download_document_file(document.file_key)
        suffix = _TEMP_FILE_SUFFIXES.get(document.file_type, "")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            extracted = extract_document_content(tmp_path, document.file_type)

            settings_dict = await get_org_settings(db, document.organization_id)
            os.environ.setdefault("USE_TF", "0")
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(settings_dict["embedding_model"])

            # Each section carries its OWN per-format metadata dict
            # (api/services/document_extraction.py's own docstring --
            # a PDF's real page number, a Markdown section's real
            # heading/level, or {} for DOCX/TXT's single whole-document
            # section) -- every chunk sliced from that section inherits
            # it unchanged, so this loop never needs to know which
            # format it's chunking.
            chunk_records: list[dict] = []
            for section in extracted["sections"]:
                section_text = section["text"].strip()
                if not section_text:
                    continue
                for piece in chunk_text(tokenizer, section_text, settings_dict["chunk_size"], settings_dict["chunk_overlap"]):
                    chunk_records.append({"content": piece, "metadata": section["metadata"]})

            embeddings: list[list[float] | None] = [None] * len(chunk_records)
            if chunk_records:
                embeddings = generate_embeddings([c["content"] for c in chunk_records], settings_dict["embedding_model"])

            # Existing chunks (a re-run of a previously-processed
            # document) are replaced, not appended to -- otherwise
            # reprocessing would duplicate every chunk each time.
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
            for record, embedding in zip(chunk_records, embeddings):
                db.add(DocumentChunk(
                    document_id=document.id, content=record["content"],
                    metadata_json=record["metadata"] or None, embedding=embedding,
                ))

            document.metadata_json = {
                **extracted["metadata"], "table_count": len(extracted["tables"]),
                "image_count": extracted["image_count"], "chunk_count": len(chunk_records),
            }
            document.status = DocumentStatus.completed.value
            document.processed_at = dt.datetime.now(dt.timezone.utc)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("process_document: processing failed for document '%s': %s", document_id, exc)
        document.status = DocumentStatus.failed.value
        document.metadata_json = {**(document.metadata_json or {}), "error": str(exc)}

    await db.flush()
    return document
