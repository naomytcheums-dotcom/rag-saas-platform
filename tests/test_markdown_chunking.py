"""Partie 3.2.4 -- tests for api/services/markdown_chunking.py's own
real, structure-aware Markdown chunking functions."""

from api.services.markdown_chunking import (
    chunk_markdown_by_headings,
    chunk_markdown_by_sections,
    chunk_markdown_code_blocks,
    chunk_markdown_lists,
    chunk_markdown_tables,
    parse_markdown_structure,
)

_DOC = """# Title

Intro paragraph before any section.

## Section A

Some real content in section A.

### Subsection A.1

Nested content under A.1.

## Section B

More real content in section B.
"""

_CODE_DOC = """# Notes

Some text before the code.

```python
def foo():
    return 1
```

Some text after the code.
"""

_TABLE_DOC = """# Data

| Name | Age |
|------|-----|
| Alice | 30 |
| Bob | 25 |

Some text after the table.
"""

_LIST_DOC = """# Tasks

- First item
- Second item
  continued on an indented line
- Third item

Some text after the list.

1. Step one
2. Step two
"""


def test_parse_markdown_structure_counts_real_elements():
    """Validation criterion: la structure Markdown est analysée."""
    structure = parse_markdown_structure(_DOC)
    assert len(structure["headings"]) == 4
    assert structure["code_blocks"] == 0
    assert structure["tables"] == 0
    assert structure["lists"] == 0


def test_parse_markdown_structure_is_empty_for_empty_input():
    assert parse_markdown_structure("") == {"headings": [], "code_blocks": 0, "tables": 0, "lists": 0}


def test_chunk_markdown_by_headings_splits_only_top_level_sections():
    """Validation criterion: le chunking par titres fonctionne -- with
    the real default MARKDOWN_CHUNK_MIN_HEADING_LEVEL (2), only real H1/
    H2 headings become chunk boundaries; the real H3 subsection stays
    inside its own parent chunk."""
    chunks = chunk_markdown_by_headings(_DOC, min_chunk_size=0, max_chunk_size=1000)
    assert len(chunks) == 3  # Title, Section A (with its H3 child), Section B
    assert any("Subsection A.1" in c for c in chunks)
    assert not any(c.strip().startswith("### Subsection A.1") for c in chunks)


def test_chunk_markdown_by_headings_respects_max_chunk_size():
    long_doc = "# Title\n\n" + ("Real filler sentence. " * 50)
    chunks = chunk_markdown_by_headings(long_doc, max_chunk_size=100)
    assert all(len(c) <= 100 for c in chunks)
    assert len(chunks) > 1


def test_chunk_markdown_by_headings_merges_real_small_sections():
    doc = "# A\n\nShort.\n\n# B\n\nAlso short.\n"
    chunks = chunk_markdown_by_headings(doc, min_chunk_size=1000, max_chunk_size=1000)
    assert len(chunks) == 1


def test_chunk_markdown_by_headings_is_empty_for_empty_input():
    assert chunk_markdown_by_headings("") == []
    assert chunk_markdown_by_headings("   ") == []


def test_chunk_markdown_by_headings_falls_back_when_no_real_headings_exist():
    chunks = chunk_markdown_by_headings("Just a plain paragraph, no headings at all.", max_chunk_size=1000)
    assert len(chunks) == 1
    assert "plain paragraph" in chunks[0]


def test_chunk_markdown_by_sections_splits_every_real_level():
    """Validation criterion: le chunking par sections fonctionne -- the
    finer, full-hierarchy alternative splits at EVERY real heading
    level, including the H3 subsection ignored by chunk_markdown_by_headings."""
    chunks = chunk_markdown_by_sections(_DOC, max_chunk_size=1000)
    assert len(chunks) == 4  # Title, Section A, Subsection A.1, Section B
    assert any("Subsection A.1" in c and "Section A" in c for c in chunks)  # real breadcrumb present


def test_chunk_markdown_by_sections_is_empty_for_empty_input():
    assert chunk_markdown_by_sections("") == []


def test_chunk_markdown_code_blocks_extracts_real_fenced_blocks():
    """Validation criterion: le chunking préservant le code fonctionne."""
    blocks = chunk_markdown_code_blocks(_CODE_DOC)
    assert len(blocks) == 1
    assert blocks[0].startswith("```python")
    assert "def foo():" in blocks[0]
    assert blocks[0].endswith("```")


def test_chunk_markdown_code_blocks_is_empty_when_there_are_none():
    assert chunk_markdown_code_blocks("Just plain text, no code here.") == []


def test_chunk_markdown_by_headings_never_splits_inside_a_real_code_block():
    """Real, direct regression check for MARKDOWN_CHUNK_PRESERVE_CODE_BLOCKS:
    even with a tiny max_chunk_size, the real fenced block stays intact
    as one atomic chunk."""
    chunks = chunk_markdown_by_headings(_CODE_DOC, min_chunk_size=0, max_chunk_size=20)
    assert any("```python\ndef foo():\n    return 1\n```" in c for c in chunks)


def test_chunk_markdown_tables_extracts_a_real_contiguous_table():
    """Validation criterion: le chunking des tableaux fonctionne."""
    tables = chunk_markdown_tables(_TABLE_DOC)
    assert len(tables) == 1
    assert "| Name | Age |" in tables[0]
    assert "| Alice | 30 |" in tables[0]
    assert "Some text after" not in tables[0]


def test_chunk_markdown_tables_is_empty_when_there_are_none():
    assert chunk_markdown_tables("Just plain text, no table here.") == []


def test_chunk_markdown_lists_extracts_a_real_contiguous_list():
    """Validation criterion: le chunking des listes fonctionne."""
    lists = chunk_markdown_lists(_LIST_DOC, max_chunk_size=1000)
    assert len(lists) == 2  # the bulleted list and the numbered list
    assert "First item" in lists[0] and "Third item" in lists[0]
    assert "continued on an indented line" in lists[0]
    assert "Step one" in lists[1] and "Step two" in lists[1]


def test_chunk_markdown_lists_respects_max_chunk_size():
    long_list = "\n".join(f"- Real item number {i} with some real filler text" for i in range(30))
    chunks = chunk_markdown_lists(long_list, max_chunk_size=100)
    assert all(len(c) <= 100 for c in chunks)
    assert len(chunks) > 1


def test_chunk_markdown_lists_is_empty_when_there_are_none():
    assert chunk_markdown_lists("Just plain text, no list here.") == []
