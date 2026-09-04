"""
Partie 3.1.9 -- extracting a document's own real headings/sections,
across 5 real formats, for a future structure-aware/semantic chunker
(this étape's own literal "améliorer le chunking sémantique" goal --
the real chunker itself is Partie 3.2's own scope, not built here).

Every real function returns the SAME real, uniform shape: a list of
`{"level": int, "text": str, "position": int}` dicts, in document
order, `position` being the real character offset into whichever text
this format's own extraction naturally produces (the PDF/DOCX real
functions -- signature-wise, `(path)`, not `(text)`, this étape's own
literal choice -- report `position` as the running character offset
into the SAME page/paragraph concatenation order
`extract_pdf_pages_text`/`extract_docx_text` (Partie 2.1.x) already
produce, so a caller combining headings with that already-extracted
text gets real, consistent offsets, not a second, incompatible
numbering).

**A real, deliberate, DOCUMENTED non-duplication**: `extract_headings_markdown`
does NOT reuse Partie 2.1.4's own `extract_markdown_structure` (a real,
richer, AST-based extractor already covering headings AND list items)
-- that function is file-PATH-based, but THIS étape's own literal
signature is TEXT-based (`extract_headings_markdown(text)`), matching
what Partie 3.1.8's own `detect_structure_markdown(text)` needs to call
this with too. Rather than force a text string through a temp file just
to reuse a parser built for a different real calling shape, this is a
real, independent, lightweight regex scan -- honestly narrower (ATX
`#`-style headings only, not Setext `===`-underline style), but
correctly fence-aware (a `#`-looking line inside a real ` ``` ` code
block is never misread as a heading, a real, common false-positive a
naive regex WOULD hit).
"""

import re

_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_MARKDOWN_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HTML_HEADING_RE = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
# Item 1's own literal generic patterns -- "1.", "1.1.", etc. -- a real
# numbered-outline heuristic for plain text with no format markup at
# all to rely on. A real, deliberate, narrow scope, stated plainly:
# this can never be as reliable as a real format's own real markup
# (Markdown's `#`, DOCX's "Heading N" style, PDF's own real font
# size) -- there is no universal, unambiguous signal for "this plain-
# text line is a heading" the way there is for the other 4 formats.
_GENERIC_NUMBERED_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")
_GENERIC_ALL_CAPS_RE = re.compile(r"^[A-ZÀ-Ý][A-ZÀ-Ý\s0-9'\-:,]{3,80}$")


def extract_headings_markdown(text: str) -> list[dict]:
    """Item 2's own literal function -- see this module's own top
    docstring for why this is a real, independent, fence-aware regex
    scan rather than a reuse of Partie 2.1.4's own file-based AST
    parser."""
    if not text:
        return []
    headings = []
    position = 0
    in_fence = False
    for line in text.split("\n"):
        if _MARKDOWN_FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            match = _MARKDOWN_HEADING_RE.match(line)
            if match:
                # `position` must land at the start of the real TITLE
                # text itself (what every `*_headings_*` function above
                # and `split_by_headings` below both assume), not the
                # start of the whole line -- `match.start(2)` is the
                # title group's own real offset within `line`, past the
                # real `#` marker(s) and the space after them.
                headings.append({"level": len(match.group(1)), "text": match.group(2).strip(), "position": position + match.start(2)})
        position += len(line) + 1  # +1 for the real newline this split() consumed
    return headings


def extract_headings_html(text: str) -> list[dict]:
    """Item 2's own literal function -- real `<h1>`-`<h6>` tags via
    BeautifulSoup (already a real dependency since Partie 2.1.5),
    `position` the real character offset into the heading's own plain
    text position within the document's real running text (built the
    same way BeautifulSoup's own `.get_text()` would, so it lines up
    with text a caller extracts the same way)."""
    from bs4 import BeautifulSoup

    if not text:
        return []
    soup = BeautifulSoup(text, "html.parser")
    headings = []
    position = 0
    for element in soup.descendants:
        if isinstance(element, str):
            position += len(element)
            continue
        if element.name and re.fullmatch(r"h[1-6]", element.name):
            heading_text = element.get_text(strip=True)
            if heading_text:
                headings.append({"level": int(element.name[1]), "text": heading_text, "position": position})
    return headings


def extract_headings_generic(text: str) -> list[dict]:
    """Item 2's own literal function -- real pattern-based detection
    for plain text with no format markup at all: a numbered outline
    ("1.", "1.1.", "1.1.1.") gives a real, reliable level (the real
    count of numeric segments); an ALL-CAPS line (a real, common plain-
    text heading convention) is reported at level 1, since plain text
    has no other real signal for relative depth."""
    if not text:
        return []
    headings = []
    position = 0
    for line in text.split("\n"):
        leading_whitespace = len(line) - len(line.lstrip())
        stripped = line.strip()
        numbered = _GENERIC_NUMBERED_RE.match(stripped)
        if numbered:
            level = min(numbered.group(1).count(".") + 1, 6)
            # Same real "position must land on the title text itself"
            # requirement as extract_headings_markdown above -- past
            # both the line's own leading whitespace AND the real
            # numbering prefix ("1.1 ").
            headings.append({"level": level, "text": numbered.group(2).strip(), "position": position + leading_whitespace + numbered.start(2)})
        elif _GENERIC_ALL_CAPS_RE.match(stripped) and any(c.isalpha() for c in stripped):
            headings.append({"level": 1, "text": stripped, "position": position + leading_whitespace})
        position += len(line) + 1
    return headings


def extract_headings_pdf(pdf_path: str) -> list[dict]:
    """Item 2's own literal function -- a real, standard heuristic:
    PyMuPDF's own per-span font SIZE (`page.get_text("dict")`), not a
    fabricated one. This document's own real "body text" baseline is
    the font size covering the most real CHARACTERS overall (not the
    most spans, and not a plain statistical median -- a real, necessary
    distinction: a single, short heading span and a single, short body
    span would tie 1-for-1 under a span-count/median measure even on a
    tiny real document, exactly the real failure a naive median hits;
    body text reliably has far more real CHARACTERS than a heading does,
    even in a short document, so weighting by character count is the
    honest, robust signal). Any span noticeably larger than that
    baseline (>1.2x, a real, deliberate, conservative multiplier so
    normal bold/emphasis text isn't misread as a heading) is a real
    heading candidate, leveled by real, relative size (the single
    largest real size found -> level 1, and so on) -- there is no
    universal absolute pt-size threshold across real, differently-
    designed PDFs, so this document's OWN real distribution is the
    only honest baseline to compare against."""
    import pymupdf

    headings = []
    position = 0
    chars_by_size: dict[float, int] = {}
    spans_by_page: list[list[tuple[str, float]]] = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            page_spans = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        span_text = span["text"].strip()
                        if span_text:
                            size = round(span["size"], 1)
                            page_spans.append((span_text, size))
                            chars_by_size[size] = chars_by_size.get(size, 0) + len(span_text)
            spans_by_page.append(page_spans)

    if not chars_by_size:
        return []
    body_size = max(chars_by_size, key=chars_by_size.get)
    distinct_larger_sizes = sorted({s for s in chars_by_size if s > body_size * 1.2}, reverse=True)

    for page_spans in spans_by_page:
        for span_text, size in page_spans:
            if size in distinct_larger_sizes:
                level = min(distinct_larger_sizes.index(size) + 1, 6)
                headings.append({"level": level, "text": span_text, "position": position})
            position += len(span_text) + 1
    return headings


def extract_headings_docx(docx_path: str) -> list[dict]:
    """Item 2's own literal function -- python-docx's own real
    paragraph style name ("Heading 1".."Heading 9", the real, standard
    Word convention -- exposed directly by `paragraph.style.name`, no
    heuristic guessing needed the way PDF above requires)."""
    import docx

    document = docx.Document(docx_path)
    headings = []
    position = 0
    for paragraph in document.paragraphs:
        match = re.fullmatch(r"Heading (\d+)", paragraph.style.name or "")
        text = paragraph.text.strip()
        if match and text:
            headings.append({"level": min(int(match.group(1)), 6), "text": text, "position": position})
        position += len(paragraph.text) + 1
    return headings


def build_section_hierarchy(headings: list[dict], content: str) -> list[dict]:
    """Item 3's own literal function -- a real, nested tree from the
    flat, level-tagged list every `extract_headings_*` function above
    returns, each node also carrying its own real section TEXT (the
    real content between this heading and the next one at the SAME or
    a SHALLOWER level, via `split_by_headings` below) -- not just the
    heading's own title."""
    sections = split_by_headings(content, headings)
    root: list[dict] = []
    stack: list[tuple[int, dict]] = []  # (level, node)
    for heading, section_text in zip(headings, sections):
        node = {"level": heading["level"], "text": heading["text"], "position": heading["position"], "content": section_text, "children": []}
        while stack and stack[-1][0] >= node["level"]:
            stack.pop()
        (stack[-1][1]["children"] if stack else root).append(node)
        stack.append((node["level"], node))
    return root


def split_by_headings(text: str, headings: list[dict]) -> list[str]:
    """Item 4's own literal function -- real text slicing: each real
    heading's own section runs from immediately after its own title to
    the real start of the next heading (any level), or the real end of
    the document for the last one. Returns one real string per heading,
    same order/length as `headings` itself."""
    if not headings:
        return []
    sorted_headings = sorted(headings, key=lambda h: h["position"])
    sections = []
    for index, heading in enumerate(sorted_headings):
        start = heading["position"] + len(heading["text"])
        if index + 1 < len(sorted_headings):
            next_position = sorted_headings[index + 1]["position"]
            # A real, necessary detail: for a line-based format
            # (Markdown/generic), `next_position` lands on the NEXT
            # heading's own title text, past its own real `#`/numbering
            # PREFIX -- ending the slice there would leak that prefix
            # into THIS section's own trailing content. Real newline
            # before it (its own line's start) is the real, correct
            # boundary; falls back to `next_position` itself when
            # there is none (HTML/PDF/DOCX headings never carry a
            # textual prefix in their own real position at all, so
            # this is a real, harmless no-op for those 3 formats).
            newline_before_next = text.rfind("\n", 0, next_position)
            end = newline_before_next if newline_before_next >= start else next_position
        else:
            end = len(text)
        sections.append(text[start:end].strip())
    return sections


def get_section_context(text: str, position: int, headings: list[dict]) -> dict | None:
    """Item 4's own literal function -- the single real heading whose
    own section this real character `position` falls under (the LAST
    real heading at or before it, any level) -- `None` for a real
    position before the document's own first heading (real, honest
    "no section yet" content, e.g. an introduction)."""
    candidates = [h for h in headings if h["position"] <= position]
    return max(candidates, key=lambda h: h["position"]) if candidates else None


def get_section_path(headings: list[dict], position: int) -> list[str]:
    """Item 4's own literal function -- the real, full hierarchical
    breadcrumb (e.g. `["Chapter 1", "Section 1.2"]`) leading to
    `position`: the most recent real heading at EACH level from 1 up to
    the deepest one reached by `position`, walking headings in document
    order (a real, later heading at a level replaces an earlier one at
    the SAME level once passed -- the same real nesting logic
    `build_section_hierarchy` above uses, applied to a single point
    instead of the whole document)."""
    path: dict[int, str] = {}
    for heading in sorted(headings, key=lambda h: h["position"]):
        if heading["position"] > position:
            break
        path = {level: title for level, title in path.items() if level < heading["level"]}
        path[heading["level"]] = heading["text"]
    return [path[level] for level in sorted(path)]
