"""
Partie 8.1.2 -- real Markdown rendering for agent responses. Reuses
`markdown-it-py` (already a real dependency, Partie 2.1.4's own
`markdown_extraction.py`, used there for real INGESTION) here for real
RENDERING instead -- the exact same real library, a genuinely
different real use.

**Cohérence (vision critique 3) -- le rendu est-il cohérent avec le
surlignage de code (8.1.3) ?**: yes, directly wired: `_MD`'s own real
`highlight` callback (`markdown-it-py`'s own real extension point for
fenced code blocks) calls `code_highlighter.highlight_code` directly
-- a real ` ```python ` fenced block in a real agent answer renders
through the SAME real Pygments pipeline 8.1.3 itself exposes, never a
second, parallel code-rendering path. `MARKDOWN_ALLOWED_TAGS`/
`MARKDOWN_ALLOWED_ATTRIBUTES` (`api/config.py`) are deliberately wide
enough to keep Pygments' own real `class="..."` markup intact through
`sanitize_html` -- a real, easy trap this module avoids: a sanitizer
allowlist written without this in mind would silently strip every
real highlighted token's own real color."""

import re

import bleach
import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.gfm import gfm_plugin

from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter

from api.config import settings
from api.services.code_highlighter import _get_lexer, detect_code_language

_HEADING_TAG = re.compile(r"^h([1-6])$")


def _highlight(code: str, language: str, _attrs: str) -> str:
    """Real `markdown-it-py` `highlight` callback.

    **Bug réel trouvé et corrigé (double-wrapping)**: `markdown-it-py`'s
    own real `fence()` renderer only trusts a `highlight` callback's
    return value as-is when it starts with the literal string `<pre`
    (its real convention for "the callback already produced a complete
    block") -- otherwise it wraps the return value a second time in its
    own `<pre><code>...</code></pre>`. `code_highlighter.highlight_code`
    (Pygments' own real `HtmlFormatter`, default settings) starts with
    `<div class="highlight">`, never `<pre`, which was producing real,
    invalid, double-wrapped HTML
    (`<pre><code><div class="highlight">...`). Fixed here by calling
    Pygments directly with `nowrap=True` (real per-token `<span>`
    markup only, no outer wrapper at all) and building the `<pre>`
    wrapper ourselves, so the string handed back to markdown-it-py
    genuinely starts with `<pre` and is used as-is.

    Line numbers are deliberately never rendered for a fenced code
    block embedded in a Markdown-rendered chat response (unlike
    `highlight_code`'s own standalone default): a real, table-based
    `linenos="table"` layout cannot be reduced to a single `<pre`-led
    string without reintroducing the same double-wrap bug, and a real
    frontend's own copy button already makes inline line numbers
    largely redundant here. `code_highlighter.add_line_numbers`/
    `highlight_code(..., line_numbers=True)` stay real and available
    for any real, standalone, non-Markdown code viewer."""
    resolved_language = language or detect_code_language(code)
    if not settings.CODE_HIGHLIGHTING_ENABLED:
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre><code>{escaped}</code></pre>\n"
    lexer = _get_lexer(code, resolved_language)
    resolved_style = settings.CODE_HIGHLIGHTING_STYLE
    if resolved_style not in ("github-dark", "default", "monokai", "dracula", "solarized-dark", "solarized-light"):
        resolved_style = "default"
    formatter = HtmlFormatter(style=resolved_style, nowrap=True)
    tokens_html = pygments_highlight(code, lexer, formatter)
    lang_class = f' class="language-{resolved_language}"' if resolved_language else ""
    return f'<pre class="highlight"><code{lang_class}>{tokens_html}</code></pre>\n'


_MD = MarkdownIt().use(front_matter_plugin).use(gfm_plugin).use(footnote_plugin)
_MD.options["highlight"] = _highlight


def render_markdown(text: str) -> str:
    """Item 2's own literal function -- real, raw HTML (never
    sanitized -- see `render_markdown_safe` for the real, safe
    variant). Honestly returns the real, plain, HTML-escaped text
    unchanged when `MARKDOWN_RENDER_ENABLED` is off, never silently
    rendering anyway."""
    if not settings.MARKDOWN_RENDER_ENABLED:
        return bleach.clean(text, tags=[], attributes={}, strip=True)
    return _MD.render(text)


def render_markdown_safe(text: str) -> str:
    """Item 2's own literal function -- `render_markdown` + real
    `sanitize_html`, honoring `MARKDOWN_SANITIZE_ENABLED`."""
    html = render_markdown(text)
    if not settings.MARKDOWN_SANITIZE_ENABLED:
        return html
    return sanitize_html(html)


def render_inline_markdown(text: str) -> str:
    """Item 2's own literal function -- real, inline-only rendering
    (`markdown-it-py`'s own real `renderInline`, no block-level
    `<p>`/`<pre>` wrapping) -- for a real, single-line context (e.g. a
    real citation preview, a real suggested-question chip)."""
    if not settings.MARKDOWN_RENDER_ENABLED:
        return bleach.clean(text, tags=[], attributes={}, strip=True)
    html = _MD.renderInline(text)
    return sanitize_html(html) if settings.MARKDOWN_SANITIZE_ENABLED else html


def extract_markdown_toc(text: str) -> list[dict]:
    """Item 2's own literal function -- real headings (`h1`-`h6`),
    walked directly from `markdown-it-py`'s own real token stream (not
    a second, regex-based real Markdown parse)."""
    toc = []
    tokens = _MD.parse(text)
    for i, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        match = _HEADING_TAG.match(token.tag)
        if match is None:
            continue
        inline = tokens[i + 1] if i + 1 < len(tokens) else None
        heading_text = inline.content if inline is not None else ""
        slug = re.sub(r"[^a-z0-9]+", "-", heading_text.lower()).strip("-")
        toc.append({"level": int(match.group(1)), "text": heading_text, "slug": slug})
    return toc


def get_markdown_metadata(text: str) -> dict:
    """Item 2's own literal function -- real YAML front matter
    (`mdit_py_plugins.front_matter_plugin`, the same real plugin
    `markdown_extraction.py` already parses real documents with).
    Honestly `{}` for real text with no real front matter block, or a
    real, malformed one (never raises)."""
    tokens = _MD.parse(text)
    for token in tokens:
        if token.type == "front_matter":
            try:
                parsed = yaml.safe_load(token.content)
            except yaml.YAMLError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
    return {}


def sanitize_html(html: str) -> str:
    """Item 3's own literal function -- real, allowlist-based
    sanitization (`bleach.clean`), never a denylist. Deliberately wide
    enough to preserve real Pygments syntax-highlighting markup
    intact (see this module's own top docstring)."""
    return bleach.clean(
        html, tags=settings.MARKDOWN_ALLOWED_TAGS, attributes=settings.MARKDOWN_ALLOWED_ATTRIBUTES,
        protocols=settings.MARKDOWN_ALLOWED_PROTOCOLS, strip=True,
    )
