"""
5.3 -- unit tests for api/security/recovery_codes.py's pure functions.
Every existing test that touches recovery codes (test_auth_api.py) only
exercises them indirectly through the /auth/2fa/* endpoints, so the
properties these functions are actually supposed to guarantee -- the
excluded-character alphabet, normalization equivalence, batch
uniqueness -- were never asserted directly. Same isolation-testing
approach as test_auth_security.py for api/security/{hashing,jwt,totp}.py.
"""

import base64
import re

from api.security.recovery_codes import (
    RECOVERY_CODE_COUNT,
    _ALPHABET,
    build_recovery_codes_file,
    generate_recovery_code,
    normalize_recovery_code,
)

_CODE_PATTERN = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def test_generate_recovery_code_matches_the_expected_shape():
    code = generate_recovery_code()
    assert _CODE_PATTERN.match(code), code


def test_generate_recovery_code_never_uses_visually_ambiguous_characters():
    """0/O and 1/I/L are deliberately excluded from _ALPHABET (see its
    comment) -- the characters people most often transcribe wrong when
    copying a code off a screen by hand. Sampled many times since
    generation is random; any single excluded character appearing even
    once would defeat the whole point."""
    excluded = set("01IOL")
    for _ in range(500):
        code = generate_recovery_code()
        raw = code.replace("-", "")
        assert not (set(raw) & excluded), code
        assert set(raw) <= set(_ALPHABET)


def test_generate_recovery_code_batch_has_no_collisions_in_practice():
    """Not a mathematical uniqueness guarantee (birthday-bound, not
    impossible) -- but with a 33-character alphabet and 12 random
    characters per code, a collision in a batch this small is
    astronomically unlikely, so a real collision here would indicate the
    RNG or alphabet is broken, not bad luck."""
    codes = {generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT * 20)}
    assert len(codes) == RECOVERY_CODE_COUNT * 20


def test_normalize_recovery_code_strips_dashes_and_whitespace_and_uppercases():
    assert normalize_recovery_code("7k9p qx3m 2vyt") == "7K9PQX3M2VYT"
    assert normalize_recovery_code("7K9P-QX3M-2VYT") == "7K9PQX3M2VYT"
    assert normalize_recovery_code("  7k9p-qx3m-2vyt  ") == "7K9PQX3M2VYT"
    assert normalize_recovery_code("7K9PQX3M2VYT") == "7K9PQX3M2VYT"


def test_normalize_recovery_code_treats_every_typed_variant_as_equal():
    """The actual guarantee this function exists for: however a user
    retypes a code (lowercase, missing dashes, extra spaces), it must
    normalize identically so the hash lookup in
    api/routers/two_factor.py's verify_two_factor_recovery_code matches."""
    variants = ["7K9P-QX3M-2VYT", "7k9p-qx3m-2vyt", "7K9P QX3M 2VYT", "7k9pqx3m2vyt", " 7K9P-QX3M-2VYT "]
    normalized = {normalize_recovery_code(v) for v in variants}
    assert normalized == {"7K9PQX3M2VYT"}


def test_normalize_recovery_code_is_idempotent():
    once = normalize_recovery_code("7k9p-qx3m-2vyt")
    twice = normalize_recovery_code(once)
    assert once == twice


def test_build_recovery_codes_file_is_a_valid_data_uri_containing_every_code():
    codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    data_uri = build_recovery_codes_file(codes)

    assert data_uri.startswith("data:text/plain;charset=utf-8;base64,")
    decoded = base64.b64decode(data_uri.split(",", 1)[1]).decode("utf-8")
    for code in codes:
        assert code in decoded
    assert "will not be shown again" in decoded  # the one-time-display warning survives into the file


def test_build_recovery_codes_file_preserves_code_order():
    codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    decoded = base64.b64decode(build_recovery_codes_file(codes).split(",", 1)[1]).decode("utf-8")
    positions = [decoded.index(code) for code in codes]
    assert positions == sorted(positions)
