# Tutorial: Embed the Widget on Your Site

See [Widget Embed](../developer/WIDGET_EMBED.md) for full reference.

## 1. Create a widget key

Under **Admin → Widget**, create a widget key (`wgt_...`) scoped to the
agent you want to expose.

## 2. Add the script tag

```html
<script
  src="https://your-instance.example.com/widget/script.js"
  data-api-key="wgt_..."
  data-theme="auto"
  data-position="bottom-right">
</script>
```

Full snippet options: [`docs/widget/SCRIPT_TAG.md`](../widget/SCRIPT_TAG.md).

## 3. Customize

Theme, position, and branding — see
[`docs/widget/CUSTOMIZATION.md`](../widget/CUSTOMIZATION.md).

## 4. React or Vue instead

If your site is a React or Vue app, use the component wrapper instead
of a raw script tag — see [React SDK](../developer/SDK_REACT.md) or
[Vue SDK](../developer/SDK_VUE.md).

## 5. Test it

Load your page, confirm the chat bubble appears, and send a test
message — check it answers using your organization's documents, with
citations.
