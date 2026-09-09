<script setup lang="ts">
import { toRef } from "vue";
import type { RAGWidgetProps } from "./RAGWidget.types";
import { useRAGWidgetLifecycle } from "./composables";

const props = defineProps<RAGWidgetProps>();
const emit = defineEmits<{
  open: [];
  close: [];
  message: [payload: unknown];
  error: [payload: { message: string }];
}>();

const propsRef = toRef(props);
const { open, close, toggle, sendMessage } = useRAGWidgetLifecycle(propsRef, emit as (event: "open" | "close" | "message" | "error", payload?: unknown) => void);

defineExpose({ open, close, toggle, sendMessage });
</script>

<template>
  <!-- Real, deliberate: renders nothing of its own -- see this
       package's own README for why (the real chat UI lives inside a
       real, sandboxed iframe the widget script itself manages). -->
</template>
