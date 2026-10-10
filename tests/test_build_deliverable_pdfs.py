"""The Markdown -> HTML converter used for the delivery PDFs (spec 14.2.x)."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("build_deliverable_pdfs", Path(__file__).resolve().parent.parent / "scripts" / "build_deliverable_pdfs.py")
module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(module)
to_html = module.markdown_to_html


def test_headings_paragraphs_and_inline_formatting():
    out = to_html("# Title\n\nSome **bold**, *italic* and `code` with a [link](https://example.com).\nSecond line of the same paragraph.")
    assert "<h1>Title</h1>" in out
    assert "<strong>bold</strong>" in out and "<em>italic</em>" in out and "<code>code</code>" in out
    assert '<a href="https://example.com">link</a>' in out
    assert out.count("<p>") == 1 and "Second line" in out


def test_lists_ordered_and_unordered():
    out = to_html("- one\n- two\n\n1. first\n2. second")
    assert out.count("<ul>") == 1 and out.count("<li>") == 4 and "<ol>" in out


def test_tables_become_html_tables():
    out = to_html("| a | b |\n|---|---|\n| 1 | **2** |")
    assert "<table>" in out and "<th>a</th>" in out and "<td><strong>2</strong></td>" in out


def test_code_blocks_are_escaped_not_interpreted():
    out = to_html("```\n<script>alert(1)</script> **x**\n```")
    assert "<pre>" in out and "&lt;script&gt;" in out and "<strong>" not in out


def test_html_in_text_is_escaped():
    out = to_html("Hello <img src=x onerror=alert(1)> world")
    assert "<img" not in out and "&lt;img" in out


def test_csv_table_helper_truncates_and_escapes_pipes(tmp_path):
    path = tmp_path / "f.csv"
    path.write_text('id,name\n1,"a|b"\n2,' + "x" * 300 + "\n", encoding="utf-8")
    table = module.csv_to_markdown_table(path, ["id", "name"])
    assert "a/b" in table and max(len(line) for line in table.split("\n")) < 200


def test_every_document_definition_points_to_existing_sources_or_says_so():
    docs = module.documents()
    assert {"architecture.pdf", "feature-list.pdf", "deployment-guide.pdf", "api-documentation.pdf", "security-audit.pdf", "benchmark-report.pdf", "setup-guide.pdf"} <= set(docs)
    for _name, (_title, parts) in docs.items():
        assert parts and all(heading and body for heading, body in parts)
