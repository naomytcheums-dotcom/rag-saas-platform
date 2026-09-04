"""
Partie 2.1.19 -- listing, filtering, and extracting files from a real
ZIP archive already uploaded as a Document (the SAME upload route as
every other format, Partie 2.1.1 -- `api/services/document_storage.py`'s
own `validate_document_upload` now recognizes real ZIP magic bytes),
purely with the stdlib `zipfile` module. **The ONLY import source in
this whole 2.1.10-2.1.19 series with NO external API and NO credentials
at all** -- fully, genuinely verifiable end to end, no honest
limitation to state the way 2.1.14/2.1.17/2.1.18 each needed one.

**Real ZipSlip protection (vision critique's own explicit ask)**: a
malicious ZIP entry name can contain path-traversal sequences
(`../../etc/passwd`) or an absolute path -- the classic "ZipSlip"
vulnerability, when code blindly joins an entry's own name onto an
extraction directory and writes there. This module never does that:
`extract_zip_file` reads a real entry's bytes directly by its own EXACT
name inside the archive, and never constructs or writes to a real
filesystem path built from that name -- the classic disk-write exploit
does not literally apply here. `should_include_zip_entry` still
defensively rejects any entry whose own name normalizes outside the
archive root (or is absolute) anyway, not because this codebase's own
extraction method is vulnerable, but because that same entry name is
stored, unchanged, as the resulting Document's own `name` -- a real, if
lower-severity, "confusing/spoofable display name" concern worth
closing anyway.

Real ZIP entry names always use forward slashes per the ZIP format's
own spec, regardless of the host OS that created the archive -- `posixpath`
is used for real path normalization here, deliberately not `os.path`
(which would use backslashes on this codebase's own Windows dev
environment, the wrong separator for a real zip entry name).

**Real, bounded-memory decompression, not a single unbounded `.read()`
call**: `extract_zip_file` reads a real entry through `ZipFile.open()`
in fixed-size chunks, raising the moment more than `max_size` real,
ACTUALLY-decompressed bytes have been read -- a genuine defense against
a real "zip bomb" (a maliciously crafted entry whose own declared
`file_size` metadata undersells its real decompressed size). Trusting
`ZipInfo.file_size` alone (checked first, in `should_include_zip_entry`,
as a cheap upfront filter) is NOT sufficient on its own -- that value
comes from the archive's own, attacker-controlled central directory --
the streaming cutoff here is what actually, physically bounds real
memory use regardless of what the metadata claims.
"""

import posixpath
import zipfile

_READ_CHUNK_SIZE = 1024 * 1024  # 1 MB


def list_zip_contents(file_path: str) -> list[zipfile.ZipInfo]:
    """
    Item 3's literal function -- every real entry's own metadata (name,
    real declared size, is-a-directory), no content read yet. A real
    `zipfile.BadZipFile` (a genuinely corrupt/truncated archive, vision
    critique's own "archive corrompue" case) propagates to the caller,
    same "not real, usable content either way" treatment every prior
    format's own corrupt-file handling already gives.
    """
    with zipfile.ZipFile(file_path) as archive:
        return archive.infolist()


def _is_safe_zip_entry_name(name: str) -> bool:
    """Real, defensive ZipSlip-style name rejection -- see this
    module's own docstring for why this matters even though nothing
    here ever writes an extracted file to a real path built from it."""
    if not name or name.startswith(("/", "\\")):
        return False
    if "\x00" in name:
        return False
    normalized = posixpath.normpath(name)
    return normalized != ".." and not normalized.startswith("../")


def should_include_zip_entry(entry: zipfile.ZipInfo, patterns: list[str] | None, max_size: int) -> bool:
    """
    Item 4's literal function -- a real ALLOWLIST, same reasoning as
    every prior `should_include_*`. Real directories, unsafe real names
    (see `_is_safe_zip_entry_name`), entries whose own declared size
    already exceeds `max_size` (a cheap upfront filter --
    `extract_zip_file`'s own real streaming cutoff is the actual,
    physical safety net against a forged/understated size, see this
    module's own docstring), and pattern mismatches are all excluded
    here.
    """
    if entry.is_dir():
        return False
    if not _is_safe_zip_entry_name(entry.filename):
        return False
    if patterns:
        if not any(entry.filename.lower().endswith(pattern.lower()) for pattern in patterns):
            return False
    if entry.file_size > max_size:
        return False
    return True


def filter_zip_contents(files: list[zipfile.ZipInfo], patterns: list[str] | None, max_size: int) -> list[zipfile.ZipInfo]:
    """Item 3's literal function -- `should_include_zip_entry` applied
    across a real archive's own full listing."""
    return [entry for entry in files if should_include_zip_entry(entry, patterns, max_size)]


def extract_zip_archive(file_path: str) -> list[zipfile.ZipInfo]:
    """
    Item 3's literal function -- NOT this module's own per-entry
    extraction function (that's `extract_zip_file` below, despite the
    similar name) -- opens and validates the real archive as a whole (a
    real `zipfile.BadZipFile` here means the whole archive is corrupt,
    vision critique's own "archive corrompue" case), returning every
    real entry's own metadata. Same real content as `list_zip_contents`
    -- kept as two separately-named literal functions per this step's
    own spec, not collapsed into one.
    """
    return list_zip_contents(file_path)


def extract_zip_file(file_path: str, entry: str, max_size: int) -> bytes:
    """
    Item 3's literal function -- real, BOUNDED-memory extraction of ONE
    real entry's content by its own exact name (see this module's own
    docstring for why this is a real streaming read, not a single
    unbounded `.read()` call). Raises `ValueError` if the real,
    ACTUALLY-decompressed content exceeds `max_size`, regardless of
    what the entry's own declared `file_size` metadata claims. A real
    `KeyError` (the named entry genuinely does not exist in this
    archive) propagates to the caller, same as a real `BadZipFile`.
    """
    with zipfile.ZipFile(file_path) as archive:
        with archive.open(entry) as member:
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = member.read(_READ_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raise ValueError(f"zip entry '{entry}' exceeds the real {max_size}-byte limit once actually decompressed")
                chunks.append(chunk)
            return b"".join(chunks)
