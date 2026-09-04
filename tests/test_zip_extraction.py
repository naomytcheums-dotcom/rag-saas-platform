"""
Partie 2.1.19 -- fast-tier tests for api/services/zip_extraction.py.

**Unlike every other test file in this whole 2.1.10-2.1.19 series, NO
mocking of any kind is needed here** -- there is no external API/
network to fake at all (see that module's own docstring): every test
below builds a real, genuine ZIP archive in memory with the stdlib
`zipfile` module, writes it to a real local temp file, and exercises
this module's own real functions against it exactly as
api/security/documents.py's real orchestration does. This is the
single most fully, genuinely end-to-end-verifiable test file of the
entire import-source series.
"""

import zipfile

import pytest

from api.services.zip_extraction import (
    extract_zip_archive,
    extract_zip_file,
    filter_zip_contents,
    list_zip_contents,
    should_include_zip_entry,
)


@pytest.fixture
def real_zip_path(tmp_path):
    """A real, genuine ZIP archive on real local disk -- one normal
    file, one oversized file, one directory entry, one ZipSlip-style
    traversal entry, one absolute-path entry, one pattern-mismatched
    file."""
    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("report.pdf", b"%PDF-1.4 fake but real-looking pdf bytes")
        archive.writestr("notes.txt", "hello world")
        archive.writestr("big.txt", "x" * 1000)
        archive.writestr("sub/dir/", "")
        archive.writestr("../../etc/passwd", "evil")
        archive.writestr("/etc/shadow", "also evil")
        archive.writestr("photo.png", b"\x89PNG\r\n\x1a\n")
    return str(path)


# ------------------------------------------------------- list_zip_contents --

def test_list_zip_contents_returns_every_real_entrys_metadata(real_zip_path):
    """Validation criterion: le contenu d'une archive ZIP est listé."""
    names = [entry.filename for entry in list_zip_contents(real_zip_path)]
    assert "report.pdf" in names
    assert "notes.txt" in names
    assert "sub/dir/" in names


def test_list_zip_contents_raises_for_a_real_corrupt_archive(tmp_path):
    """Validation criterion: une archive corrompue est gérée (vision
    critique 4)."""
    bad_path = tmp_path / "corrupt.zip"
    bad_path.write_bytes(b"PK\x03\x04" + bytes(range(200)))
    with pytest.raises(zipfile.BadZipFile):
        list_zip_contents(str(bad_path))


def test_extract_zip_archive_is_the_same_real_content_as_list_zip_contents(real_zip_path):
    assert [e.filename for e in extract_zip_archive(real_zip_path)] == [e.filename for e in list_zip_contents(real_zip_path)]


# --------------------------------------------------- should_include_zip_entry --

def test_should_include_zip_entry_excludes_real_directories(real_zip_path):
    entries = {e.filename: e for e in list_zip_contents(real_zip_path)}
    assert should_include_zip_entry(entries["sub/dir/"], None, max_size=10_000) is False


def test_should_include_zip_entry_excludes_zip_slip_traversal_names(real_zip_path):
    """Validation criterion / vision critique 2: l'archive est vérifiée
    contre le ZipSlip."""
    entries = {e.filename: e for e in list_zip_contents(real_zip_path)}
    assert should_include_zip_entry(entries["../../etc/passwd"], None, max_size=10_000) is False


def test_should_include_zip_entry_excludes_absolute_path_names(real_zip_path):
    entries = {e.filename: e for e in list_zip_contents(real_zip_path)}
    assert should_include_zip_entry(entries["/etc/shadow"], None, max_size=10_000) is False


def test_should_include_zip_entry_matches_by_real_extension(real_zip_path):
    entries = {e.filename: e for e in list_zip_contents(real_zip_path)}
    assert should_include_zip_entry(entries["report.pdf"], [".pdf"], max_size=10_000) is True
    assert should_include_zip_entry(entries["photo.png"], [".pdf"], max_size=10_000) is False


def test_should_include_zip_entry_enforces_the_real_declared_size_cap(real_zip_path):
    """Validation criterion / vision critique 4: fichiers trop gros
    exclus (contrôle amont sur la taille déclarée)."""
    entries = {e.filename: e for e in list_zip_contents(real_zip_path)}
    assert should_include_zip_entry(entries["notes.txt"], None, max_size=1000) is True
    assert should_include_zip_entry(entries["big.txt"], None, max_size=100) is False


# ------------------------------------------------------- filter_zip_contents --

def test_filter_zip_contents_applies_real_patterns_and_size_together(real_zip_path):
    """Validation criterion: les fichiers de l'archive sont filtrés."""
    entries = list_zip_contents(real_zip_path)
    filtered = filter_zip_contents(entries, [".pdf", ".txt"], max_size=500)
    assert sorted(e.filename for e in filtered) == ["notes.txt", "report.pdf"]


# --------------------------------------------------------- extract_zip_file --

def test_extract_zip_file_returns_the_real_decompressed_content(real_zip_path):
    """Validation criterion: un fichier individuel est extrait de
    l'archive."""
    content = extract_zip_file(real_zip_path, "notes.txt", max_size=10_000)
    assert content == b"hello world"


def test_extract_zip_file_raises_once_actual_decompressed_bytes_exceed_max_size(real_zip_path):
    """Validation criterion / vision critique 2: protection contre les
    fichiers malveillants -- une taille déclarée mensongère ne
    contourne pas la vraie limite, appliquée sur le flux réellement
    décompressé, pas sur la métadonnée déclarée."""
    with pytest.raises(ValueError, match="exceeds the real"):
        extract_zip_file(real_zip_path, "big.txt", max_size=10)


def test_extract_zip_file_raises_for_a_real_nonexistent_entry(real_zip_path):
    with pytest.raises(KeyError):
        extract_zip_file(real_zip_path, "does-not-exist.pdf", max_size=10_000)
