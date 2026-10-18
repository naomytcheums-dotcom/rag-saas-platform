# Brand guide (spec 14.4.1 - 14.4.4)

This guide documents the visual identity **as implemented** in the application (`frontend/app/globals.css`, `frontend/components/figma/`, `frontend/components/landing/`).
It is a record of what exists, not a new design.

## 1. Product name
The product name is **RAG SaaS Platform**, chosen by the owner on 2026-10-11 (decision D3). It is what the interface already displays (site title in
`frontend/app/layout.tsx`, `app_name` and the brand fallback in `frontend/lib/locales`). "KnowFlow AI" in the competitive-audit documents is a competitor reference and an
early working name, not the product. Remaining places to check when publishing: the e-mail sender name (`EMAIL_FROM_ADDRESS`), the widget title and the PDFs under `deliverables/`.
Every customer-facing string comes from `locales/*/common.json`, so a later rename is a text change, not a code change.

## 2. Logo
The mark is a magnifying glass (retrieval) holding a four-point spark (the generated answer), on a rounded square in the brand gradient. Files, all vector, in
`frontend/public/brand/` (served at `/brand/...`):

| File | Use |
|---|---|
| `logo-mark.svg` | the square mark in the brand gradient: app icon, avatar, social profile, the site header (`SiteHeader.tsx`) |
| `logo-mark-mono.svg` | one-colour mark (`currentColor`, default `#1c1d1d`): stamps, fax / print in black, embossing, watermarks |
| `logo-horizontal-light.svg` | mark + "RAG SaaS / Platform" for light backgrounds (documents, e-mail footers, slides) |
| `logo-horizontal-dark.svg` | same with white text for dark backgrounds (`--ink`, `--ink-deep`, the authentication screens) |
| `favicon.svg` | simplified solid-accent mark, thicker strokes so it stays readable at 16 px (declared in `frontend/app/layout.tsx`, next to the legacy `favicon.ico`) |

Rules:
- **Clear space**: keep at least one quarter of the mark's width free on every side (16 px around a 64 px mark).
- **Minimum size**: mark 16 px (use `favicon.svg` below 24 px); horizontal logo 120 px wide.
- **Do not**: recolour the gradient, rotate or skew, add shadows or outlines, put the gradient mark on the accent orange or on a photo (use the mono mark in white),
  stretch it, or redraw the spark.
- **Text in the horizontal logos** is live SVG text (Inter, then Segoe UI / Arial) so the files stay small and editable; before sending them to a printer or a
  sign-maker, open the SVG in a vector editor and "convert text to outlines". The wordmark is not a registered trademark: a trademark search and filing is an owner decision.
- **Customers** replace the logo, favicon and name through white-label settings; the files above are the platform's own identity, not the customers'.

The geometry is checked by `tests/test_brand_assets.py` (valid SVG, no script or external reference, colours taken from the tokens below, every file listed here exists).

## 3. Colours (tokens)
| Role | Token | Value |
|---|---|---|
| Accent (buttons, links) | `--accent` | `#ff4b00` |
| Accent hover | `--accent-hover` | `#e04300` |
| Accent soft background | `--accent-soft` | `#fff0ea` |
| Brand gradient | `--brand-from / --brand-via / --brand-to` | `#ff541f` / `#ff7044` / `#ff9777` |
| Text | `--foreground` | `#1c1d1d` |
| Secondary text | `--foreground-muted` | `#727272` |
| Background / surface | `--background`, `--surface` | `#ffffff` |
| Muted surface | `--surface-muted` | `#f9f9f9` |
| Borders | `--border`, `--border-strong` | `#e4e4e4`, `#d9d9d9` |
| Ink (dark sections) | `--ink`, `--ink-deep` | `#1b1b1c`, `#010101` |
| Authentication card gradient | `--auth-from / --auth-via / --auth-to` | `rgb(2,0,36)` / `rgb(9,9,121)` / `rgb(0,91,255)` |
| Success / danger / warning | `--success`, `--danger`, `--warning` | `#2f9e5e`, `#d8482f`, `#b8791a` |

Dark mode and customer branding override these tokens at runtime (`frontend/components/BrandingApplier.tsx`).

Measured contrast (WCAG 2.x relative luminance, computed by `tests/test_brand_assets.py`, not estimated):

| Pair | Ratio | Meets |
|---|---|---|
| `#1c1d1d` text on `#ffffff` | 16.9 : 1 | AA and AAA, all sizes |
| `#727272` secondary text on `#ffffff` | 4.8 : 1 | AA for normal text |
| white on `#ff4b00` accent | 3.36 : 1 | AA for **large text** (18.66 px bold / 24 px regular) and for graphics only; **not** AA for normal-size text |
| white on `#e04300` accent hover | 4.22 : 1 | AA for large text; still below 4.5 for small text |
| `#ff4b00` on `#1b1b1c` ink | 5.13 : 1 | AA for normal text |
| `#1c1d1d` on `#fff0ea` accent soft | 15.2 : 1 | AA and AAA |

Consequence, stated plainly: text on an orange button must be large and bold (the landing buttons use 18 px bold, which is just under the WCAG "large text" threshold of
18.66 px: a known gap to fix by raising the button text to 19 px or darkening the accent for small buttons), small text on orange must be `#1c1d1d`, never white.

## 4. Typography
Inter (variable), with the system sans-serif stack as fallback (`--app-font`). Titles are medium or semibold, body 14-16 px, small print 12 px.

## 5. Shape and depth
Corner radius: 6 px (small), 8 px (medium), 12 px (large). Shadows: soft (`0 4px 6px rgba(0,0,0,.09)`) and medium (`0 8px 24px rgba(0,0,0,.1)`). Inputs on the dark
authentication screens are white pills with a translucent border.

## 6. Voice
Direct, factual, no superlatives. State limits plainly (what is supported, what is not). Six languages are maintained in `locales/` (en, fr, es, de, pt, ar), the
Arabic UI is right-to-left.

## 7. Do and do not
- Do keep accent orange for the single main action of a screen; do not use it for decoration.
- Do keep contrast at WCAG AA or better (check any new colour pair).
- Do not hard-code colours in components: use the tokens above so white-label customers can restyle the product.
- Do not use customer logos on the marketing site without written permission.
