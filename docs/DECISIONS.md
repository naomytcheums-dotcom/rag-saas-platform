# Decisions taken (2026-10-10)

Decisions the audit left open, with the safest choice for each. Each one can be reversed; the reason and the way back are written down.

## D1 - SAML (spec 10.4.2): keep OIDC, add SAML only on a signed customer request
- **Decision:** the platform offers OpenID Connect single sign-on (`api/routers/enterprise_sso.py`) and SCIM 2.0 provisioning. SAML 2.0 is not built.
- **Why:** SAML needs the system library `xmlsec1` and an XML-signature dependency in the production image; XML signature handling is a classic source of vulnerabilities, and the 512 MB host cannot take another native dependency. Every major identity provider (Okta, Entra ID, Google Workspace, Auth0, Keycloak) supports OIDC.
- **Way back:** when a paying customer requires SAML, add `python3-saml` behind a feature flag in a separate image, with its own security review. The `enterprise_sso_connections` model already stores a provider type.

## D2 - Tenant isolation (spec 1.3.5, audit R-01): application isolation now, database barrier staged
- **Decision:** the isolation control stays at the application layer for now and is made verifiable: route x role contract test (`tests/test_p2_viewer_route_matrix.py`), tenant-isolation tests per area, and the P0 fixes. Row Level Security is **not** switched on in production by this change.
- **Why:** turning on `FORCE ROW LEVEL SECURITY` with policies changes the behaviour of every query. A mistake locks every customer out or, worse, silently returns nothing. It cannot be validated without a PostgreSQL role that does not bypass RLS, and the current application connects with a role that does.
- **Staged plan (to be done on a staging database, never first on production):**
  1. create a dedicated application role without `BYPASSRLS`;
  2. set `app.current_org` per transaction from the authenticated membership (one dependency in `api/database.py`);
  3. pilot `FORCE RLS` plus a policy on three tables with the lowest traffic (for example `escalations`, `coupon_redemptions`, `scim_tokens`);
  4. run the whole suite against that database (the PostgreSQL tests exist, opt-in via `P0_PG_TEST_URL`) and make that job mandatory in CI;
  5. extend table by table.
- **Way back:** each step is a separate migration with a downgrade.

## D3 - Product name and logo (spec 14.4.1, 14.4.2): unchanged until the owner chooses
- **Decision:** the working name stays "RAG SaaS Platform". No name or logo is invented. `docs/commercial/BRAND_GUIDE.md` lists exactly what to change once a name is chosen (site title, e-mail sender, widget title, PDFs); all customer-facing text is in `locales/`.
- **Before choosing:** check the name in the trademark databases of the target markets, the `.com` / `.ai` domains and the app-store / npm / PyPI namespaces.

## D4 - End-to-end browser tests (spec 13.2.4, 13.3.7): Playwright in a separate package
- **Decision:** `e2e/` is its own npm package (Playwright 1.49.1, uses the Chrome already installed, no browser download). It starts the isolated API (SQLite, every external service blanked, refuses non-local URLs) and the frontend, and never touches production.
- **Why separate:** no change to the dependencies of the shipped frontend; the tests are opt-in (`cd e2e && npm install && npx playwright test`).

## D5 - Promo codes of type percent-off
- **Decision:** recorded at redemption, not applied automatically at checkout.
- **Why:** applying a discount to Stripe / Paystack needs provider-side coupon objects and has to be validated in each provider's sandbox with the owner's test keys.
