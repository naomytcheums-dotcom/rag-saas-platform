# Embedding the widget (script tag, iframe, or the JS SDK)

Partie 9.3.1/9.3.13/9.3.14. Three real ways to embed the chat widget, in increasing order of control.

## 1. Script tag (recommended -- zero JS knowledge required)

```html
<script src="https://your-instance.example.com/widget/script.js" data-key="wgt_..."></script>
```

That's it. The script:

1. Fetches your widget's public configuration (`GET /widget/config?key=wgt_...`).
2. Renders a launcher button at the configured position.
3. On click, opens a real, sandboxed `<iframe>` pointing at `/widget/iframe?key=wgt_...`, which runs the actual chat UI.

Your real, **secret** `OrganizationAPIKey` (Partie 9.1/9.2) is never used or exposed here -- only the widget's own real, non-secret `public_key` (`wgt_...`, from `WidgetConfig.public_key`). See `api/security/widget_auth.py`'s own docstring for the full security model: the browser exchanges that public key for a short-lived session token (`POST /widget/session`) before it can send a single chat message.

### Manual init

Add `data-manual-init="true"` to skip auto-init, then call `window.RAGWidget.init()` yourself once your own page logic is ready.

## 2. iframe (for sites that can't load arbitrary JavaScript)

```html
<iframe src="https://your-instance.example.com/widget/iframe?key=wgt_..." width="380" height="600" style="border:none"></iframe>
```

This renders the exact same chat UI without any of the launcher-button/open-close chrome -- you control the sizing and placement yourself in your own page's CSS.

## 3. Programmatic control (`window.RAGWidget`)

Once the script tag has loaded, a global API is available:

```js
window.RAGWidget.open();
window.RAGWidget.close();
window.RAGWidget.toggle();
window.RAGWidget.sendMessage("What is RAG?");
window.RAGWidget.on("message:received", (payload) => console.log(payload));
window.RAGWidget.updateConfig({ theme: "dark" });
window.RAGWidget.destroy();
```

Events: `open`, `close`, `ready`, `message:sent`, `message:received`, `error`, `theme:changed`.

For a React or Vue application, use `@rag-saas/widget-react` or `@rag-saas/widget-vue` instead of the raw script tag -- see [REACT.md](./REACT.md) and [VUE.md](./VUE.md).

## Caching

`/widget/script.js`, `/widget/embed.js`, `/widget/chat.js` and `/widget/styles.css` are served with `Cache-Control: public, max-age=<WIDGET_SCRIPT_CACHE_TIME>` (3600s by default).
