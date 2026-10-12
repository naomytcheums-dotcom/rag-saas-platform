"""E2E finding 2026-10-12: an empty upload was accepted, stored and ended 'completed' with zero chunks (a document nobody can ever find)."""

import pytest

from api.services.document_storage import validate_document_upload


@pytest.mark.parametrize("content", [b"", b"   \n\t  \n"])
def test_empty_or_whitespace_only_upload_is_refused(content):
    with pytest.raises(ValueError, match="empty"):
        validate_document_upload(content, "notes.txt")


def test_a_real_text_file_is_still_accepted():
    assert validate_document_upload(b"hello world, this is a note", "notes.txt") == "text/plain"
