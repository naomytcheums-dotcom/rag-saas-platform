# Customizing the widget

Every field below lives on ONE real `WidgetConfig` row per organization (Partie 9.3.2-9.3.10) -- see `api/models/widget.py`'s own top docstring for why this is deliberately one consolidated model rather than nine separate ones.

All admin (Member+) endpoints below are scoped under `/organizations/{org_id}/widget/...` and require a real, authenticated session (`Authorization: Bearer <access_token>`), unlike the widget's own public `GET` endpoints.

## Logo (9.3.2)

```
POST   /organizations/{org_id}/widget/logo    (multipart file upload)
GET    /widget/logo?key=wgt_...
DELETE /organizations/{org_id}/widget/logo
```

PNG/JPEG/WEBP only, up to `WIDGET_LOGO_MAX_SIZE` (5MB default). SVG is deliberately not accepted -- see `api/config.py`'s own comment on `WIDGET_LOGO_ALLOWED_TYPES` for the real security reasoning (an SVG can embed a script).

## Colors (9.3.3)

```
PATCH /organizations/{org_id}/widget/config
{ "primary_color": "#6C63FF", "secondary_color": "#4A47A3", "text_color": "#FFFFFF",
  "background_color": "#FFFFFF", "header_background": "#6C63FF", "border_radius": "12px", "font_family": "system-ui" }
```

Every color is validated as a real hex string (`#rgb`, `#rrggbb`, or `#rrggbbaa`).

## Name (9.3.4)

```
PATCH /organizations/{org_id}/widget/config/name
{ "name": "Support Bot" }
```

2-50 characters. A short name (used in notifications) is auto-derived from the first word.

## Avatar (9.3.5)

```
POST   /organizations/{org_id}/widget/avatar    (multipart file upload)
GET    /widget/avatar?key=wgt_...
DELETE /organizations/{org_id}/widget/avatar
PATCH  /organizations/{org_id}/widget/avatar/default
```

Falls back to a real, generated initial-letter avatar when none is uploaded.

## Welcome message (9.3.6)

```
PATCH /organizations/{org_id}/widget/welcome
{ "message": "Hi! How can I help you today?" }

POST  /organizations/{org_id}/widget/welcome/reset
```

10-500 characters, HTML sanitized (`<p>`, `<br>`, `<strong>`, `<em>` only -- everything else, including `<script>`, is stripped).

## Suggested questions (9.3.7)

```
GET    /widget/suggested-questions?key=wgt_...                          (public, active only)
GET    /organizations/{org_id}/widget/suggested-questions/admin          (all, including inactive)
POST   /organizations/{org_id}/widget/suggested-questions
PATCH  /organizations/{org_id}/widget/suggested-questions/{id}
DELETE /organizations/{org_id}/widget/suggested-questions/{id}
PATCH  /organizations/{org_id}/widget/suggested-questions/reorder
```

Up to `SUGGESTED_WIDGET_QUESTIONS_MAX` (6) real, admin-curated questions, each with its own order. Distinct from the internal chat's own dynamic, LLM/popular/recent-derived suggestions (Partie 8.1.17) -- see `api/models/widget.py`'s own docstring.

## Position (9.3.8)

```
PATCH /organizations/{org_id}/widget/position
{ "position": "bottom-right", "offset_x": 20, "offset_y": 20, "position_locked": false }
```

`position` is one of `bottom-right`, `bottom-left`, `top-right`, `top-left`. `offset_x`/`offset_y` are pixel offsets from the chosen corner, `0`-`100`.

## Language (9.3.9)

```
GET   /widget/languages                                    (real, supported languages)
GET   /widget/language?key=wgt_...
PATCH /organizations/{org_id}/widget/language
{ "language": "fr" }
```

Reuses the platform's own real, existing 6-language list (`en`/`fr`/`es`/`de`/`pt`/`ar`, Partie 8.1.19) rather than a second, separate widget-only list -- see `api/services/widget.py`'s own docstring. With `auto_detect_language` enabled (default), the visitor's own browser `Accept-Language` header decides instead.

## Theme (9.3.10)

```
GET   /widget/theme?key=wgt_...
PATCH /organizations/{org_id}/widget/theme
{ "theme": "dark", "theme_custom_css": ".rw-app{ font-size: 15px; }" }

POST  /organizations/{org_id}/widget/theme/reset
```

`theme` is `light`, `dark`, or `auto` (follows the visitor's OS preference). `theme_custom_css` is sanitized (rejects `javascript:`, `expression(`, `@import`, `<script`) and capped at `WIDGET_CUSTOM_CSS_MAX_SIZE` (10,000 characters).
