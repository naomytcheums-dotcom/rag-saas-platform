# Widget Embed

The plain script-tag embed for the platform's chat widget. For a React
or Vue wrapper instead, see [SDK_REACT.md](SDK_REACT.md) /
[SDK_VUE.md](SDK_VUE.md) — both wrap this same script.

## Script tag

See [`docs/widget/SCRIPT_TAG.md`](../widget/SCRIPT_TAG.md) for the
exact snippet to drop into your site's HTML.

## Customization

Theme, position, and branding options are covered in
[`docs/widget/CUSTOMIZATION.md`](../widget/CUSTOMIZATION.md).

## Worked examples

[`docs/widget/EXAMPLES.md`](../widget/EXAMPLES.md) has copy-pasteable
examples for common setups.

## How it works

The widget script manages a sandboxed `<iframe>` for the chat UI and
authenticates with a widget API key (`wgt_...`), distinct from an
organization's general API key. Message events are dispatched to your
page for you to react to (e.g. analytics, custom UI triggers).
