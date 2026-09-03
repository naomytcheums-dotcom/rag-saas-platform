"""
Partie 2.1.8 -- real XML extraction tests
(api/services/xml_extraction.py). No mocking -- real XML source, real
lxml.etree parsing, same "no mocking" discipline as
tests/test_pdf_extraction.py / test_docx_extraction.py / test_txt_extraction.py /
test_markdown_extraction.py / test_html_extraction.py / test_csv_extraction.py /
test_json_extraction.py.
"""

import os

import pytest
from lxml import etree

from api.services.xml_extraction import (
    extract_xml_data,
    extract_xml_metadata,
    extract_xml_structure,
    extract_xml_text,
)

_CATALOG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<catalog>
  <book id="bk101" category="fiction">
    <title lang="en">Real Book Title</title>
    <author>Jane Doe</author>
    <price currency="USD">19.99</price>
  </book>
  <book id="bk102" category="reference">
    <title lang="fr">Un Vrai Titre</title>
    <author>John Smith</author>
    <price currency="EUR">29.99</price>
  </book>
</catalog>"""

_FLAT_XML = "<root><a>1</a><b>2</b></root>"

_MALFORMED_XML = "<a><b></a>"

_NAMESPACED_XML = (
    '<ns:root xmlns:ns="http://example.com/ns">'
    '<ns:child attr="v">hi</ns:child>'
    "</ns:root>"
)

_BILLION_LAUGHS_XML = """<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY a "1234567890">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
]>
<root>&c;</root>"""

_BENIGN_ENTITY_XML = """<?xml version="1.0"?>
<!DOCTYPE root [ <!ENTITY company "Acme Corp"> ]>
<root>Hello &company;</root>"""

_WITH_COMMENT_XML = "<root><!-- a real comment --><item>real content</item></root>"


def _write(tmp_path, name, content: str | bytes):
    path = tmp_path / name
    path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
    return str(path)


@pytest.fixture
def catalog_path(tmp_path):
    return _write(tmp_path, "catalog.xml", _CATALOG_XML)


@pytest.fixture
def flat_path(tmp_path):
    return _write(tmp_path, "flat.xml", _FLAT_XML)


@pytest.fixture
def malformed_path(tmp_path):
    return _write(tmp_path, "malformed.xml", _MALFORMED_XML)


@pytest.fixture
def namespaced_path(tmp_path):
    return _write(tmp_path, "namespaced.xml", _NAMESPACED_XML)


@pytest.fixture
def billion_laughs_path(tmp_path):
    return _write(tmp_path, "billion_laughs.xml", _BILLION_LAUGHS_XML)


@pytest.fixture
def benign_entity_path(tmp_path):
    return _write(tmp_path, "benign_entity.xml", _BENIGN_ENTITY_XML)


@pytest.fixture
def with_comment_path(tmp_path):
    return _write(tmp_path, "with_comment.xml", _WITH_COMMENT_XML)


@pytest.fixture
def too_deep_path(tmp_path):
    # libxml2's own real, DELIBERATE depth guard (confirmed for real at
    # exactly 257 levels in this lxml/libxml2 version -- see this
    # module's own docstring, "real finding #1") is a compiled-in
    # constant bundled with the lxml wheel, not an OS thread's own C
    # stack size the way Partie 2.1.7's JSON RecursionError turned out
    # to be -- still, a generous margin (1000, ~4x the observed real
    # threshold) is used here rather than testing right at that exact
    # boundary, having learned that lesson the hard way in CI already.
    depth = 1000
    content = ("<a>" * depth + "text" + "</a>" * depth).encode("utf-8")
    return _write(tmp_path, "too_deep.xml", content)


@pytest.fixture
def empty_path(tmp_path):
    return _write(tmp_path, "empty.xml", "")


@pytest.fixture
def not_xml_path(tmp_path):
    return _write(tmp_path, "not_xml.xml", "just plain text, no xml here at all")


@pytest.fixture
def binary_path(tmp_path):
    path = tmp_path / "binary.xml"
    path.write_bytes(os.urandom(500))
    return str(path)


# ---------------------------------------------------------------- text --

def test_extract_xml_text_returns_readable_path_value_lines(catalog_path):
    """Validation criterion + vision critique Q2: readable, structured
    text -- one line per real text-bearing element, showing both where
    a value came from (its tag path) and what it says."""
    text = extract_xml_text(catalog_path)
    lines = text.split("\n")
    assert "catalog/book/title: Real Book Title" in lines
    assert "catalog/book/author: Jane Doe" in lines
    assert "catalog/book/price: 19.99" in lines
    assert "catalog/book/title: Un Vrai Titre" in lines


def test_extract_xml_text_tolerates_a_real_comment_without_crashing(with_comment_path):
    """Real robustness: an XML comment is a real, valid, non-element
    node -- the walker must skip it, not crash trying to treat it as
    a tagged element."""
    text = extract_xml_text(with_comment_path)
    assert "root/item: real content" in text


def test_extract_xml_text_does_not_expand_a_billion_laughs_entity(billion_laughs_path):
    """Vision critique Q3, a real security finding: entity resolution
    is deliberately disabled (see this module's own docstring) -- the
    unresolved entity reference must not crash extraction and must not
    silently expand into a huge string either."""
    text = extract_xml_text(billion_laughs_path)
    assert len(text) < 100  # nowhere near what real expansion would produce
    assert "1234567890" not in text


def test_extract_xml_text_raises_for_malformed_xml(malformed_path):
    with pytest.raises(etree.XMLSyntaxError):
        extract_xml_text(malformed_path)


def test_extract_xml_text_raises_for_excessive_nesting_depth(too_deep_path):
    """Vision critique Q3, part 2: libxml2's own real depth guard,
    confirmed for real before writing this module -- not an incidental
    Python RecursionError the way Partie 2.1.7's JSON parser's own
    ceiling turned out to be."""
    with pytest.raises(etree.XMLSyntaxError):
        extract_xml_text(too_deep_path)


def test_extract_xml_text_raises_for_a_genuinely_empty_file(empty_path):
    with pytest.raises(etree.XMLSyntaxError):
        extract_xml_text(empty_path)


def test_extract_xml_text_raises_for_content_that_is_not_xml_at_all(not_xml_path):
    with pytest.raises(etree.XMLSyntaxError):
        extract_xml_text(not_xml_path)


def test_extract_xml_text_raises_for_real_binary_content(binary_path):
    with pytest.raises(etree.XMLSyntaxError):
        extract_xml_text(binary_path)


def test_extract_xml_text_strips_the_namespace_uri_for_readability(namespaced_path):
    """Real, deliberate simplification (see this module's own
    docstring): the local tag name is used, not the full Clark-notation
    `{namespace}tag` lxml itself uses internally."""
    text = extract_xml_text(namespaced_path)
    assert text == "root/child: hi"


# ---------------------------------------------------------------- data --

def test_extract_xml_data_matches_the_real_xmltodict_convention(catalog_path):
    """Validation criterion: raw data extraction works, following the
    same real, well-known convention xmltodict itself uses (confirmed
    against a real xmltodict.parse() call before writing this module):
    @attr keys, #text for mixed attribute+text content, repeated
    siblings collapsed into a list."""
    data = extract_xml_data(catalog_path)
    books = data["catalog"]["book"]
    assert isinstance(books, list)
    assert len(books) == 2
    assert books[0]["@id"] == "bk101"
    assert books[0]["@category"] == "fiction"
    assert books[0]["title"] == {"@lang": "en", "#text": "Real Book Title"}
    assert books[0]["author"] == "Jane Doe"  # text-only, no attributes -- a bare string, not wrapped
    assert books[0]["price"] == {"@currency": "USD", "#text": "19.99"}


def test_extract_xml_data_does_not_crash_on_an_unresolved_entity_node(billion_laughs_path):
    """Real, non-obvious bug caught before it shipped: with entity
    resolution disabled, an unresolved reference is a real, distinct
    node type in the tree (lxml's own Entity sentinel, not a string
    tag) -- confirmed for real to need explicit filtering, not just
    assumed to behave like a normal child element."""
    data = extract_xml_data(billion_laughs_path)
    assert "root" in data


def test_extract_xml_data_raises_for_malformed_xml(malformed_path):
    with pytest.raises(etree.XMLSyntaxError):
        extract_xml_data(malformed_path)


# ------------------------------------------------------------ metadata --

def test_extract_xml_metadata_returns_real_root_counts_and_depth(catalog_path):
    """Validation criterion: root, attributes, and depth are all
    extracted."""
    metadata = extract_xml_metadata(catalog_path)
    assert metadata["root"] == "catalog"
    assert metadata["element_count"] == 9  # catalog + 2 books + 2*(title/author/price)
    assert metadata["attribute_count"] == 8  # 2*(id,category) + 2*lang + 2*currency
    assert metadata["depth"] == 3


def test_extract_xml_metadata_for_a_flat_document(flat_path):
    metadata = extract_xml_metadata(flat_path)
    assert metadata == {"root": "root", "element_count": 3, "attribute_count": 0, "depth": 2}


def test_extract_xml_metadata_strips_namespace_from_the_root_name(namespaced_path):
    assert extract_xml_metadata(namespaced_path)["root"] == "root"


# ------------------------------------------------------------ structure --

def test_extract_xml_structure_detects_attributes_and_nesting(catalog_path):
    """Validation criterion + vision critique Q3: attribute presence
    and real nested-element depth are both detected."""
    structure = extract_xml_structure(catalog_path)
    assert structure == {"has_attributes": True, "has_nested_elements": True, "depth": 3}


def test_extract_xml_structure_for_a_flat_document_with_no_attributes(flat_path):
    """A root with only simple leaf children (depth 2, the minimal real
    XML shape) is NOT itself considered "nested" -- a deliberate,
    stated definition (see this module's own docstring), unlike a
    coarser "any children at all" reading that almost every real XML
    document would trivially satisfy."""
    structure = extract_xml_structure(flat_path)
    assert structure == {"has_attributes": False, "has_nested_elements": False, "depth": 2}
