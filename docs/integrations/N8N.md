# n8n Integration

Connect RAG SaaS Platform to 400+ apps via n8n's HTTP Request node.

## How it works

n8n uses a standard **HTTP Request node** to POST JSON to our inbound
webhook. No OAuth, no n8n-specific node -- just a URL + a bearer token.

## Setup

### 1. Create an Integration Connection

In RAG SaaS Platform:
1. Go to **Dashboard → Integrations**
2. Click **New connection**
3. Provider: **n8n**
4. Action: choose one of:
   - `ingest_document` — feeds payload text into the RAG pipeline
   - `log_only` — just records the payload
   - `create_agent` — creates a new Agent
   - `create_conversation` — creates a new Conversation
   - `send_notification` — sends an in-app + email notification
   - `trigger_workflow` — triggers a Workflow run
5. Copy the generated **token** (shown once)

### 2. Create an n8n Workflow

In n8n:
1. Create a new workflow
2. Add a trigger node (any app -- Gmail, Slack, HubSpot, etc.)
3. Add an **HTTP Request** node
4. Configure:
   - **Method**: `POST`
   - **URL**: `https://your-instance.example.com/integrations/{connection_id}/inbound`
   - **Authentication**: `Generic Credential Type`
   - **Generic Auth Type**: `Header Auth`
   - **Header Name**: `Authorization`
   - **Header Value**: `Bearer {your_token}`
   - **Send Body**: `true`
   - **Body Content Type**: `JSON`
   - **JSON**: `{"title": "{{ $json.subject }}", "body": "{{ $json.text }}"}`

### 3. Test

Click **Execute Workflow** in n8n. The connection's **Logs** tab in
RAG SaaS Platform shows every accepted or rejected POST.

## Self-hosted n8n

Works identically. n8n calls our webhook over the public internet (or
your private network). Make sure our webhook URL is reachable from n8n.

## Actions reference

Same as Make -- see [MAKE.md](./MAKE.md#actions-reference).

## Troubleshooting

Same as Make -- see [MAKE.md](./MAKE.md#troubleshooting).
