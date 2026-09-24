# Publishing the Make App

## Prerequisites

1. **Make partner account**: Register at https://www.make.com/en/partner
2. **Make Developer Hub access**: once approved as a partner
3. **GitHub repository**: public, with this app's code
4. **Documentation**: at least a README + a getting-started guide
5. **Support email**: monitored

## Steps

### 1. Create the app in Make Developer Hub

- Go to https://developers.make.com/
- Click **New app**
- Fill in: name, description, category, icon
- Upload `app.yaml` as the manifest

### 2. Configure the connection

- Type: **Bearer**
- Fields: `baseUrl`, `connectionId`, `token`
- Test URL: `{{connection.baseUrl}}/integrations/{{connection.connectionId}}/inbound`
- Test method: POST
- Test body: `{"title": "Make test"}`

### 3. Implement the modules

Each module in `app.yaml` maps to a Make action. Make validates the
manifest and generates the module UI automatically.

For dynamic field options (e.g. a dropdown of workflows), add Make
**RPC** calls in `rpc/`:
- `rpc/getWorkflows.js` → returns `[{name, label}]`
- Reference in `app.yaml` via `options: "rpc://getWorkflows"`

### 4. Add webhook triggers (optional)

If you want Make scenarios to fire when events happen in RAG SaaS
Platform, expose outbound webhooks on our side (already implemented:
`api/routers/webhooks.py`) and register them as Make **instant
triggers** in the manifest.

### 5. Submit for review

- In Make Developer Hub, click **Submit for review**
- Make's team reviews the app (typically 1-2 weeks)
- Once approved, the app appears in Make's marketplace

## Testing checklist

- [ ] Connection test passes
- [ ] Each module works with a real scenario
- [ ] Error cases return clear messages
- [ ] Documentation covers all modules
- [ ] Support contact is monitored
- [ ] Rate limits are documented

## Post-publication

- Monitor Make's **error reporting** dashboard
- Update the app when RAG SaaS Platform changes
- Add new modules as needed
