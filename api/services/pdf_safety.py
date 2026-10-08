"""Safety rules for every PDF built from HTML with WeasyPrint.

WeasyPrint is a browser engine: given `<link rel="attachment" href="file:///etc/passwd">`, `<img src="http://169.254.169.254/...">` or a
stylesheet URL it FETCHES the resource from the server and, for attachments, embeds it in the PDF it returns. Two things keep that
closed:

1. Everything that comes from a user or a tenant (a conversation title, an organization name, an invoice line description) is escaped
   before it is placed in the HTML (`esc`).
2. WeasyPrint is given a `url_fetcher` that refuses every external resource (`deny_all_url_fetcher`), so even markup that slips through
   cannot make the server read a local file or call an internal address. These documents are self-contained: they never need a fetch.
"""

import html


def esc(value) -> str:
    """HTML-escape any value (None becomes an empty string) for text and attribute positions."""
    return html.escape("" if value is None else str(value), quote=True)


def deny_all_url_fetcher(url, *args, **kwargs):
    """A WeasyPrint `url_fetcher` that never fetches anything. WeasyPrint reports the failure for that one resource and carries on
    rendering the rest of the document."""
    raise ValueError(f"loading external resources is disabled in generated PDFs: {str(url)[:80]!r}")
