# @rag-saas/widget-vue

Official Vue 3 (Composition API) component wrapping the RAG SaaS Platform's real, already-built embeddable chat widget (Partie 9.3).

## Install

```bash
npm install @rag-saas/widget-vue
```

## Usage

```vue
<script setup>
import { RAGWidget } from "@rag-saas/widget-vue";
</script>

<template>
  <RAGWidget
    api-key="wgt_..."
    base-url="https://your-instance.example.com"
    theme="auto"
    position="bottom-right"
    @message="(payload) => console.log('received', payload)"
  />
</template>
```

## Composables

```vue
<script setup>
import { useRAGWidget, useRAGWidgetMessages } from "@rag-saas/widget-vue";

const { open, sendMessage } = useRAGWidget();
const messages = useRAGWidgetMessages();
</script>
```

## Design note

`<RAGWidget>` renders no DOM of its own -- it owns the lifecycle of the real, already-built `frontend/widget/embed.js` script (loaded from your instance's own `/widget/script.js`), which manages a real, sandboxed `<iframe>` for the actual chat UI. Same real design as `@rag-saas/widget-react` -- see that package's own README for the full reasoning.
