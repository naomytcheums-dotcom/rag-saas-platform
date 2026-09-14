# Chat API

Backed by `api/routers/chat_stream.py` and `api/routers/conversations.py`.
See [Chat](../user/CHAT.md) for end-user behavior.

Conversations and messages are not nested under `/organizations/{org_id}/`
in this router — the conversation itself already carries its owning
organization, so paths are flat (`/conversations/...`).

## Create a conversation

```
POST /conversations
```

Optionally specify `agent_id` to target a specific [agent](AGENTS.md)
instead of the default assistant.

## Send a message (streaming)

```
POST /conversations/{conversation_id}/messages
```

Response is a streamed sequence of chunks (server-sent events), ending
with the final message including citations. Client SDKs handle the
stream for you — see [SDKs](../developer/OVERVIEW.md).

## Editing, retrying, regenerating

```
POST /conversations/{conversation_id}/messages/{message_id}/edit
POST /conversations/{conversation_id}/messages/{message_id}/retry
POST /conversations/{conversation_id}/messages/{message_id}/regenerate
POST /conversations/{conversation_id}/messages/{message_id}/revert
GET  /conversations/{conversation_id}/messages/{message_id}/edit-history
```

## Citations

Each assistant message includes a `citations` array referencing the
specific document chunks used to ground the answer — see
[Citations](../user/CITATIONS.md).

## Feedback

Feedback is a separate resource — see `api/routers/feedback.py` —
thumbs up/down plus an optional note.

## Exporting

```
GET /conversations/{conversation_id}/export/markdown
GET /conversations/{conversation_id}/export/json
GET /conversations/{conversation_id}/export/pdf
GET /conversations/{conversation_id}/export/docx
```

## Sharing

```
POST /conversations/{conversation_id}/share
GET  /conversations/{conversation_id}/shares
```

`api/routers/conversation_shares.py` — see
[Conversations](../user/CONVERSATIONS.md#sharing).

## Archive, restore, delete

```
POST   /conversations/{conversation_id}/archive
POST   /conversations/{conversation_id}/restore
DELETE /conversations/{conversation_id}
DELETE /conversations/{conversation_id}/permanent
```
