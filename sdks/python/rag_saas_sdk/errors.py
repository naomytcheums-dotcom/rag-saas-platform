"""Real, honest error type for the SDK -- every real, non-2xx response
from the real backend becomes one of these, carrying the real status
code and the real, parsed error detail, never a bare, unhelpful
`httpx.HTTPStatusError`."""


class RagSaasAPIError(Exception):
    def __init__(self, status_code: int, detail: object):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"RAG SaaS API error {status_code}: {detail}")
