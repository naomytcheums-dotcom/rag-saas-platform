"""
Partie 2.1.4 -- real Markdown extraction tests
(api/services/markdown_extraction.py). No mocking -- real Markdown
source, real markdown-it-py parsing, same "no mocking" discipline as
tests/test_pdf_extraction.py / test_docx_extraction.py / test_txt_extraction.py.
"""

import pytest

from api.services.markdown_extraction import (
    extract_markdown_metadata,
    extract_markdown_sections,
    extract_markdown_structure,
    extract_markdown_tables,
    extract_markdown_text,
)

_SIMPLE_MARKDOWN = """# Main Title

Some **bold** intro text with a [link](https://example.com) and `inline code`.

## Subsection

- Item one
- Item two

A paragraph with *italic* text.
"""

_FRONTMATTER_MARKDOWN = """---
title: Real Test Document
author: pytest
tags:
  - test
  - markdown
---

# Body Heading

Real body content after the frontmatter.
"""

_TABLE_MARKDOWN = """# Doc With A Table

| Name | Age |
|------|-----|
| Alice | 30 |
| Bob | 25 |
"""

_INVALID_FRONTMATTER_MARKDOWN = """---
title: [unclosed bracket
author: pytest
---

# Heading
"""


@pytest.fixture
def simple_path(tmp_path):
    path = tmp_path / "simple.md"
    path.write_bytes(_SIMPLE_MARKDOWN.encode("utf-8"))
    return str(path)


@pytest.fixture
def frontmatter_path(tmp_path):
    path = tmp_path / "frontmatter.md"
    path.write_bytes(_FRONTMATTER_MARKDOWN.encode("utf-8"))
    return str(path)


@pytest.fixture
def table_path(tmp_path):
    path = tmp_path / "table.md"
    path.write_bytes(_TABLE_MARKDOWN.encode("utf-8"))
    return str(path)


@pytest.fixture
def invalid_frontmatter_path(tmp_path):
    path = tmp_path / "invalid_frontmatter.md"
    path.write_bytes(_INVALID_FRONTMATTER_MARKDOWN.encode("utf-8"))
    return str(path)


@pytest.fixture
def no_frontmatter_path(tmp_path):
    path = tmp_path / "no_frontmatter.md"
    path.write_bytes(b"# Just a heading\n\nNo frontmatter here.\n")
    return str(path)


@pytest.fixture
def binary_path(tmp_path):
    import os

    path = tmp_path / "binary.md"
    path.write_bytes(os.urandom(500))
    return str(path)


# ------------------------------------------------------------------- text --

def test_extract_markdown_text_strips_all_markdown_syntax(simple_path):
    """Validation criterion: text extraction works, WITHOUT the
    Markdown syntax -- real bold/link/code/italic markers are gone,
    only the real words remain."""
    text = extract_markdown_text(simple_path)
    assert "Main Title" in text
    assert "Some bold intro text with a link and inline code." in text
    assert "Subsection" in text
    assert "Item one" in text
    assert "Item two" in text
    assert "A paragraph with italic text." in text
    # No raw syntax survives.
    for syntax in ("**", "##", "[link]", "(https://example.com)", "`inline code`", "*italic*"):
        assert syntax not in text


def test_extract_markdown_text_raises_for_real_binary_content(binary_path):
    """Inherited from api/services/txt_extraction.py -- a Markdown file
    is still just text at the byte level, so the same real
    encoding-detection failure mode applies."""
    with pytest.raises(ValueError):
        extract_markdown_text(binary_path)


# -------------------------------------------------------------- structure --

def test_extract_markdown_structure_captures_real_headings_and_list_items(simple_path):
    """Validation criterion: structure extraction works (headings, sections, lists)."""
    structure = extract_markdown_structure(simple_path)
    headings = [s for s in structure if s["type"] == "heading"]
    list_items = [s for s in structure if s["type"] == "list_item"]

    assert headings == [
        {"type": "heading", "level": 1, "text": "Main Title"},
        {"type": "heading", "level": 2, "text": "Subsection"},
    ]
    assert [item["text"] for item in list_items] == ["Item one", "Item two"]


def test_extract_markdown_structure_returns_empty_list_for_plain_prose(tmp_path):
    path = tmp_path / "prose.md"
    path.write_bytes(b"Just a plain paragraph, no headings or lists at all.\n")
    assert extract_markdown_structure(str(path)) == []


# -------------------------------------------------------------- metadata --

def test_extract_markdown_metadata_returns_real_frontmatter_fields(frontmatter_path):
    """Validation criterion: frontmatter YAML metadata is extracted."""
    metadata = extract_markdown_metadata(frontmatter_path)
    assert metadata["title"] == "Real Test Document"
    assert metadata["author"] == "pytest"
    assert metadata["tags"] == ["test", "markdown"]
    assert metadata["heading_count"] == 1


def test_extract_markdown_metadata_returns_only_heading_count_without_frontmatter(no_frontmatter_path):
    """A document with no frontmatter block at all is a normal, valid
    case -- not an error -- just an empty frontmatter contribution."""
    metadata = extract_markdown_metadata(no_frontmatter_path)
    assert "title" not in metadata
    assert metadata["heading_count"] == 1


def test_extract_markdown_metadata_raises_for_real_invalid_yaml_frontmatter(invalid_frontmatter_path):
    """Vision critique / robustness -- Markdown's own genuine
    'corruption' case: CommonMark itself never fails to parse, but a
    frontmatter block with real invalid YAML inside it does raise, and
    must surface as a clear ValueError (confirmed for real:
    yaml.safe_load raises yaml.YAMLError on this exact input)."""
    with pytest.raises(ValueError):
        extract_markdown_metadata(invalid_frontmatter_path)


# -------------------------------------------------------------- sections --

def test_extract_markdown_sections_groups_by_real_heading_boundaries(simple_path):
    sections = extract_markdown_sections(simple_path)
    assert len(sections) == 2
    assert sections[0]["heading"] == "Main Title"
    assert sections[0]["level"] == 1
    assert "bold intro text" in sections[0]["text"]
    assert sections[1]["heading"] == "Subsection"
    assert sections[1]["level"] == 2
    assert "Item one" in sections[1]["text"]
    assert "A paragraph with italic text." in sections[1]["text"]


def test_extract_markdown_sections_handles_text_before_the_first_heading(tmp_path):
    path = tmp_path / "intro.md"
    path.write_bytes(b"Some intro text with no heading above it.\n\n# Real Heading\n\nBody text.\n")
    sections = extract_markdown_sections(str(path))
    assert sections[0]["heading"] is None
    assert sections[0]["level"] is None
    assert "intro text" in sections[0]["text"]
    assert sections[1]["heading"] == "Real Heading"


# ---------------------------------------------------------------- tables --

def test_extract_markdown_tables_finds_the_real_gfm_table(table_path):
    """Validation criterion: table extraction works -- real GFM table
    parsing (CommonMark alone does not parse tables at all)."""
    tables = extract_markdown_tables(table_path)
    assert len(tables) == 1
    df = tables[0]
    assert list(df.columns) == ["Name", "Age"]
    assert df.iloc[0].tolist() == ["Alice", "30"]
    assert df.iloc[1].tolist() == ["Bob", "25"]


def test_extract_markdown_tables_returns_empty_list_when_there_are_none(simple_path):
    assert extract_markdown_tables(simple_path) == []
