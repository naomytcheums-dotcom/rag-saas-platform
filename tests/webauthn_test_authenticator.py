"""
A minimal, REAL software WebAuthn authenticator for tests -- generates a
genuine ES256 keypair and produces spec-shaped, correctly-signed
attestation/assertion objects that api/security/webauthn.py's real
verify_registration_response/verify_authentication_response calls
(from the `webauthn` library) can genuinely cryptographically verify.

This is NOT a mock of the verification logic -- it's the other half of
the real protocol, played by code instead of a physical key/browser, the
same testing approach this codebase already uses elsewhere for "the real
thing is impractical to run in CI" (e.g. tests/test_auth_security.py's
own dummy-hash timing test, or how OAuth's Google/GitHub token exchange
is stubbed at the httpx layer rather than the crypto layer). Every
signature produced here is checked by the SAME code path a real YubiKey's
signature would go through.

Not a pytest file itself (no test_ prefix) -- imported by
tests/test_webauthn_*.py.
"""

import base64
import hashlib
import json

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.cose import COSEAlgorithmIdentifier, COSECRV, COSEKey, COSEKTY

_FLAG_USER_PRESENT = 0x01
_FLAG_USER_VERIFIED = 0x04
_FLAG_ATTESTED_CREDENTIAL_DATA = 0x40


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class SoftwareAuthenticator:
    """One simulated physical key -- one keypair, one credential id, one
    monotonically-increasing sign counter, exactly like a real
    authenticator's internal state."""

    def __init__(self, credential_id: bytes, rp_id: str):
        self.credential_id = credential_id
        self.rp_id = rp_id
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self.sign_count = 0

    def _rp_id_hash(self) -> bytes:
        return hashlib.sha256(self.rp_id.encode()).digest()

    def _cose_public_key_bytes(self) -> bytes:
        numbers = self._private_key.public_key().public_numbers()
        x = numbers.x.to_bytes(32, "big")
        y = numbers.y.to_bytes(32, "big")
        cose_key = {
            COSEKey.KTY: COSEKTY.EC2,
            COSEKey.ALG: COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEKey.CRV: COSECRV.P256,
            COSEKey.X: x,
            COSEKey.Y: y,
        }
        return cbor2.dumps(cose_key)

    def create_registration_response(self, challenge: bytes, rp_origin: str) -> dict:
        """Simulates navigator.credentials.create()'s browser-produced
        response for this authenticator -- real CBOR attestation object
        (fmt="none", no attestation statement -- the same "self
        attestation"/"none" format most real platform authenticators use
        by default), real ECDSA-signed authenticator data structure."""
        self.sign_count += 1
        flags = _FLAG_USER_PRESENT | _FLAG_USER_VERIFIED | _FLAG_ATTESTED_CREDENTIAL_DATA
        attested_credential_data = (
            b"\x00" * 16  # AAGUID -- all-zero is valid, means "no particular authenticator model asserted"
            + len(self.credential_id).to_bytes(2, "big")
            + self.credential_id
            + self._cose_public_key_bytes()
        )
        auth_data = (
            self._rp_id_hash()
            + bytes([flags])
            + self.sign_count.to_bytes(4, "big")
            + attested_credential_data
        )
        attestation_object = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})

        client_data = json.dumps({
            "type": "webauthn.create",
            "challenge": bytes_to_base64url(challenge),
            "origin": rp_origin,
            "crossOrigin": False,
        }).encode()

        return {
            "id": _b64url(self.credential_id),
            "rawId": _b64url(self.credential_id),
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "response": {
                "clientDataJSON": _b64url(client_data),
                "attestationObject": _b64url(attestation_object),
                "transports": ["internal"],
            },
        }

    def create_authentication_response(self, challenge: bytes, rp_origin: str, *, sign_count_override: int | None = None) -> dict:
        """Simulates navigator.credentials.get()'s response. Increments
        (or overrides, for a replay-attack test) the internal counter --
        a real authenticator's whole defense against cloning is that this
        number only ever goes up."""
        self.sign_count = sign_count_override if sign_count_override is not None else self.sign_count + 1
        flags = _FLAG_USER_PRESENT | _FLAG_USER_VERIFIED
        auth_data = self._rp_id_hash() + bytes([flags]) + self.sign_count.to_bytes(4, "big")

        client_data = json.dumps({
            "type": "webauthn.get",
            "challenge": bytes_to_base64url(challenge),
            "origin": rp_origin,
            "crossOrigin": False,
        }).encode()
        client_data_hash = hashlib.sha256(client_data).digest()

        signature = self._private_key.sign(auth_data + client_data_hash, ec.ECDSA(hashes.SHA256()))

        return {
            "id": _b64url(self.credential_id),
            "rawId": _b64url(self.credential_id),
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "response": {
                "clientDataJSON": _b64url(client_data),
                "authenticatorData": _b64url(auth_data),
                "signature": _b64url(signature),
                "userHandle": None,
            },
        }
