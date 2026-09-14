# Pagination

List endpoints use offset/limit query parameters:

```
GET /organizations/{org_id}/documents?limit=20&offset=40
```

## Response shape

```json
{
  "items": ["..."],
  "total": 137,
  "limit": 20,
  "offset": 40
}
```

## Defaults and maximums

`limit` defaults to a moderate page size (typically 20-50 depending on
the endpoint) and is capped server-side — requesting a larger `limit`
than the endpoint's maximum is clamped, not rejected.

## Iterating a full list

```python
items = []
offset = 0
while True:
    page = client.get(f"/organizations/{org_id}/documents", params={"limit": 100, "offset": offset})
    items.extend(page["items"])
    if len(items) >= page["total"]:
        break
    offset += 100
```

Check the specific endpoint's schema (via [Swagger UI](swagger.md)) for
any endpoint-specific pagination differences — a handful of endpoints
with naturally small result sets (e.g. organization settings) don't
paginate at all.
