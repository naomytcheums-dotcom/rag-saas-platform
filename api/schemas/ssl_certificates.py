"""Request/response bodies for api/routers/ssl_certificates.py
(Partie 1.4.3). Deliberately has NO field for the certificate's private
key anywhere -- see api/models/ssl_certificate.py's own docstring on
why it's encrypted at rest; it must also never be returned by any API
response, encrypted or not."""

import datetime as dt

from pydantic import BaseModel


class SSLDns01Challenge(BaseModel):
    record_name: str
    record_value: str
    instructions: dict[str, str]


class SSLCertificateResponse(BaseModel):
    domain: str
    status: str
    # A certificate itself is public information by definition (any
    # TLS client sees it during the handshake) -- safe to return,
    # unlike the private key. None until status="issued".
    cert_pem: str | None
    chain_pem: str | None
    expires_at: dt.datetime | None
    # Only populated while status="pending_dns01" -- nothing left to
    # tell the Owner to do once a certificate is issued or failed.
    dns01_challenge: SSLDns01Challenge | None
    created_at: dt.datetime
    updated_at: dt.datetime
