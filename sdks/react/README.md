# @rag-saas/widget-react

Official React component wrapping the RAG SaaS Platform's real, already-built embeddable chat widget (Partie 9.3). Compatible with React 16.8+ (hooks).

## Install

```bash
npm install @rag-saas/widget-react
```

## Usage

```tsx
import { RAGWidget } from "@rag-saas/widget-react";

function App() {
  return (
    <RAGWidget
      apiKey="wgt_..."
      baseUrl="https://your-instance.example.com"
      theme="auto"
      position="bottom-right"
      onMessage={(payload) => console.log("received", payload)}
    />
  );
}
```

## Hooks

```tsx
import { useRAGWidget, useRAGWidgetMessages } from "@rag-saas/widget-react";

function ChatControls() {
  const { open, sendMessage } = useRAGWidget();
  const messages = useRAGWidgetMessages();
  return <button onClick={open}>Open chat ({messages.length} messages)</button>;
}
```

## Design note

`<RAGWidget>` renders nothing itself (`return null`) -- it owns the lifecycle of the real, already-built `frontend/widget/embed.js` script (loaded from your instance's own `/widget/script.js`), which manages a real, sandboxed `<iframe>` for the actual chat UI. This is a deliberate choice: reimplementing that UI a second time in React would duplicate real, tested logic (streaming, session tokens, suggested questions, i18n) that already exists and is already exercised by `tests/test_widget.py`. There is therefore no `RAGWidget.css` either -- there is no DOM here to style.

A non-2xx script load surfaces through the `onError` prop, same as every other real failure path.
