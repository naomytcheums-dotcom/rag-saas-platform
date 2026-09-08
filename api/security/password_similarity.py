"""
Audit finding 16 -- reject a password that's a trivial variation of the
account's own email or name (e.g. "janedoe" / "janedoe1" for
jane.doe@example.com). Hand-rolled Levenshtein distance rather than a new
dependency (python-Levenshtein/rapidfuzz) -- the algorithm is the standard
~20-line dynamic-programming table, short enough to read and verify
directly, same "no dependency for logic this small" reasoning as
api/security/rate_limit.py's own sliding window.
"""

from api.config import settings


def levenshtein_distance(a: str, b: str) -> int:
    """Classic O(len(a) * len(b)) edit-distance DP. Only the previous row
    is ever needed, so this keeps O(min(len(a), len(b))) space rather
    than a full 2D table -- passwords and email/name strings are short,
    but there's no reason to allocate more than necessary.

    Public (not private to this module) -- Partie 7.1.3's own real
    `ground_truth_answers.validate_fuzzy` reuses this exact same real
    algorithm rather than a second, hand-rolled copy."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i]
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            current_row.append(min(
                previous_row[j] + 1,      # deletion
                current_row[j - 1] + 1,   # insertion
                previous_row[j - 1] + cost,  # substitution
            ))
        previous_row = current_row
    return previous_row[-1]


def is_password_too_similar(password: str, email: str, name: str | None = None) -> bool:
    """True if `password` is within PASSWORD_SIMILARITY_MIN_DISTANCE
    single-character edits of the account's email, the email's
    local-part (everything before '@' -- comparing against the FULL
    email would make almost every password look "far" from it purely
    because of the added length of "@domain.tld", missing the actual
    risk: a password derived from the part of the email a person
    actually treats as their handle), or their name. Case-insensitive --
    "JaneDoe123" is exactly as weak as "janedoe123"."""
    password_lower = password.lower()
    local_part = email.split("@", 1)[0].lower()
    candidates = [email.lower(), local_part]
    if name:
        candidates.append(name.lower())

    return any(
        levenshtein_distance(password_lower, candidate) < settings.PASSWORD_SIMILARITY_MIN_DISTANCE
        for candidate in candidates
        if candidate
    )
