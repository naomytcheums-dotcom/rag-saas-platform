"""Spec 14.4.2 / 14.4.4: the logo files and the brand guide are real, consistent with each other and with the application's own colour tokens."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "frontend" / "public" / "brand"
GUIDE = (ROOT / "docs" / "commercial" / "BRAND_GUIDE.md").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "app" / "globals.css").read_text(encoding="utf-8")
FILES = ["logo-mark.svg", "logo-mark-mono.svg", "logo-horizontal-light.svg", "logo-horizontal-dark.svg", "favicon.svg"]
SVG = "{http://www.w3.org/2000/svg}"


def _luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("name", FILES)
def test_each_logo_is_a_valid_safe_svg(name):
    path = BRAND / name
    assert path.is_file(), name
    root = ET.parse(path).getroot()
    assert root.tag == SVG + "svg" and root.get("viewBox")
    assert root.find(SVG + "title") is not None, "an accessible name"
    raw = path.read_text(encoding="utf-8").lower()
    for forbidden in ("<script", "onload", "onclick", "javascript:", "http://", "https://", "<image", "<foreignobject", "@import"):
        if forbidden == "http://":
            assert raw.count("http://") == raw.count("http://www.w3.org/2000/svg"), "no external reference besides the SVG namespace"
        else:
            assert forbidden not in raw, f"{name} contains {forbidden}"
    assert path.stat().st_size < 4096, "a logo is a few hundred bytes, not an embedded bitmap"


def test_colours_in_the_logos_are_brand_tokens():
    tokens = {m.lower() for m in re.findall(r"#[0-9a-fA-F]{6}\b", CSS)}
    allowed = tokens | {"#ffffff", "#fff"}
    for name in FILES:
        for colour in re.findall(r"#[0-9a-fA-F]{3,6}\b", (BRAND / name).read_text(encoding="utf-8")):
            assert colour.lower() in allowed, f"{name} uses {colour}, which is not a token of frontend/app/globals.css"


def test_the_guide_lists_every_logo_file_and_the_tokens_it_quotes_exist():
    for name in FILES:
        assert f"`{name}`" in GUIDE, f"{name} is not documented in docs/commercial/BRAND_GUIDE.md"
    table = GUIDE.split("## 3. Colours")[1].split("## 4.")[0]
    css_tokens = {m.lower() for m in re.findall(r"#[0-9a-fA-F]{6}\b", CSS)}
    for colour in set(re.findall(r"#[0-9a-fA-F]{6}\b", table)):
        assert colour.lower() in css_tokens, f"the guide quotes {colour}, absent from globals.css"


@pytest.mark.parametrize("foreground, background, minimum", [
    ("#1c1d1d", "#ffffff", 7.0),
    ("#727272", "#ffffff", 4.5),
    ("#ff4b00", "#1b1b1c", 4.5),
    ("#1c1d1d", "#fff0ea", 7.0),
    ("#ffffff", "#ff4b00", 3.0),  # graphics and large text only: see the guide
])
def test_the_contrast_ratios_stated_in_the_guide_are_true(foreground, background, minimum):
    assert contrast(foreground, background) >= minimum
    ratio = contrast(foreground, background)
    assert f"{ratio:.1f}" in GUIDE or f"{ratio:.2f}" in GUIDE, f"{ratio:.2f} is not stated in the guide"


def test_white_on_accent_is_honestly_documented_as_not_aa_for_small_text():
    assert contrast("#ffffff", "#ff4b00") < 4.5
    assert "not** AA for normal-size text" in GUIDE


def test_the_header_and_the_metadata_use_the_files():
    assert "/brand/logo-mark.svg" in (ROOT / "frontend" / "components" / "figma" / "SiteHeader.tsx").read_text(encoding="utf-8")
    assert "/brand/favicon.svg" in (ROOT / "frontend" / "app" / "layout.tsx").read_text(encoding="utf-8")
