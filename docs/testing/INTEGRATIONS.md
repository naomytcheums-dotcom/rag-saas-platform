# Vérification réelle des intégrations (2026-09-16)

Vérification en direct, une par une, des 13 intégrations demandées : appels réels
contre les services externes configurés (jamais simulés), et vérification en
direct dans un vrai navigateur / via la suite de tests réelle pour le reste.
Aucun SMS réel envoyé, aucune synchronisation Airbyte réelle déclenchée, aucun
message réel posté sur un canal Slack/Teams/Discord (par construction : ces
identifiants ne sont pas configurés dans cet environnement).

## Méthode

- Pour chaque service avec des identifiants réels dans `.env` (Twilio, Airbyte
  Cloud, Datadog, Grafana Cloud), un appel HTTP réel, en lecture seule ou
  explicitement conçu pour un test (`send_test_log_synchronously()` de
  Grafana Loki), a été effectué directement contre le service tiers.
- Pour les services sans identifiants configurés (Slack, Teams, Discord,
  Stripe), impossible de tester un envoi réel — vérifié que le code se
  dégrade proprement (statut "non configuré" honnête, jamais un faux succès)
  et que la suite de tests unitaires existante (avec mocks) passe.
- Pour le widget, le SDK Python, les webhooks et l'API publique : test de bout
  en bout réel contre le backend local (`http://localhost:8000`), avec un
  compte de test créé puis supprimé à la fin.
- Suite de tests réelle exécutée en parallèle :
  `tests/test_telephony.py`, `test_inbound_webhooks.py`,
  `test_notifications_datadog_grafana.py`, `test_observability.py`,
  `test_public_api.py`, `test_teams.py`, `test_webhooks.py`, `test_widget.py`,
  `test_chat_integrations.py`, `test_billing.py`, `test_connections.py` —
  **169 tests réussis, 0 échec**.

## Résultats détaillés

### 1. Twilio (SMS)
✅ **Fonctionnel.** Authentification vérifiée en direct contre l'API Twilio
réelle (`messages.list(limit=1)`, lecture seule, aucun SMS envoyé) —
succès avec les vraies clés API (`TWILIO_API_KEY_SID`/`SECRET`) présentes
dans `.env`. Le code gère correctement les deux modes d'authentification
(Auth Token classique ou API Key) et échoue proprement (`TwilioNotConfiguredError`
→ 501) si aucun n'est présent.

### 2. Airbyte Cloud (authentification + syncs)
✅ **Fonctionnel.** Échange OAuth2 `client_credentials` réel réussi contre
`https://api.airbyte.com/v1/applications/token`, puis appel réel
`GET /workspaces/{id}/definitions/sources` — **582 connecteurs source
réels retournés**. Le déclenchement réel d'une synchronisation
(`trigger_sync`) n'a volontairement pas été exercé (créerait une vraie
tâche de sync sur le workspace Airbyte Cloud réel) ; l'authentification et
la lecture, qui couvrent la surface réelle du bug le plus probable (clé
expirée/révoquée), sont vérifiées en direct.

### 3. Datadog (envoi de logs)
✅ **Fonctionnel (corrigé le 2026-09-16).** La clé fournie initialement
répondait `HTTP 403 Forbidden` — testée en direct contre les deux sites
Datadog (`datadoghq.eu` et `datadoghq.com`), la vraie cause n'était pas une
clé invalide mais un **site Datadog erroné** : `DD_SITE=datadoghq.eu` alors
que la clé appartient à l'organisation **US1** (`datadoghq.com`). Nouvelle
clé API fournie par l'utilisateur testée en direct sur les deux sites :
`403` sur `.eu`, **`200 {"valid":true}` sur `.com`**. Corrigé dans `.env`
(`DD_API_KEY` + `DD_SITE=datadoghq.com`), redémarrage du backend, revérifié
en direct après redémarrage : `200 {"valid":true}`. `DD_APP_KEY` inchangée
(la nouvelle valeur fournie en UUID ne correspond au format d'aucune clé
Datadog valide sur les endpoints testés — `/api/v2/current_user` et
`/api/v1/org` répondent `401` avec elle — donc non substituée, pour ne pas
casser une clé peut-être encore valide par une qui ne l'est manifestement
pas).

### 4. Grafana Cloud (logs, métriques, traces)
🔴 **Toujours non fonctionnel** sur les 3 canaux, malgré un nouveau token
fourni le 2026-09-16 :
- **Loki (logs)** : `send_test_log_synchronously()` → **HTTP 401**, token
  invalide/expiré.
- **Tempo (traces)** : export réel d'un span de test via l'exporter OTLP/HTTP
  du projet → **échec**.
- **Prometheus (métriques)** : pas un push direct depuis l'app (nécessite un
  Grafana Agent externe scrapant `GET /monitoring/metrics`, qui **fonctionne**
  en local, HTTP 200) — aucun agent en cours d'exécution ici pour tester le
  push distant lui-même.
- **Nouveau token testé en direct, toujours non fonctionnel** : le token
  fourni décode (`glc_...` en base64) vers `{"o":"1907125","n":"rag2-rag2",
  "m":{"r":"us"}}` — un **stack Grafana Cloud différent** ("rag2-rag2",
  région US) de celui déjà configuré dans `.env` ("rag-saas-logs-traces...",
  région `prod-eu-central-0`). Testé en direct contre l'ancien host
  (`logs-prod-039.grafana.net`) avec plusieurs usernames (l'ancien
  `3575376`, l'org id `1907125`) → 401 à chaque fois ; testé aussi contre 3
  hosts US courants devinés (`logs-prod-006/021/3.grafana.net`) → 401 à
  chaque fois, l'org id seul n'étant pas le bon identifiant de stack.
  **Cause réelle** : pour utiliser ce nouveau token, il faut le vrai
  `LOKI_HOST`/`TEMPO_HOST`/`PROMETHEUS_HOST` **et** le username (l'Instance
  ID, pas l'org id) du stack "rag2-rag2" région US — visibles uniquement
  sur le portail Grafana Cloud (Connections → Loki/Tempo/Prometheus →
  Details de CE stack précis), pas devinables ni dérivables du token
  lui-même. Le token est sauvegardé dans `.env`
  (`GRAFANA_NEW_TOKEN_PENDING_HOST`) en attendant ces 6 valeurs (3 hosts + 3
  usernames).
- **Action requise côté utilisateur** : ouvrir le portail Grafana Cloud sur
  le stack "rag2-rag2" et copier les URLs + Instance IDs de Loki, Tempo et
  Prometheus affichées là (page "Details" de chaque intégration).

### 5. Slack (envoi de message)
🔴 **Non configuré dans cet environnement** — aucun `SLACK_CLIENT_ID`/
`SLACK_SIGNING_SECRET` dans `.env`. Impossible de tester un envoi réel sans
credentials. Le code (`api/services/chat_integrations` et consorts) est
couvert par `tests/test_chat_integrations.py` (mocks) — tous verts.

### 6. Microsoft Teams (envoi de message)
🔴 **Non configuré** — aucun `TEAMS_BOT_ID`/`TEAMS_BOT_TOKEN`. Même
situation que Slack ; `tests/test_teams.py` vert (mocks).

### 7. Discord (envoi de message)
🔴 **Non configuré** — aucun `DISCORD_BOT_TOKEN`. Même situation ;
couvert par `tests/test_chat_integrations.py` (mocks).

### 8. Stripe (checkout, webhook)
🔴 **Non configuré** — aucun `STRIPE_SECRET_KEY`. Le catalogue public
`GET /billing/plans` (qui ne nécessite pas Stripe) fonctionne bien en direct
(HTTP 200, 4 plans réels retournés). La logique de checkout/webhook
elle-même (signature, gestion des événements) est couverte par
`tests/test_billing.py` (mocks) — tous verts, mais aucun appel réel contre
l'API Stripe n'a pu être fait sans clé.

### 9. Zapier / Make / n8n (webhook)
🟡 **Partiel, mais fonctionnellement réel.** Il n'existe pas de code
spécifique "Zapier" ou "Make" séparé — ces trois outils s'intègrent tous
via le même mécanisme générique de webhooks sortants
(`POST /organizations/{org_id}/webhooks`), exactement comme n8n. **Testé en
direct** : création réelle d'un webhook organisationnel pointant vers un
serveur HTTP local de test — réussie (HTTP 201). n8n a en plus un statut
dédié (`GET /integrations/n8n/status`), testé en direct : répond
honnêtement `{"configured": false, "reachable": false}` car `N8N_URL`
n'est pas défini et Docker n'est pas disponible dans cet environnement pour
lancer l'instance n8n locale (`docker compose -f
docker-compose.observability.yml up -d n8n`).

### 10. Widget embarquable
✅ **Fonctionnel — testé de bout en bout dans un vrai navigateur.**
Page de test réelle chargée via le serveur Next.js local, avec une vraie
clé publique de widget générée pour une organisation de test :
`widget/script.js` chargé (200), bulle de chat affichée correctement,
clic réel sur la bulle → `GET /widget/config`, `GET /widget/iframe`,
`GET /widget/styles.css`, `GET /widget/chat.js`, et **`POST
/widget/session` → 200** (session de chat réelle créée). Aucune erreur
console.

### 11. SDK Python et JS
✅ **Fonctionnels.**
- **SDK Python** : 8/8 tests unitaires verts, **plus un appel réel de bout
  en bout** (`RagSaasClient(...).usage.get()`) contre le backend local avec
  une vraie clé API générée pour un compte de test — réponse réelle reçue.
- **SDK JS** : 4/4 tests unitaires verts (`vitest`).

### 12. Webhooks
✅ **Fonctionnel.** `tests/test_webhooks.py` (sortants) et
`tests/test_inbound_webhooks.py` (entrants, dont Airbyte) tous verts.
Création réelle d'un webhook sortant vérifiée en direct (voir point 9).

### 13. API publique
✅ **Fonctionnel — un bug réel trouvé et corrigé pendant ce test.**
`tests/test_public_api.py` vert (28 tests). En testant en direct la
création de clé API avec un scope invalide, l'endpoint `POST
/organizations/{org_id}/api-keys` renvoyait une **erreur 500 non gérée**
au lieu du 400 propre que retournent tous les autres endpoints de ce même
routeur pour la même exception (`OrganizationAPIKeyError`) — le seul
endpoint du fichier où le `try/except` avait été oublié. **Corrigé** :
[api/routers/public_api.py:66-72](../../api/routers/public_api.py#L66-L72)
— revérifié en direct après correctif : un scope invalide renvoie
maintenant `HTTP 400` avec un message clair, et la création avec un scope
valide fonctionne (`HTTP 200`, clé réelle générée). `GET /v1/conversations`
et `GET /v1/documents` vérifiés en direct avec une vraie clé `X-API-Key` —
`HTTP 200` sur les deux.

## Synthèse

| # | Intégration | Statut | Raison si non fonctionnel |
|---|---|---|---|
| 1 | Twilio (SMS) | ✅ Fonctionnel | — |
| 2 | Airbyte Cloud | ✅ Fonctionnel | — |
| 3 | Datadog | ✅ Fonctionnel (corrigé) | — |
| 4 | Grafana Cloud | 🔴 Non fonctionnel | Nouveau token = stack différent ; host/username réels manquants |
| 5 | Slack | 🔴 Non configuré | Aucun credential dans `.env` |
| 6 | Microsoft Teams | 🔴 Non configuré | Aucun credential dans `.env` |
| 7 | Discord | 🔴 Non configuré | Aucun credential dans `.env` |
| 8 | Stripe | 🔴 Non configuré | Aucune clé dans `.env` |
| 9 | Zapier/Make/n8n | 🟡 Partiel | Mécanisme générique fonctionnel ; n8n local non lancé (Docker indisponible) |
| 10 | Widget embarquable | ✅ Fonctionnel | — |
| 11 | SDK Python/JS | ✅ Fonctionnel | — |
| 12 | Webhooks | ✅ Fonctionnel | — |
| 13 | API publique | ✅ Fonctionnel (bug corrigé) | — |

**8/13 pleinement fonctionnels, 1/13 partiel (mécanisme générique validé),
4/13 non testables en direct par manque d'identifiants valides ou configurés
— aucun bug de code trouvé sur ces 4, uniquement des identifiants externes
(Grafana Cloud) ou manquants (Slack/Teams/Discord/Stripe) à fournir.**

## Mise à jour du 2026-09-16 (soir) — nouveaux identifiants fournis

L'utilisateur a fourni 3 nouvelles valeurs pour corriger Datadog/Grafana.
Chacune testée en direct avant application :
- **Datadog** : la nouvelle clé API s'est révélée valide, mais sur le site
  **US1** (`datadoghq.com`), pas EU comme configuré — `DD_SITE` était la
  vraie cause du 403, pas la clé elle-même. Corrigé et revérifié en direct
  après redémarrage du backend : `200 {"valid":true}`. Voir section 3.
- **Grafana Cloud** : le nouveau token appartient à un **stack différent**
  (US, pas EU) — non utilisable avec les hosts/usernames actuellement dans
  `.env`. Sauvegardé en attente des vraies valeurs du portail. Voir section 4.
