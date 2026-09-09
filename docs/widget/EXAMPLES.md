# Widget integration examples

## Plain HTML site (script tag)

```html
<!DOCTYPE html>
<html>
<body>
  <h1>Welcome to our site</h1>
  <script src="https://your-instance.example.com/widget/script.js" data-key="wgt_your_public_key"></script>
</body>
</html>
```

## iframe-only site

```html
<div style="position:fixed;bottom:20px;right:20px;width:380px;height:600px;">
  <iframe src="https://your-instance.example.com/widget/iframe?key=wgt_your_public_key"
          width="100%" height="100%" style="border:none;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.25);"></iframe>
</div>
```

## React

```tsx
import { RAGWidget } from "@rag-saas/widget-react";

<RAGWidget apiKey="wgt_your_public_key" baseUrl="https://your-instance.example.com" theme="auto" />
```

## Vue

```vue
<RAGWidget api-key="wgt_your_public_key" base-url="https://your-instance.example.com" theme="auto" />
```

## Programmatic control from your own page's JavaScript

```html
<script src="https://your-instance.example.com/widget/script.js" data-key="wgt_..." data-manual-init="true"></script>
<script>
  window.RAGWidget.init();
  document.getElementById("help-button").addEventListener("click", () => window.RAGWidget.open());
  window.RAGWidget.on("message:received", (payload) => {
    console.log("Assistant replied:", payload.response);
  });
</script>
```
