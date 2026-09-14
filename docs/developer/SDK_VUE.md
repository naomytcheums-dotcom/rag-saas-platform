# Vue SDK (`@rag-saas/widget-vue`)

Full source and README: [`sdks/vue/README.md`](../../sdks/vue/README.md).
Wraps the platform's embeddable chat widget as a Vue 3 (Composition
API) component — same design as the [React SDK](SDK_REACT.md).

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

`<RAGWidget>` renders no DOM of its own — it owns the lifecycle of the
already-built `frontend/widget/embed.js` script, same real design as
[`@rag-saas/widget-react`](SDK_REACT.md).
