# 05 — Frontend : pages et parcours

Audit du 2026-10-10, HEAD `59d5ec9`. **57 fichiers `page.tsx`** (décompte direct `Get-ChildItem` et `git ls-files`, concordants), 10 `layout.tsx`, 1 `error.tsx`, 6 `loading.tsx`, 0 `not-found.tsx`, 0 `route.ts`, 187 composants, 27 fichiers de test vitest (178 tests réussis le 2026-10-10).

**Limite essentielle** : aucune page n'a été ouverte dans un navigateur, aucun parcours cliqué, aucune capture produite. Les classifications ci-dessous sont des **déductions statiques** (appels `api.*`/hooks visibles) ; « UI et backend intégrés » signifie « un appel à une route existante est présent dans le code », pas « le parcours fonctionne ».

## Routes (liste exhaustive, générée depuis le disque)
`/` · `/login` · `/register` · `/forgot-password` · `/reset-password` · `/restore-account` · `/reactivate-consent` · `/2fa-lockout-recovery` · `/invitations/accept` · `/oauth-callback` · `/voice-demo` · `/maquette` · `/chat` · `/admin` · `/dashboard` · `/dashboard/documents` · `/dashboard/agents` · `/dashboard/agents/new` · `/dashboard/agents/factory` · `/dashboard/analytics` (+ `/business`, `/product`, `/technical`) · `/dashboard/api-docs` · `/dashboard/autonomous-agents` (+ `/[id]`) · `/dashboard/ab-tests` (+ `/[id]`) · `/dashboard/billing` · `/dashboard/eval` (+ `/[datasetId]`, `/[datasetId]/jobs/[jobId]`, `/evolution`, `/runs/[runId]/comparison`) · `/dashboard/fine-tuning` (+ `/datasets`, `/jobs`, `/jobs/[id]`, `/models`) · `/dashboard/marketplace` · `/dashboard/media` (+ `/[id]`) · `/dashboard/partners` · `/dashboard/profile` · `/dashboard/quality` · `/dashboard/security` · `/dashboard/settings/{api-keys, integrations, llm-config, organization, webhooks, white-label, widget}` · `/dashboard/voice-agent` · `/dashboard/whitelabel` · `/dashboard/workflows` (+ `/[id]`).

## Éléments établis
- **MAP-001 et MAP-003 corrigés** : `/invitations/accept`, `/oauth-callback`, `/restore-account`, `/reactivate-consent`, `/2fa-lockout-recovery` existent ; un test de contrat backend (`tests/test_p1_frontend_link_contract.py`, `tests/test_p2_map003_emailed_links_have_pages.py`) échoue si un lien e-mailé n'a pas de page. Tests vitest : `app/invitations/accept`, `components/auth/TokenConfirmForm.test.tsx`.
- Les pages MAP-003 n'envoient **rien au chargement** (anti-prévisualisation de courrier) : le jeton est posté seulement au clic.
- `/maquette` : page de maquette — **données fictives probables** (aucun appel API identifié par le sous-agent) : NON DÉTERMINÉ quant à son usage.
- Pages de **demande** de restauration/réactivation (côté « request ») : **absentes** (aucune route frontend pour `POST /account/restore/request` et `/account/consent/reactivate/request` identifiée) → fonctionnalité backend sans interface (**CONFIRMÉ par recherche textuelle** : aucune occurrence de `restore/request`, `consent/reactivate/request`, `lockout-recovery/request` dans `frontend/**/*.ts(x)`).
- Markdown : `react-markdown` + `rehype-sanitize` dans les dépendances ; test `ChatMarkdown.test.tsx` présent.
- Exposition admin : `/admin` (statistiques, liens vers `/docs` et `/metrics`) ; les contrôles de rôle côté client n'ont pas été relus ; la protection effective est côté API (`require_superadmin`/`require_admin`).
- Pas de `not-found.tsx` dédié ; un seul `error.tsx` : gestion des erreurs de route **minimale** (observation, pas un défaut démontré).
- Variables front : `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SENTRY_DSN`, `NEXT_PUBLIC_ENVIRONMENT`, `NEXT_PUBLIC_SOCIAL_*` (noms seulement).
- i18n : bundles dans `frontend/lib` (`i18n-bundled.test.ts`), 18 fichiers `locales/` suivis à la racine.

## Non établi
Responsive/mobile, accessibilité réelle, états de chargement/vide/erreur page par page, liens morts exhaustifs, données mockées exhaustives, fonctionnalités derrière des flags.

---
## Annexe — Exploration automatisée « frontend + déploiement »
*(rapport d'un sous-agent en lecture seule ; **erreur corrigée** : il annonce 74 fichiers `page.tsx`, le décompte direct donne 57 ; sa colonne « classification » est une déduction par import de hook/service, non une preuve d'intégration)*

<!-- ANNEXE_AJOUTEE -->
#### B. Frontend Next.js — routes

Les appels ci-dessous incluent les appels directs de la page ; les hooks/services importés encapsulent fréquemment les endpoints. Quand aucun appel littéral n’est visible dans la page, l’appel est indiqué comme « hook/service importé ».

| Route | Purpose | Backend calls | Classification |
|---|---|---|---|
| `/` | Landing page | `LandingSections` peut appeler API pour pricing | UI présente avec backend partiel |
| `/login` | Connexion/MFA | `/auth/2fa/verify-login` — `app/login/page.tsx` | UI et backend intégrés |
| `/register` | Inscription | service auth | UI et backend intégrés |
| `/forgot-password` | Demande reset | service auth | UI et backend intégrés |
| `/reset-password` | Nouveau mot de passe | service auth | UI et backend intégrés |
| `/restore-account` | Restauration compte | service auth | UI et backend intégrés |
| `/reactivate-consent` | Consentement réactivation | service auth | UI et backend intégrés |
| `/2fa-lockout-recovery` | Récupération 2FA | service auth | UI et backend intégrés |
| `/invitations/accept` | Accepter invitation | service invitation | UI et backend intégrés |
| `/oauth-callback` | Callback OAuth | service OAuth | UI et backend intégrés |
| `/voice-demo` | Démo vocale | `voiceApi` | UI et backend intégrés |
| `/maquette` | Maquette UI | aucun appel identifié | UI avec données fictives |
| `/chat` | Chat RAG | `useRealChat`, historique/conversations | UI et backend intégrés |
| `/admin` | Statistiques/admin | `GET /admin/stats`, `/docs`, `/metrics` — `app/admin/page.tsx` | UI et backend intégrés |
| `/dashboard` | Vue synthèse | hooks dashboard/metrics/history | UI et backend intégrés |
| `/dashboard/documents` | Documents/upload | documents API, upload/processing | UI et backend intégrés |
| `/dashboard/agents` | Liste agents | agents service/hook | UI et backend intégrés |
| `/dashboard/agents/new` | Création agent | agents service | UI et backend intégrés |
| `/dashboard/agents/factory` | Agent factory | agents service | UI et backend intégrés |
| `/dashboard/analytics` | Analytics | `useAnalytics`/dashboards | UI et backend intégrés |
| `/dashboard/analytics/business` | Metrics business | analytics service | UI et backend intégrés |
| `/dashboard/analytics/product` | Metrics produit | analytics service | UI et backend intégrés |
| `/dashboard/analytics/technical` | Metrics techniques | analytics service | UI et backend intégrés |
| `/dashboard/api-docs` | Documentation API | base `NEXT_PUBLIC_API_URL` | UI avec backend partiel |
| `/dashboard/autonomous-agents` | Agents autonomes | autonomous-agent hooks | UI et backend intégrés |
| `/dashboard/autonomous-agents/[id]` | Détail agent autonome | autonomous-agent hook | UI et backend intégrés |
| `/dashboard/ab-tests` | A/B tests | `useABTests`/services | UI et backend intégrés |
| `/dashboard/ab-tests/[id]` | Détail A/B test | AB-test services | UI et backend intégrés |
| `/dashboard/billing` | Abonnement/facturation | checkout/billing API | UI et backend intégrés |
| `/dashboard/eval` | Jeux d’évaluation | eval hooks | UI et backend intégrés |
| `/dashboard/eval/[datasetId]` | Dataset eval | eval hooks | UI et backend intégrés |
| `/dashboard/eval/[datasetId]/jobs/[jobId]` | Job eval | eval hooks | UI et backend intégrés |
| `/dashboard/eval/evolution` | Évolution eval | eval services | UI et backend intégrés |
| `/dashboard/eval/runs/[runId]/comparison` | Comparaison runs | eval services | UI et backend intégrés |
| `/dashboard/fine-tuning` | Synthèse fine-tuning | fine-tuning hooks | UI et backend intégrés |
| `/dashboard/fine-tuning/datasets` | Datasets | fine-tuning service | UI et backend intégrés |
| `/dashboard/fine-tuning/jobs` | Jobs | fine-tuning service | UI et backend intégrés |
| `/dashboard/fine-tuning/jobs/[id]` | Job détail | fine-tuning service | UI et backend intégrés |
| `/dashboard/fine-tuning/models` | Modèles | fine-tuning service | UI et backend intégrés |
| `/dashboard/marketplace` | Marketplace/plugins | plugins hooks | UI et backend intégrés |
| `/dashboard/media` | Médias | `useMedia`, upload/processing | UI et backend intégrés |
| `/dashboard/media/[id]` | Média détail | media hook | UI et backend intégrés |
| `/dashboard/partners` | Partenaires | partner components/API | UI avec backend partiel |
| `/dashboard/profile` | Profil | auth/profile API | UI et backend intégrés |
| `/dashboard/quality` | Qualité | metrics/quality API | UI et backend intégrés |
| `/dashboard/security` | Sécurité | principalement affichage/liens | UI présente avec backend partiel |
| `/dashboard/settings/api-keys` | Clés API | API-key endpoints | UI et backend intégrés |
| `/dashboard/settings/integrations` | Intégrations | integrations endpoints | UI et backend intégrés |
| `/dashboard/settings/llm-config` | Configuration LLM | provider/config endpoints | UI et backend intégrés |
| `/dashboard/settings/organization` | Organisation | organization endpoints | UI et backend intégrés |
| `/dashboard/settings/webhooks` | Webhooks | webhook endpoints | UI et backend intégrés |
| `/dashboard/settings/white-label` | White-label | whitelabel hooks | UI et backend intégrés |
| `/dashboard/settings/widget` | Widget | widget config + `/widget/script.js`, `/widget/iframe` | UI et backend intégrés |
| `/dashboard/voice-agent` | Agent vocal | `voiceApi` | UI et backend intégrés |
| `/dashboard/whitelabel` | Preview white-label | whitelabel hooks | UI et backend intégrés |
| `/dashboard/workflows` | Workflows | workflow hooks/services | UI et backend intégrés |
| `/dashboard/workflows/[id]` | Workflow détail | workflow services | UI et backend intégrés |

##### Frontend — constats transversaux

- Hooks/services API : `frontend/lib/hooks/*`, `frontend/lib/services/*`, `frontend/lib/api.ts`.
- Données mockées ou placeholders détectés surtout dans la maquette et les composants de démonstration ; les composants de test utilisent explicitement `vi.mock`.
- États loading : layouts/loading dédiés notamment pour analytics, autonomous agents, fine-tuning, media et whitelabel.
- États d’erreur/empty : présents dans plusieurs dashboards (`error`, `loading`, messages empty), mais couverture uniforme non établie.
- Liens morts : aucun lien évident vers une route complètement absente dans l’échantillon contrôlé ; les liens dynamiques et composants importés nécessitent une vérification exhaustive.
- Admin/superadmin : `/admin` existe et appelle `/admin/stats`; la protection de route côté serveur et l’autorisation réelle backend ne peuvent pas être déduites de la seule UI. Le lien vers `/docs` et `/metrics` est exposé dans l’interface admin — `frontend/app/admin/page.tsx`.
- Permissions client-side : aucune preuve suffisante d’une protection exclusivement côté client ; statut d’autorisation **indéterminé**.
- i18n : `useTranslation`/`t(...)`, `LanguageMenu`, langues configurées côté API (`UI_SUPPORTED_LANGUAGES`) ; certains textes restent littéraux en anglais/français dans les pages.
- A11y : présence d’`aria-label`, `aria-hidden`, `role="alert"` et labels sur plusieurs composants (`frontend/components/AudioPermission.tsx`, `Chat*`). Audit WCAG complet non établi.
- Markdown : configuration de rendu visible dans `frontend/components/ChatMarkdown.tsx`; présence exacte de `rehype-sanitize` non confirmée par les recherches ciblées. L’API possède en revanche une allow-list markdown dans `api/config.py`.
- Tests frontend : notamment `frontend/lib/api.test.ts`, `api-errors.test.ts`, `currency.test.ts`, `i18n-bundled.test.ts`, `app/admin/page.test.tsx`, `app/dashboard/page.test.tsx`, `app/dashboard/agents/agents-pages.test.tsx`, `app/invitations/accept/page.test.tsx`, `app/oauth-callback/page.test.tsx`, `app/dashboard/billing/*test.tsx`, `components/**/*.test.tsx`.

#### Questions non établies

1. Le `render.yaml` actuellement versionné est-il réellement utilisé, ou a-t-il été remplacé par une configuration Render manuelle ?
2. Qui exécute les migrations Alembic en production, et selon quelle procédure de rollback ?
3. Le backend Render, Redis, Supabase, Vercel et les workers sont-ils actuellement disponibles ? **NON VÉRIFIÉ — aucun réseau utilisé.**
4. Les autorisations `/admin`, `/metrics` et `/docs` sont-elles effectivement protégées côté backend ?
5. `rehype-sanitize` est-il installé/configuré dans le composant Markdown final ?
6. Quelle est la procédure officielle de sauvegarde/restauration et quels sont les RPO/RTO ?
7. Le worker Celery planifié GitHub est-il une solution temporaire acceptée pour la production ?
8. Les variables obligatoires de `api/config.py` sont-elles toutes présentes dans chaque environnement dev/test/staging/prod ?
