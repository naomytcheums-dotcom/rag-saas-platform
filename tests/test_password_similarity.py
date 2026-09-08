"""
Audit finding 16 -- unit tests for api/security/password_similarity.py's
hand-rolled Levenshtein distance and is_password_too_similar. Pure
functions, no DB/network -- tested directly and fast, same as
test_password_strength.py's neighbor test_recovery_codes.py.
"""

from api.config import settings
from api.security.password_similarity import levenshtein_distance, is_password_too_similar


def testlevenshtein_distance_of_identical_strings_is_zero():
    assert levenshtein_distance("janedoe", "janedoe") == 0


def testlevenshtein_distance_counts_single_character_edits():
    assert levenshtein_distance("janedoe", "janedoe1") == 1  # one insertion
    assert levenshtein_distance("janedoe", "janedo") == 1  # one deletion
    assert levenshtein_distance("janedoe", "janedof") == 1  # one substitution


def testlevenshtein_distance_of_completely_different_strings_is_large():
    assert levenshtein_distance("correct-horse-battery-staple", "xyz") >= 3


def testlevenshtein_distance_against_an_empty_string_is_the_other_length():
    assert levenshtein_distance("abc", "") == 3
    assert levenshtein_distance("", "") == 0


def testlevenshtein_distance_is_symmetric():
    assert levenshtein_distance("kitten", "sitting") == levenshtein_distance("sitting", "kitten")


def test_password_matching_the_email_local_part_is_too_similar():
    assert is_password_too_similar("janedoe", "janedoe@example.com", None) is True


def test_password_close_to_the_email_local_part_is_too_similar():
    assert is_password_too_similar("janedoe1", "janedoe@example.com", None) is True  # distance 1


def test_password_matching_the_full_name_is_too_similar():
    assert is_password_too_similar("janedoe", "someone@example.com", "Jane Doe") is True


def test_password_is_case_insensitive_for_similarity():
    assert is_password_too_similar("JANEDOE", "janedoe@example.com", None) is True


def test_unrelated_password_is_not_too_similar():
    assert is_password_too_similar("correct-horse-battery-staple", "janedoe@example.com", "Jane Doe") is False


def test_no_name_provided_only_checks_against_email():
    assert is_password_too_similar("correct-horse-battery-staple", "janedoe@example.com", None) is False


def test_similarity_threshold_is_read_from_settings(monkeypatch):
    """Proves PASSWORD_SIMILARITY_MIN_DISTANCE is actually consulted at
    call time, not hardcoded -- a threshold of 0 (nothing is ever "too
    similar" except an exact match) lets a password one edit away
    through that the default threshold of 3 would reject."""
    monkeypatch.setattr(settings, "PASSWORD_SIMILARITY_MIN_DISTANCE", 0)
    assert is_password_too_similar("janedoe1", "janedoe@example.com", None) is False
