"""
A minimal, REAL OIDC identity provider for testing enterprise SSO
(api/routers/enterprise_sso.py, audit finding 27) -- genuine RSA keypair,
a real /.well-known/openid-configuration + JWKS endpoint, and RS256-signed
id_tokens, served over an actual local HTTP server (see
tests/test_enterprise_sso_integration.py's oidc_idp fixture).

This plays the role no free, hosted Azure AD/Okta tenant is available to
play in this environment -- see api/models/enterprise_sso.py's module
docstring for the broader self-critique of that constraint. What matters
for a genuine test is that this app's OWN code (api/security/enterprise_oidc.py's
JWKS fetch + RS256 signature verification via PyJWT, and Authlib's real
authorization-code/token exchange) runs against a REAL, independently
implemented OIDC server, not a mock of the verification logic itself --
exactly the same principle as tests/webauthn_test_authenticator.py's
software authenticator for WebAuthn.

Not a pytest file itself (no test_ prefix).
"""

import time
import uuid

import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

KID = "test-idp-signing-key-1"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_numbers = _private_key.public_key().public_numbers()


def _b64url_uint(number: int) -> str:
    import base64
    length = (number.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(number.to_bytes(length, "big")).rstrip(b"=").decode()


def create_app() -> FastAPI:
    """A fresh app + fresh in-memory state per test -- `state` holds the
    issuer URL (only known once the server's port is bound) and a
    one-time code -> claims map the test populates before driving the
    real /auth/sso/{id}/authorize -> /callback flow."""
    app = FastAPI()
    state = {"issuer": None, "codes": {}}
    app.state.idp = state

    @app.get("/.well-known/openid-configuration")
    def discovery():
        issuer = state["issuer"]
        return {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/authorize",
            "token_endpoint": f"{issuer}/token",
            "jwks_uri": f"{issuer}/jwks.json",
        }

    @app.get("/jwks.json")
    def jwks():
        return {
            "keys": [{
                "kty": "RSA", "use": "sig", "alg": "RS256", "kid": KID,
                "n": _b64url_uint(_public_numbers.n), "e": _b64url_uint(_public_numbers.e),
            }]
        }

    @app.post("/token")
    async def token(request: Request):
        form = await request.form()
        code = form.get("code")
        claims = state["codes"].pop(code, None)
        if claims is None:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

        now = int(time.time())
        payload = {**claims, "iss": state["issuer"], "iat": now, "exp": now + 300}
        id_token = pyjwt.encode(payload, _private_key, algorithm="RS256", headers={"kid": KID})
        return {"access_token": f"test-access-{uuid.uuid4().hex}", "id_token": id_token, "token_type": "Bearer", "expires_in": 300}

    return app


def register_authorization_code(app: FastAPI, code: str, *, sub: str, email: str, audience: str) -> None:
    """Called by a test right before it drives a browser-style redirect
    to /auth/sso/{id}/authorize with this exact code (real IdPs mint the
    code themselves after the user consents; this test IdP has no real
    consent screen, so the test picks the code and pre-registers the
    claims it should resolve to)."""
    app.state.idp["codes"][code] = {"sub": sub, "email": email, "aud": audience}
