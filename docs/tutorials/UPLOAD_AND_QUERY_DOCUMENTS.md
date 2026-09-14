# Tutorial: Upload & Query Documents via the API

## 1. Get an API key

Create one under your organization's developer settings — see
[Authentication](../api/AUTHENTICATION.md).

## 2. Upload a document

```bash
curl -X POST "https://your-instance.example.com/organizations/$ORG_ID/documents" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@handbook.pdf"
```

Response includes the document's `id` and `status: "processing"`.

## 3. Poll for completion

```bash
curl "https://your-instance.example.com/documents/$DOCUMENT_ID/status" \
  -H "Authorization: Bearer $API_KEY"
```

Wait for `status: "ready"` — or subscribe to `document.processed` via
[Webhooks](../api/WEBHOOKS.md) instead of polling.

## 4. Query it

```bash
curl -X POST "https://your-instance.example.com/conversations" \
  -H "Authorization: Bearer $API_KEY" -d '{}'
# then
curl -X POST "https://your-instance.example.com/conversations/$CONVERSATION_ID/messages" \
  -H "Authorization: Bearer $API_KEY" -d '{"content": "What is the vacation policy?"}'
```

See [Chat API](../api/CHAT.md) for the full streaming response shape,
or use an [SDK](../developer/OVERVIEW.md) to skip the raw HTTP.
