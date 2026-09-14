# React SDK (`@rag-saas/widget-react`)

Full source and README: [`sdks/react/README.md`](../../sdks/react/README.md).
Wraps the platform's embeddable chat widget as a React component
(React 16.8+, hooks).

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

`<RAGWidget>` renders nothing itself — it owns the lifecycle of the
already-built `frontend/widget/embed.js` script (loaded from your
instance's own `/widget/script.js`), which manages a sandboxed
`<iframe>` for the actual chat UI. This avoids reimplementing widget UI
logic (streaming, session tokens, suggested questions, i18n) a second
time in React. See also [Widget Embed](WIDGET_EMBED.md) for the plain
script-tag version this wraps.
