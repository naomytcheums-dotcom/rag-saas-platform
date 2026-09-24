# Make (Integromat) Integration

Connect RAG SaaS Platform to 2000+ apps via Make's HTTP module.

## How it works

Make uses a standard **HTTP module** to POST JSON to our inbound webhook.
No OAuth, no Make-specific app -- just a URL + a bearer token.

## Setup

### 1. Create an Integration Connection

In RAG SaaS Platform:
1. Go to **Dashboard → Integrations**
2. Click **New connection**
3. Provider: **Make (Integromat)**
4. Action: choose one of:
   - `ingest_document` — feeds payload text into the RAG pipeline
   - `log_only` — just records the payload
   - `create_agent` — creates a new Agent
   - `create_conversation` — creates a new Conversation
   - `send_notification` — sends an in-app + email notification
   - `trigger_workflow` — triggers a Workflow run
5. Copy the generated **token** (shown once)

### 2. Create a Make Scenario

In Make:
1. Create a new scenario
2. Add a trigger (any app -- Gmail, Slack, HubSpot, etc.)
3. Add an **HTTP → Make a request** module
4. Configure:
   - **URL**: `https://your-instance.example.com/integrations/{connection_id}/inbound`
   - **Method**: `POST`
   - **Headers**:
     - `Authorization: Bearer {your_token}`
     - `Content-Type: application/json`
   - **Body type**: `Raw`
   - **Content type**: `JSON (application/json)`
   - **Request content**: `{"title": "{{1.subject}}", "body": "{{1.text}}"}`

### 3. Test

Click **Run once** in Make. The connection's **Logs** tab in RAG SaaS Platform
shows every accepted or rejected POST, with the payload.

## Actions reference

| Action | Payload example | Effect |
|--------|----------------|--------|
| `ingest_document` | `{"title": "X", "body": "..."}` | New document ingested |
| `log_only` | any JSON | Recorded in IntegrationLog only |
| `create_agent` | `{"name": "X", "system_prompt": "..."}` | New Agent created |
| `create_conversation` | `{"title": "X"}` | New Conversation created |
| `send_notification` | `{"title": "X", "body": "..."}` | In-app + email notification sent |
| `trigger_workflow` | `{"workflow_name": "X", ...}` | Workflow run triggered |

## Field mappings

Optional per-connection field renaming lets you normalize Make's payload
before the action runs (e.g. rename `subject` → `title`).

Configure in: **Dashboard → Integrations → {connection} → Mappings**.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| 401 | Wrong or missing token | Copy the token again from the connection |
| 400 | Malformed JSON body | Check Make's JSON syntax |
| 404 | Wrong connection_id | Verify the URL |
| 500 | Action failed | Check the Logs tab for the real error |
