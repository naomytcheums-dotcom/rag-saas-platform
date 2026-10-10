# Brand guide (spec 14.4.1 - 14.4.4)

This guide documents the visual identity **as implemented** in the application (`frontend/app/globals.css`, `frontend/components/figma/`, `frontend/components/landing/`).
It is a record of what exists, not a new design.

## 1. Product name
The repository and the product are currently called **RAG SaaS Platform**. Earlier planning documents use "KnowFlow AI" as a working name. **The commercial name has
not been decided**: choose it before any public launch, then change the site title (`frontend/app/layout.tsx`), the e-mail sender name (`EMAIL_FROM_ADDRESS`), the
widget title and the PDFs under `deliverables/`. Every customer-facing string comes from `locales/*/common.json`, so a rename is a text change, not a code change.

## 2. Logo
No final logo file is committed: the header uses a text wordmark (`frontend/components/figma/SiteHeader.tsx`). Provide an SVG (square and horizontal versions) and
place it in `frontend/public/brand/`. Organizations can replace it per customer through white-label settings (logo, favicon, name).

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
