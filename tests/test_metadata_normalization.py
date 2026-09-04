"""
Partie 2.2.5 -- fast-tier tests for api/services/metadata_normalization.py.
Pure, real, no mocking of any kind needed -- every test feeds a real,
hand-built per-format metadata dict (the exact shape each real
extractor already produces, per that module's own docstring) straight
into normalize_document_metadata.
"""

from api.services.document_extraction import (
    CSV_CONTENT_TYPE,
    DOCX_CONTENT_TYPE,
    EPUB_CONTENT_TYPE,
    HTML_CONTENT_TYPE,
    JSON_CONTENT_TYPE,
    MARKDOWN_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    TXT_CONTENT_TYPE,
    XML_CONTENT_TYPE,
)
from api.services.metadata_normalization import normalize_document_metadata


def test_normalizes_a_real_pdf_date_and_splits_real_keywords():
    """Validation criterion: extraction/normalisation fonctionne pour
    PDF, y compris la date réelle au format spec PDF."""
    metadata = {
        "title": "My PDF", "author": "Jane Doe", "creator": "Microsoft Word",
        "creationDate": "D:20230115143000+00'00'", "keywords": "alpha, beta;gamma", "page_count": 5,
    }
    result = normalize_document_metadata(metadata, PDF_CONTENT_TYPE)
    assert result["title"] == "My PDF"
    assert result["author"] == "Jane Doe"
    assert result["created_date"] == "2023-01-15T14:30:00"
    assert result["keywords"] == ["alpha", "beta", "gamma"]
    assert result["raw"] == metadata


def test_pdf_creator_is_never_treated_as_a_real_author_fallback():
    """A real, deliberate distinction -- PDF's own `creator` field is
    the authoring SOFTWARE (e.g. 'Microsoft Word'), never a person."""
    result = normalize_document_metadata({"creator": "Microsoft Word"}, PDF_CONTENT_TYPE)
    assert result["author"] is None


def test_pdf_date_parsing_handles_a_real_partial_date_and_a_bad_one():
    assert normalize_document_metadata({"creationDate": "D:2023"}, PDF_CONTENT_TYPE)["created_date"] == "2023-01-01T00:00:00"
    assert normalize_document_metadata({"creationDate": ""}, PDF_CONTENT_TYPE)["created_date"] is None
    assert normalize_document_metadata({"creationDate": "not a real pdf date"}, PDF_CONTENT_TYPE)["created_date"] is None
    assert normalize_document_metadata({}, PDF_CONTENT_TYPE)["created_date"] is None


def test_normalizes_real_docx_metadata():
    """Validation criterion: extraction/normalisation fonctionne pour
    DOCX."""
    metadata = {"title": "My Doc", "author": "John", "keywords": "x; y", "created": "2023-01-01T00:00:00", "paragraph_count": 10}
    result = normalize_document_metadata(metadata, DOCX_CONTENT_TYPE)
    assert result["title"] == "My Doc"
    assert result["author"] == "John"
    assert result["created_date"] == "2023-01-01T00:00:00"
    assert result["keywords"] == ["x", "y"]


def test_normalizes_real_epub_metadata_with_its_own_real_list_shapes():
    """Validation criterion: extraction/normalisation fonctionne pour
    EPUB, y compris ses vrais champs multi-valeurs (author/subject)."""
    metadata = {"title": "A Book", "author": ["A", "B"], "subject": ["Fiction", "Adventure"], "date": "2020"}
    result = normalize_document_metadata(metadata, EPUB_CONTENT_TYPE)
    assert result["title"] == "A Book"
    assert result["author"] == ["A", "B"]
    assert result["created_date"] == "2020"
    assert result["keywords"] == ["Fiction", "Adventure"]


def test_normalizes_real_html_metadata():
    metadata = {"title": "My Page", "author": "Jane", "date": "2024-01-01", "keywords": "alpha, beta"}
    result = normalize_document_metadata(metadata, HTML_CONTENT_TYPE)
    assert result["created_date"] == "2024-01-01"
    assert result["keywords"] == ["alpha", "beta"]


def test_normalizes_real_markdown_frontmatter_tags_not_keywords():
    """A real, deliberate distinction -- Markdown frontmatter's own
    conventional key is `tags`, not `keywords`."""
    metadata = {"title": "Post", "author": "Me", "tags": ["x", "y"], "date": "2024-01-01"}
    result = normalize_document_metadata(metadata, MARKDOWN_CONTENT_TYPE)
    assert result["keywords"] == ["x", "y"]
    assert result["created_date"] == "2024-01-01"


def test_markdown_tags_as_a_bare_string_are_still_split():
    result = normalize_document_metadata({"tags": "x, y"}, MARKDOWN_CONTENT_TYPE)
    assert result["keywords"] == ["x", "y"]


def test_formats_with_no_real_metadata_concept_report_honest_none_and_empty_list():
    """Validation criterion / vision critique 3: pas de métadonnées
    fabriquées quand le format n'en a réellement aucune."""
    for content_type in (CSV_CONTENT_TYPE, JSON_CONTENT_TYPE, XML_CONTENT_TYPE, TXT_CONTENT_TYPE):
        result = normalize_document_metadata({"row_count": 5}, content_type)
        assert result["title"] is None
        assert result["author"] is None
        assert result["created_date"] is None
        assert result["keywords"] == []


def test_handles_a_real_missing_metadata_dict_gracefully():
    """Validation criterion / vision critique 3: métadonnées manquantes
    gérées sans erreur."""
    result = normalize_document_metadata(None, CSV_CONTENT_TYPE)
    assert result == {"title": None, "author": None, "created_date": None, "keywords": [], "raw": {}}
