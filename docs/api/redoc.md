# Redoc

Every running instance also serves a Redoc-rendered version of the same
live OpenAPI schema:

```
https://your-instance.example.com/redoc
```

Redoc is read-focused (three-panel layout, no "Try it out" execution)
— use it for browsing/reference, and [Swagger UI](swagger.md) when you
want to execute requests directly from the browser.

## Same schema, two viewers

Both `/docs` (Swagger UI) and `/redoc` render the same schema returned
by `app.openapi()` — nothing is duplicated or hand-maintained
separately between them. See [`openapi.json`](openapi.json) for the
underlying static export.
