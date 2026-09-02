# Cahier des charges — rag-saas-platform

Ce fichier existe pour ne plus jamais perdre ce document dans un fil de
discussion trop long. Il contient :
1. Le cahier des charges complet tel que récupéré (515 fonctionnalités,
   15 Parties — la Partie 15 est incomplète, coupée dans le message
   original et jamais retrouvée depuis).
2. Le statut réel de chaque Partie (✅ fait / 🟡 partiel / ⬜ non commencé).
3. Une feuille de route en Étapes pour continuer le travail sans tout
   mélanger.

**Note honnête sur la fiabilité de ce document** : le texte brut d'origine
(rédigé directement dans le chat, jamais sauvegardé) n'existe plus nulle
part — il précède tous les logs de session encore présents sur ce PC. Ce
qui suit a été reconstitué à partir (a) du message que tu as recollé dans
la conversation (Parties 1 à 14 complètes, Partie 15 tronquée), et (b) de
l'audit du code réel pour le statut de chaque item. Si tu retrouves la
suite de la Partie 15 (ou d'autres Parties après), on complète ce fichier.

---

## Légende

- ✅ **Fait** — vérifié contre le code réel, testé.
- 🟡 **Partiel** — une base existe mais incomplète, ou écrite mais jamais
  validée en conditions réelles.
- ⬜ **Non commencé** — aucune trace dans le code.

Confiance : **haute** pour tout ce qui est authentification/sécurité
(`api/`, construit et testé dans les sessions récentes) — **moyenne**
pour tout ce qui touche au pipeline RAG (`src/`, `dashboard/`, travail
antérieur non revérifié ligne par ligne dans les sessions récentes).

---

## PARTIE 1 — Structure & Multi-tenant

### 1.1 Authentification — ✅ FAIT (16/14 — au-delà du prévu)

| # | Fonctionnalité | Implémentation prévue | Statut |
|---|---|---|---|
| 1.1.1 | Inscription email+mdp | Route POST /auth/register, hash passlib[bcrypt], table users | ✅ |
| 1.1.2 | Connexion/Déconnexion | POST /auth/login → JWT access token ; logout = suppression cookie/refresh en DB | ✅ |
| 1.1.3 | Reset mot de passe | Token à usage unique en DB (expire 1h), envoi via Resend/SES | ✅ |
| 1.1.4 | Vérification email (OTP) | Code 6 chiffres généré, stocké hashé, TTL 10 min | ✅ |
| 1.1.5 | OAuth Google | Authlib (flow Authorization Code), mapping vers users.oauth_accounts | ✅ |
| 1.1.6 | OAuth GitHub | Même mécanisme Authlib, provider GitHub | ✅ |
| 1.1.7 | 2FA (TOTP) | pyotp, QR code d'enrôlement, vérif à chaque login si activé | ✅ (+ WebAuthn/FIDO2 ajouté en bonus) |
| 1.1.8 | Sessions JWT + refresh | Access token 15 min + refresh token rotatif en DB | ✅ (+ rotation automatique de clé JWT ajoutée en bonus) |
| 1.1.9 | Sessions actives (liste/révocation) | Table sessions avec device/IP/last_seen, endpoint DELETE /sessions/{id} | ✅ |
| 1.1.10 | Suppression de compte | Soft-delete + purge différée (job Celery à J+30) | ✅ |
| 1.1.11 | Export RGPD (JSON) | Endpoint qui agrège toutes les tables liées à user_id | ✅ (+ export CSV ajouté en bonus) |
| 1.1.12 | Consentement RGPD | Champ consent_given_at + version des CGU acceptée | ✅ |
| 1.1.13 | Profil (avatar, nom, entreprise) | Table users + upload avatar vers S3/R2 | ✅ |
| 1.1.14 | Préférences (langue, fuseau) | Colonnes locale, timezone sur users | ✅ |
| 1.1.15 | *(ajouté, hors liste initiale)* Révocation des tokens d'accès | Blacklist des access tokens (jti), nettoyée par tâche planifiée | ✅ |
| 1.1.16 | *(ajouté, hors liste initiale)* Protection CSRF | Double-submit cookie sur /auth/refresh et /auth/logout | ✅ |

Bonus construits au-delà du cahier des charges original (Catégorie 4 de
l'audit sécurité) : WebAuthn/FIDO2, SSO entreprise (OIDC générique),
rotation automatique de clé JWT, rate limiting géo-adaptatif, exemption
IP de confiance. Voir `docs/AUTH_BACKEND_SETUP.md`.

### 1.2 Rôles & Permissions — 🟡 PARTIEL (~3-4/8)

| # | Fonctionnalité | Implémentation prévue | Statut |
|---|---|---|---|
| 1.2.1 | Super Admin | Rôle global hors-org, flag is_superadmin sur users | ✅ (implémenté via l'enum `role` existant plutôt qu'une colonne `is_superadmin` séparée -- migration 0010 avait déjà supprimé ce booléen au profit de l'enum, le réintroduire aurait recréé deux sources de vérité. `require_superadmin()` dans `api/dependencies.py` + `PATCH /admin/users/{id}/role` dans `api/routers/admin_users.py`, protégé contre la démotion du dernier superadmin, journalisé dans l'audit log. 8 tests, voir `tests/test_roles_and_permissions.py`) |
| 1.2.2 | Organization Owner | Rôle le plus élevé dans organization_members.role | ✅ (tables `organizations`/`organization_members` créées -- première tranche de la Partie 1.3. `create_organization_with_owner()` partagé entre `POST /organizations` et l'organisation par défaut auto-créée à l'inscription. `require_org_member/admin/owner()` dans `api/security/organizations.py`. 13 tests SQLite + 1 test de cascade contre le vrai Postgres, voir `tests/test_organizations.py` et `tests/test_postgres_integration.py`) |
| 1.2.3 | Admin | Idem, niveau juste sous Owner | ✅ (`OrganizationRole.admin` + `require_org_admin()`. Endpoints de gestion des membres : `GET/POST/PATCH/DELETE /organizations/{id}/members/...`. Un Admin ne peut ni toucher au rôle d'un Owner ni le retirer -- règle appliquée à TOUT appelant, pas seulement aux Admins, puisqu'aucun flux de transfert de propriété n'existe encore pour réparer une auto-démotion accidentelle. 15 tests, voir `tests/test_organization_members.py`) |
| 1.2.4 | Manager | Idem | ✅ (`require_org_manager()` -- Owner/Admin/Manager, strictement entre Member et Admin. Deux capacités propres : (1) inviter des membres (`GET/POST /organizations/{id}/members[/invite]` élargis d'Admin à Manager+ -- rôle mis à jour et retrait restent Admin-only, inchangés), avec un garde-fou anti-escalade de privilèges ajouté dans `invite_organization_member` : un Manager ne peut inviter qu'en `member`/`viewer`, jamais en `admin`/`manager` (403 sinon) ; (2) gérer des workspaces -- nouvelle table `workspaces` (`api/models/workspace.py`, migration 0015, `ON DELETE CASCADE` depuis `organizations`) et 4 endpoints (`GET/POST /organizations/{id}/workspaces`, `PATCH/DELETE /workspaces/{id}`) dans `api/routers/workspaces.py`, la liste étant ouverte à tout membre (Owner à Viewer) et la création/renommage/suppression réservés à Manager+. 15 nouveaux tests Manager dans `tests/test_organization_members.py` + 15 tests dans `tests/test_workspaces.py` + 1 test de cascade contre le vrai Postgres) |
| 1.2.5 | Member | Idem (rôle par défaut à l'invitation) | ✅ (rôle par défaut confirmé -- `OrganizationMemberInviteRequest.role` défaut déjà `member` depuis 1.2.3, l'org auto-créée à l'inscription attribue Owner à son créateur, pas de flux séparé attribuant Member par défaut ailleurs pour l'instant. `require_org_member_or_higher` ajouté comme alias littéral de `require_org_member`, demandé nommément par le spec de cette étape -- voir `docs/AUTH_BACKEND_SETUP.md` pour la nuance sur son nom. Permissions Member confirmées sur les ressources existantes : lecture organisation/workspaces ✅, gestion membres/workspaces/organisation ❌. **Aucun endpoint `documents`/`conversations` créé** -- décision explicite, ces tables n'existent pas et appartiennent aux Parties 2/3, voir la doc pour la justification complète. 3 nouveaux tests Viewer + 1 test d'isolation cross-org dans `tests/test_workspaces.py`, en plus des tests Member déjà existants depuis 1.2.2-1.2.4) |
| 1.2.6 | Viewer | Idem, lecture seule | ✅ (effet de bord honnête de 1.2.5, pas construit délibérément pour cette étape : Viewer a toujours été rejeté par `require_org_manager`/`require_org_admin`/`require_org_owner` depuis 1.2.2-1.2.4, mais ce n'était pas explicitement testé. `tests/test_viewer_cannot_create_a_workspace`/`_rename_`/`_delete_` le prouvent maintenant explicitement) |
| 1.2.7 | RBAC complet | casbin ou décorateur @require_role() sur chaque route | 🟡 (Casbin installé, migré, initialisé au démarrage réel de l'app, et vérifié en conditions réelles contre le vrai Postgres -- `api/security/rbac.py`, table `casbin_rule` migration 0016, modèle domain-scoped (`dom` = organization_id, pas le modèle plat littéral du spec -- aurait cassé le multi-tenant : un Manager dans une org serait devenu Manager partout). **Décision majeure : `require_org_manager`/`admin`/`owner` restent inchangés**, toujours les tuples codés en dur -- la bascule a été implémentée et vérifiée comme comportementalement identique, puis annulée après avoir découvert (empiriquement, pas supposé) que `tests/conftest.py`'s fixture `client` ne déclenche JAMAIS le `lifespan` de l'app (confirmé par un test dédié), donc `init_rbac()` ne tournerait jamais pendant la suite rapide -- basculer aurait fait planter (500) la quasi-totalité des ~450 tests existants. `@require_permission(resource, action)` ajouté comme dependency additive pour documents/conversations (Parties 2/3, pas encore construits) -- non branché sur aucune route existante. 38 tests contre le vrai Postgres, voir `tests/test_rbac_integration.py` et `docs/AUTH_BACKEND_SETUP.md` pour le plan de transition complet) |
| 1.2.8 | Permissions granulaires par ressource | Table permissions (resource_type, action, role) | 🟡 (table `resource_permissions` réelle, migration 0017, `ON DELETE CASCADE` depuis `organizations` et `users`. Ordre de priorité implémenté et testé : permission granulaire > rôle général > refus. **Branché en direct** sur `PATCH/DELETE /workspaces/{id}` -- un Viewer avec un grant `update` peut renommer CE workspace précis sans changer de rôle, prouvé par test réel (`test_viewer_with_granular_grant_can_update_a_workspace`). **Pas branché sur `organizations.py`** (rename/delete) -- délibéré, action à plus haut risque (toute l'organisation, pas un seul workspace), cohérent avec la position déjà plus stricte que demandé de 1.2.2/1.2.3. **Pas basé sur Casbin** malgré la suggestion du spec -- Casbin (1.2.7) charge ses politiques une fois en mémoire au démarrage, correct pour des rôles statiques, mais faux pour un grant révocable en temps réel (plusieurs processus workers en prod, chacun avec son propre enforcer en mémoire -- une révocation resterait active ailleurs jusqu'au redémarrage). Requête SQL directe et indexée à la place, aucun cache -- fraîcheur de la révocation jugée plus importante que la micro-optimisation. Garde-fous vérifiés par test : un utilisateur ne peut ni s'auto-accorder une permission, ni accorder à un non-membre, ni accorder une action qu'il n'a pas lui-même (un Admin ne peut pas accorder `organization:delete`, réservé à Owner). 18 tests SQLite + 1 test de cascade contre le vrai Postgres, voir `tests/test_resource_permissions.py`) |

**Score 1.2 : 8-9/10** (Owner ✅, Admin ✅, Super Admin ✅, Manager ✅, Member ✅, Viewer ✅, RBAC complet 🟡, permissions granulaires 🟡 -- réelles et branchées en direct sur workspaces, pas encore sur organizations).

### 1.3 Architecture Multi-tenant — 🟡 DÉMARRÉ (2-3/10, via les Étapes 1.2.2 et 1.2.4)

| # | Fonctionnalité | Implémentation prévue | Statut |
|---|---|---|---|
| 1.3.1 | Organizations | Table organizations, FK sur toutes les tables métier | ✅ (`api/models/organization.py`, aucune AUTRE table métier n'a encore de FK vers elle -- c'est la prochaine étape logique une fois que du contenu org-scopé existe) |
| 1.3.2 | Workspaces | Table workspaces (FK org), regroupe KB + agents | 🟡 (table `workspaces` créée à l'Étape 1.2.4 avec CRUD complet -- `id`, `organization_id`, `name`, `created_by`, timestamps -- mais délibérément minimale : pas encore de lien vers une KB ou des agents, puisqu'aucun des deux n'existe encore. Le "regroupe KB + agents" de la portée complète reste à faire une fois que ces briques existeront) |
| 1.3.3-1.3.10 | Teams, Invitations, isolation, quotas, config, branding | — | ⬜ |

Reste de la table originale, pour référence :

| # | Fonctionnalité | Implémentation prévue |
|---|---|---|
| 1.3.1 | Organizations | Table organizations, FK sur toutes les tables métier |
| 1.3.2 | Workspaces | Table workspaces (FK org), regroupe KB + agents |
| 1.3.3 | Teams | Table teams (FK workspace), M2M avec users |
| 1.3.4 | Invitations (email+lien) | Table invitations (token, email, rôle, expiry) |
| 1.3.5 | Isolation des données | org_id obligatoire sur chaque requête + collection Chroma dédiée |
| 1.3.6 | Quotas par organisation | Table organization_limits, vérifiées en middleware |
| 1.3.7 | Limites par utilisateur | Colonne daily_request_limit sur organization_members |
| 1.3.8 | Usage par organisation | Agrégation telemetry filtrée par org_id |
| 1.3.9 | Configuration par organisation | Table organization_settings (JSON) |
| 1.3.10 | Branding par organisation | Table organization_branding |

### 1.4 Domaine & White-label — ⬜ NON COMMENCÉ (0/10)

| # | Fonctionnalité | Implémentation prévue |
|---|---|---|
| 1.4.1 | Custom domains | Table custom_domains, reverse-proxy dynamique (Caddy/Traefik) |
| 1.4.2 | Instructions DNS | Page générée avec les enregistrements CNAME/TXT attendus |
| 1.4.3 | SSL auto (Let's Encrypt) | Traefik + resolver ACME, ou Caddy |
| 1.4.4 | Vérification domaine | Challenge TXT DNS, job Celery de polling |
| 1.4.5 | Custom email domain | Resend/SES avec domaine vérifié (DKIM/SPF) par org |
| 1.4.6 | White-label complet | Flag hide_platform_branding + templates conditionnels |
| 1.4.7 | Logo/favicon/brand name | Champs dans organization_branding |
| 1.4.8 | Couleurs/polices/thème | CSS custom properties depuis organization_branding.theme_json |
| 1.4.9 | Email sender custom | En-tête From: dynamique selon domaine vérifié |
| 1.4.10 | System prompt/persona IA | Colonne organization_settings.system_prompt |

---

## PARTIE 2 — Knowledge Base universelle — ⬜ NON COMMENCÉ (0/35)

### 2.1 Import de documents

| # | Format | Implémentation prévue |
|---|---|---|
| 2.1.1 | PDF | pymupdf (fitz) |
| 2.1.2 | DOCX | python-docx |
| 2.1.3 | TXT | Lecture brute |
| 2.1.4 | Markdown | **Existe déjà** (`src/ingestion.py`) — seul format géré actuellement |
| 2.1.5 | HTML | BeautifulSoup4 + readability-lxml |
| 2.1.6 | CSV | pandas |
| 2.1.7 | JSON | Parsing récursif configurable (JSONPath) |
| 2.1.8 | XML | lxml |
| 2.1.9 | EPUB | ebooklib |
| 2.1.10 | URLs / pages web | httpx + readability-lxml, Playwright si JS nécessaire |
| 2.1.11 | Sitemap | Parse sitemap.xml, fan-out Celery |
| 2.1.12 | GitHub repos | API GitHub + clone shallow |
| 2.1.13 | GitHub issues | API GitHub Search |
| 2.1.14 | Google Drive | Google Drive API |
| 2.1.15 | Google Docs | Google Docs API export → Markdown |
| 2.1.16 | Notion | Notion API (notion-client) |
| 2.1.17 | Confluence | API REST Confluence |
| 2.1.18 | OneDrive | Microsoft Graph API |
| 2.1.19 | Fichiers ZIP | zipfile stdlib, extraction + fan-out |

### 2.2 Gestion des documents

| # | Fonctionnalité | Implémentation prévue |
|---|---|---|
| 2.2.1 | Upload multiple | Endpoint POST /documents multipart |
| 2.2.2 | Drag & drop | react-dropzone |
| 2.2.3 | Barre de progression | Upload chunké + WebSocket/SSE |
| 2.2.4 | Preview | PDF.js / react-doc-viewer |
| 2.2.5 | Extraction metadata | Étendre à auteur/date par format |
| 2.2.6 | Tags/catégories | Table document_tags M2M |
| 2.2.7 | Versioning | Table document_versions |
| 2.2.8 | Suppression/remplacement | Endpoint DELETE, purge chunks Chroma |
| 2.2.9 | Réindexation manuelle | Job Celery scopé à un doc |
| 2.2.10 | Historique modifications | Table document_audit_log |
| 2.2.11 | Statut d'indexation (UI) | Colonne status + polling frontend |
| 2.2.12 | Détection doublons | Hash SHA-256 du contenu |
| 2.2.13 | Détection docs modifiés | Hash comparé à la dernière version |
| 2.2.14 | Sync automatique | Job Celery périodique par source externe |
| 2.2.15 | Réindexation programmée | celery beat cron par organisation |
| 2.2.16 | Batch processing | Celery group()/chord |

---

## PARTIE 3 — Pipeline RAG avancé — 🟡 PARTIEL (~5/41)

### 3.1 Ingestion — ⬜ (0/10, sauf ce qui est listé ailleurs)

Nettoyage/normalisation/extraction texte, titres/sections, metadata :
**existent déjà** pour Markdown uniquement (`src/ingestion.py`).
Extraction tableaux/images, OCR, détection de langue : ⬜.

### 3.2 Chunking

| # | Stratégie | Statut |
|---|---|---|
| 3.2.1 | Fixed-size (512 tokens, overlap 50) | ✅ Existe déjà |
| 3.2.2 | Recursive | ⬜ |
| 3.2.3 | Semantic chunking | ⬜ |
| 3.2.4 | Markdown-aware | ⬜ |
| 3.2.5 | Code-aware (tree-sitter) | ⬜ |
| 3.2.6 | Sentence-based | ⬜ |
| 3.2.7 | Paragraph-based | ⬜ |
| 3.2.8 | Parent-child chunks | ⬜ |

### 3.3 Paramètres configurables — ⬜ (0/7)

Tout est en constantes fixes dans le code (`SEMANTIC_CANDIDATES`,
`FINAL_TOP_K`, etc.), rien n'est configurable par organisation.

### 3.4 Recherche hybride avancée

| # | Fonctionnalité | Statut |
|---|---|---|
| 3.4.1 | BM25 | ✅ Existe déjà |
| 3.4.2 | Vector Search | ✅ Existe déjà |
| 3.4.3 | RRF | ✅ Existe déjà |
| 3.4.4 | Cross-encoder reranking | ✅ Existe déjà |
| 3.4.5-16 | Query expansion, HyDE, multi-query, filtering, compression, MMR, dédup | ⬜ (12 items) |

---

## PARTIE 4 — Multi-LLM & Embeddings — ⬜ NON COMMENCÉ (0/18)

| Section | Statut |
|---|---|
| 4.1 LLM Providers (7 items) | Seul 4.1.1 Anthropic Claude existe (en dur, pas via LiteLLM) |
| 4.2 Embedding Providers (6 items) | Seul Sentence Transformers/MiniLM existe (4.2.4), pas d'abstraction |
| 4.3 Configurabilité (5 items) | ⬜ tout |

---

## PARTIE 5 — Agent IA — 🟡 PARTIEL (base seulement, ~0-14/47 selon granularité)

### 5.1 Architecture Agent

Orchestrateur central, tool selection, tool timeout, retry, tool result
validation, agent memory (court-terme), agent traces : **existent déjà**
côté `src/`/agent (hérité, non revérifié dans les sessions récentes).
Tool permissions, per-tool budget, fallback, parallel tool calls, human
approval, conversation memory cross-session (DB), task planning : ⬜.

### 5.2 Outils intégrés

Search KB, GitHub, Human Escalation : existent déjà. Web Search
(Tavily), Database (SQL), Calculator, URL Reader, Calendar complet,
Email, Custom Tools (webhooks) : ⬜.

### 5.3 Agent Builder — ⬜ NON COMMENCÉ (0/10)
### 5.4 Workflow Builder — ⬜ NON COMMENCÉ (0/13)

Aucune table `agents`, aucune UI (React Flow).

---

## PARTIE 6 — Citations & Anti-hallucination — 🟡 PARTIEL (~4/22)

| Section | Statut |
|---|---|
| 6.1 Citations (10 items) | Citations basiques + source document existent ; page/URL/chunk-id/preview/sources secondaires : ⬜ |
| 6.2 Anti-hallucination (12 items) | Code écrit (`hallucination_detection.py`, `llm_judge.py`) mais **jamais validé en conditions réelles** — bloqué sur crédit API selon `README.md` |

---

## PARTIE 7 — Evaluation Lab — ⬜ NON COMMENCÉ pour l'essentiel (~2/33)

Recall@5 et MRR existent (avec une réserve de data-leakage déjà
documentée dans `AUDIT.md` : le poids du reranker a été réglé sur le
même jeu de test que celui reporté). Dataset manager, Recall@1/3/10,
NDCG, precision, comparaisons multi-modèles, A/B testing : ⬜.

---

## PARTIE 8 — Interface Utilisateur — ⬜ NON COMMENCÉ (0/32)

L'UI actuelle est un dashboard Streamlit mono-utilisateur
(`dashboard/app.py`), pas le Next.js/React prévu. Aucun streaming SSE,
pas de feedback structuré, pas d'historique de conversations en DB, pas
de Voice AI.

---

## PARTIE 9 — API publique & Intégrations — ⬜ NON COMMENCÉ (0/37)

`api/` ne contient QUE l'authentification (Partie 1.1). Aucun endpoint
`/v1/chat`, `/v1/documents`, `/v1/agents/run`. Pas de clés API, pas de
webhooks, pas de SDK généré, pas de widget embarquable, pas
d'intégration Slack/Teams/Discord.

---

## PARTIE 10 — Sécurité & Governance — 🟡 PARTIEL (~10/49)

### 10.1 Sécurité de base

| # | Fonctionnalité | Statut |
|---|---|---|
| 10.1.1 | JWT | ✅ |
| 10.1.2 | Refresh tokens | ✅ |
| 10.1.3 | OAuth | ✅ |
| 10.1.4 | RBAC | 🟡 (voir 1.2.7) |
| 10.1.5 | Rate limiting | ✅ (+ géo-adaptatif, IP de confiance) |
| 10.1.6 | Request validation | ✅ (Pydantic partout) |
| 10.1.7 | Input sanitization | 🟡 |
| 10.1.8 | Prompt injection protection | 🟡 (écrit, pas intégré en filtre live) |
| 10.1.9 | SSRF protection | ⬜ |
| 10.1.10 | File validation | ✅ |
| 10.1.11 | MIME validation | ✅ (vérification magic-bytes) |
| 10.1.12 | Malware scanning (ClamAV) | ⬜ |
| 10.1.13 | Secret management | 🟡 (.env seulement, pas de Vault) |
| 10.1.14 | Encryption at rest | ⬜ (dépend du provider cloud, rien au niveau app) |
| 10.1.15 | Encryption in transit | ✅ (HTTPS, voir guide de déploiement) |

### 10.2 AI Security (Guardrails) — ⬜ (0/10)

Prompt injection/jailbreak/PII/toxicity detection : rien d'intégré en
filtre actif (au-delà de 10.1.8's code non branché).

### 10.3 Audit & Logging

| # | Fonctionnalité | Statut |
|---|---|---|
| 10.3.1 | Audit log (actions admin) | ✅ (log inviolable HMAC, Catégorie 2) |
| 10.3.2 | Structured logging | 🟡 |
| 10.3.3-5 | Request IDs, trace IDs, distributed tracing | ⬜ |
| 10.3.6-8 | LLM/retrieval/tool traces | 🟡 (existent côté RAG, hérité) |
| 10.3.9 | Error tracking (Sentry) | ⬜ |
| 10.3.10-12 | Performance/cost/token monitoring | 🟡 |

### 10.4 Enterprise Features

| # | Fonctionnalité | Statut |
|---|---|---|
| 10.4.1 | SSO | ✅ (OIDC générique, Catégorie 4 item 27) |
| 10.4.2 | SAML | ⬜ (choix documenté : OIDC à la place) |
| 10.4.3-12 | SCIM, rôles enterprise, rétention, déploiement dédié/on-premise/VPC, SLA | ⬜ |

---

## PARTIE 11 — Admin Dashboard & Analytics — 🟡 PARTIEL (~3/34)

| Section | Statut |
|---|---|
| 11.1 Vue Globale (8 items) | ⬜ (pas de données multi-org à agréger) |
| 11.2 Analytics (16 items) | ⬜ (question clusters, knowledge gaps : rien) |
| 11.3 Monitoring (10 items) | GET /health ✅, GET /ready ✅, GET /metrics ✅ (Prometheus, vrai multiprocess) ; Flower, Grafana/alerting, health check vecteurs : ⬜ |

---

## PARTIE 12 — Facturation & Monétisation — ⬜ NON COMMENCÉ (0/23)

Aucune intégration Paystack, aucune table plans/subscriptions/credits.

---

## PARTIE 13 — Developer Experience — 🟡 PARTIEL (~10/52)

| Section | Statut |
|---|---|
| 13.1 Qualité du code (9 items) | ⬜ (pas de ruff/mypy/pre-commit/dependabot/bandit configurés) |
| 13.2 Tests (11 items) | 🟡 (383 tests auth réels en CI + 105 tests RAG hérités — substantiel, mais pas de tests E2E Playwright faute de frontend) |
| 13.3 CI/CD (8 items) | 🟡 (GitHub Actions réel : tests + Snyk + ZAP + build Docker ; pas de lint/type-check en CI, pas de déploiement automatique) |
| 13.4 Déploiement (12 items) | ⬜ (Docker existe et testé en CI ; Terraform/K8s/Helm/multi-cloud : rien) |
| 13.5 Observabilité (12 items) | Couvert par 10.3 |

---

## PARTIE 14 — Documentation & Livrables — 🟡 PARTIEL (~5/33)

| Section | Statut |
|---|---|
| 14.1 Documentation technique (12 items) | README ✅, architecture avec diagrammes Mermaid ✅ (Catégorie 5), guide de déploiement ✅ (Catégorie 5), doc API (Swagger + exemples curl) ✅ — guide admin/utilisateur/white-label/FAQ : ⬜ |
| 14.2 Documentation commerciale (8 items) | ⬜ |
| 14.3 Landing page (9 items) | ⬜ |
| 14.4 Branding (4 items) | ⬜ (nom/logo/palette jamais tranchés) |

---

## PARTIE 15 — Human-in-the-loop — ⚠️ INCOMPLET DANS CE DOCUMENT

Le message original s'arrête à "15.1.1 Ticke..." — la suite n'a jamais
été retrouvée. Ce qu'on sait : l'outil "Human Escalation" existe déjà
côté agent (voir 5.2.9). **À compléter si tu retrouves la suite.**

---

## Total recompté

| | Items | Confiance |
|---|---|---|
| ✅ Fait | ~29 | Haute (vérifié ce fil-ci) |
| 🟡 Partiel | ~35-40 | Moyenne (RAG hérité non revérifié) |
| ⬜ Non commencé | ~450 | Haute |
| **Total** | **~515** (Partie 15 incomplète) | |

---

## Feuille de route — Étapes de travail

Principe : **finir ce qui est partiel avant d'ouvrir un nouveau chantier**,
une Étape = une Partie (ou un regroupement cohérent), jamais deux en même
temps.

### Étapes sur le PARTIEL (à faire en premier, tel que demandé)

- **Étape A — Partie 1.2 (Rôles & Permissions)** : RBAC granulaire réel.
  ⚠️ Dépendance à trancher avant de commencer : 1.2.2-1.2.6 (rôles par
  organisation) ne peuvent pas être complétés sans que la Partie 1.3
  (Multi-tenant) existe. Deux options : (a) faire un RBAC générique sans
  organisation pour l'instant, (b) basculer sur la Partie 1.3 d'abord.
  À décider ensemble avant de lancer cette étape.
- **Étape B — Partie 10 (Sécurité & Governance), le reste** : SSRF
  protection, guardrails IA (PII/toxicity), secret management (Vault),
  request/trace IDs, Sentry.
- **Étape C — Partie 11.3 (Monitoring), le reste** : health check
  vecteurs, Flower, alerting Grafana.
- **Étape D — Partie 13 (Developer Experience)** : ruff/mypy/pre-commit/
  dependabot/bandit, lint+type-check en CI.
- **Étape E — Partie 14 (Documentation), le reste** : guide admin, guide
  utilisateur, FAQ.
- **Étape F — Partie 3 (Pipeline RAG), le reste** : chunking avancé,
  query expansion/HyDE, MMR, paramètres configurables.
- **Étape G — Partie 6 (Citations & Anti-hallucination)** : validation
  réelle du code déjà écrit (nécessite du crédit API Anthropic).

### Étapes sur le NON-COMMENCÉ (après le partiel)

- **Étape H — Partie 1.3 (Multi-tenant)** — fondation pour beaucoup
  d'autres parties (1.2, 1.4, 3.3, 9, 12).
- **Étape I — Partie 1.4 (White-label)**
- **Étape J — Partie 2 (Knowledge Base multi-format)**
- **Étape K — Partie 4 (Multi-LLM)**
- **Étape L — Partie 5.3/5.4 (Agent Builder / Workflow Builder)**
- **Étape M — Partie 7 (Evaluation Lab)**
- **Étape N — Partie 8 (Interface Utilisateur)**
- **Étape O — Partie 9 (API publique)**
- **Étape P — Partie 12 (Facturation)**
- **Étape Q — Partie 15 (Human-in-the-loop)** — dès que le contenu complet est retrouvé.

**On commence par laquelle ?**
