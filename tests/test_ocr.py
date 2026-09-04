"""
Partie 3.1.6 -- tests for api/services/ocr.py.

Real Tesseract/poppler binaries are NOT installed on this session's own
dev machine (confirmed for real: `tesseract`/`pdftoppm` are both
absent from PATH) -- the same honest limitation as every other real,
optional system dependency this codebase has hit before (real
Postgres/S3/MinIO for tests/test_documents_integration.py). What's
tested here instead: `get_ocr_confidence`'s own real, pure math
(no binary involved at all), `detect_scanned_pdf`'s own real heuristic
against REAL PyMuPDF-extracted text (no Tesseract needed either), and
every other real function's own orchestration logic mocked at the
`pytesseract`/`pdf2image` call boundary (the SAME "real library
behavior, fake network/binary" split this codebase already uses for
Redis/SSRF elsewhere) -- proving THIS module's own real logic
(language/timeout wiring, graceful degradation, per-page resilience),
not Tesseract's own internals. A real, end-to-end test against the
real binaries is included, SKIPPED when they're not on PATH -- the
same honest, real "skip when infra is unavailable" convention as
every other real-infrastructure test in this codebase.
"""

import shutil
from unittest.mock import patch

import pytest
from PIL import Image
from pytesseract import TesseractNotFoundError

from api.services.ocr import (
    OCRNotAvailableError,
    detect_scanned_pdf,
    get_ocr_confidence,
    ocr_image,
    ocr_image_bytes,
    ocr_image_with_confidence,
    ocr_pdf_page,
    ocr_pdf_scanned,
)

_TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
_POPPLER_AVAILABLE = shutil.which("pdftoppm") is not None


# ------------------------------------------------------------- get_ocr_confidence --

def test_get_ocr_confidence_averages_real_recognized_words():
    """Validation criterion: le niveau de confiance de l'OCR est
    obtenu."""
    assert get_ocr_confidence({"conf": [90, 80, 70]}) == 80.0


def test_get_ocr_confidence_excludes_real_non_text_regions():
    """Tesseract's own real `-1` marker (not a real OCR guess at all)
    must never drag down a real, meaningful average."""
    assert get_ocr_confidence({"conf": [90, -1, -1, 70]}) == 80.0


def test_get_ocr_confidence_returns_zero_for_no_real_recognized_words():
    assert get_ocr_confidence({"conf": [-1, -1]}) == 0.0
    assert get_ocr_confidence({}) == 0.0


# ------------------------------------------------------------- detect_scanned_pdf --

def _real_text_pdf(tmp_path, text: str) -> str:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    path = tmp_path / "test.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_detect_scanned_pdf_is_false_for_a_real_text_pdf(tmp_path):
    """Validation criterion: la détection de PDF scanné fonctionne
    (cas texte réel)."""
    path = _real_text_pdf(tmp_path, "This is real, substantial text content on this real PDF page, well above any real minimal threshold.")
    assert detect_scanned_pdf(path) is False


def test_detect_scanned_pdf_is_true_for_a_real_blank_page(tmp_path):
    """Validation criterion: la détection de PDF scanné fonctionne
    (cas scanné réel -- aucune vraie couche de texte)."""
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()  # a real, genuinely blank page -- no real text layer at all
    path = tmp_path / "blank.pdf"
    doc.save(str(path))
    doc.close()
    assert detect_scanned_pdf(str(path)) is True


# ---------------------------------------------------------------------- ocr_image --

def test_ocr_image_raises_ocr_not_available_when_tesseract_is_missing():
    """Robustesse (vision critique 3) -- absence réelle du binaire
    Tesseract signalée explicitement, jamais une exception opaque."""
    with patch("api.services.ocr.pytesseract.image_to_string", side_effect=TesseractNotFoundError()):
        with pytest.raises(OCRNotAvailableError):
            ocr_image("irrelevant.png")


def test_ocr_image_passes_the_real_configured_language_and_timeout():
    with patch("api.services.ocr.pytesseract.image_to_string", return_value="real recognized text") as mock_ocr:
        result = ocr_image("a.png")
    assert result == "real recognized text"
    _, kwargs = mock_ocr.call_args
    assert kwargs["lang"] == "fra"  # this codebase's own real default
    assert kwargs["timeout"] == 30


def test_ocr_image_respects_an_explicit_language_override():
    with patch("api.services.ocr.pytesseract.image_to_string", return_value="") as mock_ocr:
        ocr_image("a.png", language="eng")
    assert mock_ocr.call_args.kwargs["lang"] == "eng"


def test_ocr_image_bytes_decodes_a_real_image_before_ocr(tmp_path):
    import io

    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")

    with patch("api.services.ocr.pytesseract.image_to_string", return_value="real text") as mock_ocr:
        result = ocr_image_bytes(buf.getvalue())
    assert result == "real text"
    mock_ocr.assert_called_once()


def test_ocr_image_with_confidence_returns_both_from_one_real_pass():
    """Validation criterion -- texte ET confiance viennent du même
    vrai appel OCR."""
    with patch("api.services.ocr.pytesseract.image_to_data", return_value={"text": ["Hello", "", "World"], "conf": [95, -1, 85]}):
        text, confidence = ocr_image_with_confidence("a.png")
    assert text == "Hello World"
    assert confidence == 90.0


def test_ocr_image_with_confidence_raises_ocr_not_available_when_tesseract_is_missing():
    with patch("api.services.ocr.pytesseract.image_to_data", side_effect=TesseractNotFoundError()):
        with pytest.raises(OCRNotAvailableError):
            ocr_image_with_confidence("a.png")


# ------------------------------------------------------------------ ocr_pdf_page --

def test_ocr_pdf_page_rasterizes_then_ocrs_the_real_requested_page():
    """Validation criterion: l'OCR d'une page PDF fonctionne."""
    fake_image = object()
    with patch("pdf2image.convert_from_path", return_value=[fake_image]) as mock_convert, \
         patch("api.services.ocr.pytesseract.image_to_string", return_value="page text") as mock_ocr:
        result = ocr_pdf_page("doc.pdf", page_number=2)

    assert result == "page text"
    _, kwargs = mock_convert.call_args
    assert kwargs["first_page"] == 2
    assert kwargs["last_page"] == 2
    assert kwargs["dpi"] == 300  # this codebase's own real default
    mock_ocr.assert_called_once_with(fake_image, lang="fra", timeout=30)


def test_ocr_pdf_page_raises_ocr_not_available_when_poppler_is_missing():
    from pdf2image.exceptions import PDFInfoNotInstalledError

    with patch("pdf2image.convert_from_path", side_effect=PDFInfoNotInstalledError()):
        with pytest.raises(OCRNotAvailableError):
            ocr_pdf_page("doc.pdf", page_number=1)


# --------------------------------------------------------------- ocr_pdf_scanned --

def test_ocr_pdf_scanned_returns_one_real_string_per_page():
    """Validation criterion: l'OCR d'un PDF scanné fonctionne (toutes
    les pages)."""
    fake_images = [object(), object()]
    with patch("pdf2image.convert_from_path", return_value=fake_images), \
         patch("api.services.ocr.pytesseract.image_to_string", side_effect=["page one", "page two"]):
        result = ocr_pdf_scanned("doc.pdf")
    assert result == ["page one", "page two"]


def test_ocr_pdf_scanned_tolerates_a_real_failure_on_one_page():
    """Robustesse (vision critique 3) -- une page qui échoue ne bloque
    pas les autres."""
    fake_images = [object(), object(), object()]
    with patch("pdf2image.convert_from_path", return_value=fake_images), \
         patch("api.services.ocr.pytesseract.image_to_string", side_effect=["good 1", RuntimeError("real OCR crash"), "good 2"]):
        result = ocr_pdf_scanned("doc.pdf")
    assert result == ["good 1", "", "good 2"]


# ------------------------------------------------- real, end-to-end (skipped if unavailable) --

@pytest.mark.skipif(not _TESSERACT_AVAILABLE, reason="real Tesseract binary not installed on this machine")
def test_ocr_image_works_for_real_against_the_real_tesseract_binary(tmp_path):
    """The real, genuine end-to-end proof this module works, once the
    real binary is actually installed (e.g. in CI, or a real
    deployment) -- skipped, not faked, everywhere else."""
    path = tmp_path / "real_text.png"
    Image.new("RGB", (300, 80), color="white").save(path)
    from PIL import ImageDraw

    image = Image.open(path)
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), "HELLO", fill="black")
    image.save(path)

    result = ocr_image(str(path))
    assert "HELLO" in result.upper()


@pytest.mark.skipif(not (_TESSERACT_AVAILABLE and _POPPLER_AVAILABLE), reason="real Tesseract/poppler binaries not installed on this machine")
def test_detect_scanned_pdf_and_ocr_pdf_scanned_work_for_real_end_to_end(tmp_path):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()  # a real, genuinely blank/scanned-like page
    path = tmp_path / "scanned.pdf"
    doc.save(str(path))
    doc.close()

    assert detect_scanned_pdf(str(path)) is True
    pages = ocr_pdf_scanned(str(path))
    assert len(pages) == 1  # a real result for the real, single page, even if empty
