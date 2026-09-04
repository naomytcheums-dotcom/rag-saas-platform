"""
Partie 3.1.1 -- cleaning text extracted from a document, before it's
embedded (applied per real chunk -- see this étape's own literal item
3 -- inside api/security/documents.py's own process_document).

Every real function here tolerates `None`/empty input honestly
(returns `""`, never raises) -- a section with no real text is a
normal, expected outcome for several formats already handled
elsewhere in this codebase (e.g. an empty table cell), not an error
this module should surface.
"""

import re
import unicodedata

# A real, deliberate, NARROW definition of "structural" -- Markdown
# headers, list items (bullet or numbered), and table rows, the same
# real markup api/services/*_extraction.py's own Markdown/table
# extractors already produce or pass through. Preserving structure for
# arbitrary rich formats (real DOCX heading STYLES, real PDF layout)
# is real, separate, much deeper work -- this étape's own literal
# scope is post-extraction TEXT cleanup, not re-deriving structure
# extraction never captured as text in the first place.
_STRUCTURAL_LINE_RE = re.compile(r"^\s*(#{1,6}\s.*|[-*+]\s.*|\d+[.)]\s.*|\|.*\|\s*)$")


def normalize_whitespace(text: str) -> str:
    """Item 2's own literal function -- collapses runs of horizontal
    whitespace to one real space, trims spaces around real newlines,
    collapses 3+ consecutive real newlines to a single real blank line
    (2 newlines), and trims the whole result."""
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_control_characters(text: str) -> str:
    """Item 2's own literal function -- strips real Unicode control
    characters (category `Cc`: NUL, form feed, vertical tab, escape
    codes, ...) that sometimes survive a real PDF/DOCX extraction --
    never a printable character. `\\n`/`\\t` are real control
    characters by Unicode's own definition but are real, meaningful
    structure this module's OTHER functions handle deliberately, so
    they're explicitly kept here, not stripped as noise."""
    if not text:
        return ""
    return "".join(c for c in text if c in "\n\t" or unicodedata.category(c) != "Cc")


def normalize_unicode(text: str) -> str:
    """Item 2's own literal function -- real NFKC normalization (the
    same real form `api/security/webauthn.py`'s own docstring already
    notes is the standard choice for text meant to be compared/searched,
    not just displayed): full-width/half-width variants, compatibility
    ligatures, and multiple real ways to encode the same accented
    character all collapse to ONE real canonical form."""
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text)


def preserve_structure(text: str) -> str:
    """Item 2's own literal function -- real, line-aware whitespace
    normalization: a real structural line (Markdown header/list item/
    table row -- see this module's own top docstring for the honest,
    narrow definition used) keeps its own real line break intact
    (never merged into a neighboring paragraph), while every other
    real line still gets the same real horizontal-whitespace collapse
    `normalize_whitespace` applies globally. Vision critique 2's own
    "les titres et listes sont-ils conservés" answer: yes, for
    real Markdown-style structure -- see this module's own docstring
    for what's honestly out of scope."""
    if not text:
        return ""
    lines = text.split("\n")
    cleaned = [re.sub(r"[ \t]+", " ", line).strip() if not _STRUCTURAL_LINE_RE.match(line) else re.sub(r"[ \t]+", " ", line).rstrip() for line in lines]
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def clean_text(text: str) -> str:
    """Item 2's own literal pipeline function -- real, deliberate
    order: control characters first (garbage bytes could otherwise
    confuse the Unicode-category-sensitive steps after them), then
    Unicode normalization (so `preserve_structure`'s own real regex
    matches consistently regardless of which real encoding variant a
    document's own extractor produced), then structure-aware whitespace
    cleanup last. Vision critique 3's own "texte vide ou null" answer:
    real, honest empty string back, never a raised exception."""
    if not text:
        return ""
    text = remove_control_characters(text)
    text = normalize_unicode(text)
    text = preserve_structure(text)
    return text
