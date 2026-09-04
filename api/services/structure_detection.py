"""
Partie 3.1.8 -- a real, uniform structural outline (`DocumentStructure`)
across 5 real formats, for the same "chunking sémantique" goal Partie
3.1.9's own headings extraction already states (the real chunker
itself is Partie 3.2's own scope).

**A real, deliberate, DOCUMENTED scope choice**: `DocumentStructure` is
a real, FLAT, document-ordered list -- `StructureElement.children`
exists (this étape's own literal field) but stays empty here by
design. Nesting headings into a real tree is exactly what Partie
3.1.9's own `build_section_hierarchy` already does; duplicating that
logic here, a second, competing way to nest the SAME real headings,
would be real, unnecessary complexity this étape's own literal
`DocumentStructure -> liste de StructureElement` wording doesn't
actually ask for. A caller wanting the nested tree combines this
module's own flat headings with Partie 3.1.9 directly.
"""

import re
from dataclasses import dataclass, field


@dataclass
class StructureElement:
    type: str  # "heading" | "paragraph" | "list_item" | "code_block" | "table"
    level: int | None
    content: str
    children: list["StructureElement"] = field(default_factory=list)


DocumentStructure = list[StructureElement]

_MARKDOWN_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_MARKDOWN_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$")


def detect_structure_markdown(text: str) -> DocumentStructure:
    """Item 2's own literal function -- headings (via Partie 3.1.9's
    own `extract_headings_markdown`, reused unchanged, not a second,
    duplicated regex), real list items, and real fenced code blocks
    (their own real, complete, un-cleaned content -- code is
    deliberately NEVER run through Partie 3.1.1/3.1.2's own cleanup/
    normalization pipeline, since whitespace/punctuation are real,
    meaningful syntax there, not noise)."""
    from api.services.headings_extraction import extract_headings_markdown

    if not text:
        return []
    headings_by_position = {h["position"]: h for h in extract_headings_markdown(text)}
    elements: list[StructureElement] = []
    lines = text.split("\n")
    position = 0
    in_fence = False
    code_lines: list[str] = []
    for line in lines:
        if _MARKDOWN_FENCE_RE.match(line):
            if in_fence:
                elements.append(StructureElement(type="code_block", level=None, content="\n".join(code_lines)))
                code_lines = []
            in_fence = not in_fence
        elif in_fence:
            code_lines.append(line)
        else:
            heading = next((h for h in headings_by_position.values() if position <= h["position"] < position + len(line) + 1), None)
            if heading:
                elements.append(StructureElement(type="heading", level=heading["level"], content=heading["text"]))
            else:
                list_match = _MARKDOWN_LIST_ITEM_RE.match(line)
                if list_match:
                    elements.append(StructureElement(type="list_item", level=None, content=list_match.group(1).strip()))
                elif line.strip():
                    elements.append(StructureElement(type="paragraph", level=None, content=line.strip()))
        position += len(line) + 1
    return elements


def detect_structure_html(text: str) -> DocumentStructure:
    """Item 2's own literal function -- real `<h1>`-`<h6>`/`<p>`/`<li>`/
    `<table>` tags via BeautifulSoup, in real document order
    (`soup.find_all` with no filter, walked once)."""
    from bs4 import BeautifulSoup

    if not text:
        return []
    soup = BeautifulSoup(text, "html.parser")
    elements: list[StructureElement] = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"]):
        content = tag.get_text(strip=True)
        if not content:
            continue
        if re.fullmatch(r"h[1-6]", tag.name):
            elements.append(StructureElement(type="heading", level=int(tag.name[1]), content=content))
        elif tag.name == "li":
            elements.append(StructureElement(type="list_item", level=None, content=content))
        elif tag.name == "table":
            elements.append(StructureElement(type="table", level=None, content=content))
        else:
            elements.append(StructureElement(type="paragraph", level=None, content=content))
    return elements


def detect_structure_text(text: str) -> DocumentStructure:
    """Item 2's own literal function -- real headings (Partie 3.1.9's
    own `extract_headings_generic`, the same real, honestly-narrow
    pattern-based heuristic), every other real, non-blank line grouped
    into paragraphs by real blank-line boundaries (plain text's own
    only real structural signal)."""
    from api.services.headings_extraction import extract_headings_generic

    if not text:
        return []
    # Matched by real POSITION, not by exact line-text equality -- a
    # numbered heading's own `extract_headings_generic` text is just
    # the part AFTER its real "1.1 " prefix (see that function's own
    # docstring), which never equals the full, still-prefixed line
    # this loop sees, so a text-equality check would silently miss
    # every real numbered heading (confirmed by a real test failure
    # before this fix).
    headings_by_position = {h["position"]: h for h in extract_headings_generic(text)}
    elements: list[StructureElement] = []
    paragraph_lines: list[str] = []
    position = 0

    def _flush_paragraph():
        if paragraph_lines:
            elements.append(StructureElement(type="paragraph", level=None, content=" ".join(paragraph_lines)))
            paragraph_lines.clear()

    for line in text.split("\n"):
        stripped = line.strip()
        heading = next((h for h in headings_by_position.values() if position <= h["position"] < position + len(line) + 1), None)
        if heading:
            _flush_paragraph()
            elements.append(StructureElement(type="heading", level=heading["level"], content=heading["text"]))
        elif stripped:
            paragraph_lines.append(stripped)
        else:
            _flush_paragraph()
        position += len(line) + 1
    _flush_paragraph()
    return elements


def detect_structure_pdf(pdf_path: str) -> DocumentStructure:
    """Item 2's own literal function -- real headings (Partie 3.1.9's
    own `extract_headings_pdf`, its own real font-size heuristic,
    reused unchanged), every other real, non-empty span grouped into
    one real paragraph per page (a real, honest limitation -- PyMuPDF's
    own `page.get_text()` line/paragraph boundaries are themselves
    already a real heuristic; this étape's own real value is
    distinguishing HEADING spans from everything else, not re-deriving
    PDF's own real paragraph boundaries a second, competing way)."""
    import pymupdf

    from api.services.headings_extraction import extract_headings_pdf

    heading_texts = {h["text"] for h in extract_headings_pdf(pdf_path)}
    heading_by_text = {h["text"]: h for h in extract_headings_pdf(pdf_path)}
    elements: list[StructureElement] = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            paragraph_parts: list[str] = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        span_text = span["text"].strip()
                        if not span_text:
                            continue
                        if span_text in heading_texts:
                            if paragraph_parts:
                                elements.append(StructureElement(type="paragraph", level=None, content=" ".join(paragraph_parts)))
                                paragraph_parts = []
                            heading = heading_by_text[span_text]
                            elements.append(StructureElement(type="heading", level=heading["level"], content=span_text))
                        else:
                            paragraph_parts.append(span_text)
            if paragraph_parts:
                elements.append(StructureElement(type="paragraph", level=None, content=" ".join(paragraph_parts)))
    return elements


def detect_structure_docx(docx_path: str) -> DocumentStructure:
    """Item 2's own literal function -- real headings (Partie 3.1.9's
    own `extract_headings_docx`, real "Heading N" paragraph styles),
    real non-heading paragraphs, and real tables (Partie 3.1.4's own
    already-existing `extract_docx_tables`, reused unchanged and
    rendered via Partie 3.1.4's own `table_to_text`, not a second,
    competing table-to-string implementation)."""
    import docx

    from api.services.headings_extraction import extract_headings_docx
    from api.services.table_transformation import table_to_text

    heading_texts = {h["text"] for h in extract_headings_docx(docx_path)}
    heading_by_text = {h["text"]: h for h in extract_headings_docx(docx_path)}
    elements: list[StructureElement] = []
    document = docx.Document(docx_path)
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if text in heading_texts:
            heading = heading_by_text[text]
            elements.append(StructureElement(type="heading", level=heading["level"], content=text))
        else:
            elements.append(StructureElement(type="paragraph", level=None, content=text))

    from api.services.docx_extraction import extract_docx_tables

    for table in extract_docx_tables(docx_path):
        elements.append(StructureElement(type="table", level=None, content=table_to_text(table)))
    return elements


def structure_to_json(structure: DocumentStructure) -> list[dict]:
    """Item 3's own literal function."""
    return [
        {"type": element.type, "level": element.level, "content": element.content, "children": structure_to_json(element.children)}
        for element in structure
    ]


def structure_to_markdown(structure: DocumentStructure) -> str:
    """Item 3's own literal function -- a real, readable Markdown
    rendering: a real heading level back into `#`s, a real list item
    back into `- `, a real code block back into a fenced block, a real
    table's own already-rendered text kept as-is."""
    lines = []
    for element in structure:
        if element.type == "heading":
            lines.append(f"{'#' * (element.level or 1)} {element.content}")
        elif element.type == "list_item":
            lines.append(f"- {element.content}")
        elif element.type == "code_block":
            lines.append(f"```\n{element.content}\n```")
        else:
            lines.append(element.content)
        if element.children:
            lines.append(structure_to_markdown(element.children))
    return "\n\n".join(lines)
