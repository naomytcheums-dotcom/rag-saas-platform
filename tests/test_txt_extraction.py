"""
Partie 2.1.3 -- real TXT extraction/encoding-detection tests
(api/services/txt_extraction.py). No mocking -- real bytes, real
encodings, real charset-normalizer detection, same "no mocking"
discipline as tests/test_pdf_extraction.py and tests/test_docx_extraction.py.
"""

import os

import pytest

from api.services.txt_extraction import detect_encoding, extract_txt_text, is_valid_text

_SAMPLE_TEXT = (
    "Ceci est un texte plus long en francais, avec de nombreux mots pour aider "
    "la detection automatique d'encodage a etre plus fiable, car il y a plus de "
    "signal statistique a analyser sur un echantillon plus long."
)
_ACCENTED_TEXT = (
    "Voici un texte reel avec des caracteres accentues : été, à, ça, "
    "déjà, où, français, système, problème."
)


@pytest.fixture
def utf8_path(tmp_path):
    path = tmp_path / "utf8.txt"
    path.write_bytes(_ACCENTED_TEXT.encode("utf-8"))
    return str(path)


@pytest.fixture
def latin1_path(tmp_path):
    path = tmp_path / "latin1.txt"
    path.write_bytes(_ACCENTED_TEXT.encode("iso-8859-1"))
    return str(path)


@pytest.fixture
def cp1252_path(tmp_path):
    path = tmp_path / "cp1252.txt"
    path.write_bytes(_ACCENTED_TEXT.encode("cp1252"))
    return str(path)


@pytest.fixture
def utf16_path(tmp_path):
    path = tmp_path / "utf16.txt"
    path.write_bytes(_ACCENTED_TEXT.encode("utf-16"))  # includes a BOM
    return str(path)


@pytest.fixture
def empty_path(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_bytes(b"")
    return str(path)


@pytest.fixture
def binary_path(tmp_path):
    path = tmp_path / "binary.dat"
    path.write_bytes(os.urandom(500))
    return str(path)


# ------------------------------------------------------------- detection --

def test_detect_encoding_identifies_real_utf8(utf8_path):
    """Validation criterion: encoding detection works (UTF-8)."""
    assert detect_encoding(utf8_path) == "utf_8"


def test_detect_encoding_identifies_a_real_western_single_byte_encoding(latin1_path):
    """
    Validation criterion: encoding detection works (ISO-8859-1). A real,
    honest caveat, confirmed by testing rather than assumed: ISO-8859-1
    and Windows-1252 are byte-identical for every character in normal
    Western text (they only differ in the rarely-used 0x80-0x9F control
    range) -- detect_encoding may report either label for the same real
    bytes. What's actually verified here is that the CONTENT decodes
    correctly, not a specific one of those two interchangeable labels
    -- see api/services/txt_extraction.py's own module docstring.
    """
    encoding = detect_encoding(latin1_path)
    assert encoding in ("iso8859_1", "cp1252")
    assert extract_txt_text(latin1_path) == _ACCENTED_TEXT


def test_detect_encoding_identifies_real_cp1252(cp1252_path):
    encoding = detect_encoding(cp1252_path)
    assert encoding in ("iso8859_1", "cp1252")
    assert extract_txt_text(cp1252_path) == _ACCENTED_TEXT


def test_detect_encoding_identifies_real_utf16(utf16_path):
    assert detect_encoding(utf16_path) == "utf_16"


def test_detect_encoding_raises_for_real_binary_content(binary_path):
    """Vision critique Q2 -- what happens when the encoding is unknown:
    a real, random byte sequence that doesn't decode as text under any
    common encoding raises a clear ValueError."""
    with pytest.raises(ValueError):
        detect_encoding(binary_path)


def test_detect_encoding_handles_a_genuinely_empty_file(empty_path):
    """Vision critique Q4 -- empty files are a real, valid edge case
    (trivial, zero-length UTF-8 text), not an error."""
    assert detect_encoding(empty_path) == "utf_8"


# ----------------------------------------------------------------- text --

def test_extract_txt_text_returns_the_real_utf8_content(utf8_path):
    """Validation criterion: text extraction works."""
    assert extract_txt_text(utf8_path) == _ACCENTED_TEXT


def test_extract_txt_text_returns_the_real_utf16_content(utf16_path):
    assert extract_txt_text(utf16_path) == _ACCENTED_TEXT


def test_extract_txt_text_returns_empty_string_for_an_empty_file(empty_path):
    assert extract_txt_text(empty_path) == ""


def test_extract_txt_text_raises_for_real_binary_content(binary_path):
    with pytest.raises(ValueError):
        extract_txt_text(binary_path)


# ------------------------------------------------------------- is_valid_text --

def test_is_valid_text_accepts_real_utf8_bytes():
    assert is_valid_text(_SAMPLE_TEXT.encode("utf-8")) is True


def test_is_valid_text_accepts_genuinely_empty_bytes():
    assert is_valid_text(b"") is True


def test_is_valid_text_rejects_real_binary_bytes():
    assert is_valid_text(os.urandom(500)) is False


def test_is_valid_text_rejects_pdf_shaped_binary():
    """Defense in depth -- even though api/services/document_storage.py's
    validate_document_upload checks PDF/DOCX signatures BEFORE falling
    back to text detection, is_valid_text on its own must not
    misclassify real binary formats as text."""
    assert is_valid_text(b"%PDF-1.4\n" + os.urandom(300)) is False
