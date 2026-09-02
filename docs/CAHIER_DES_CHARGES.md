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

### 1.2 Rôles & Permissions — 🟡 QUASI-COMPLET (6/8 ✅, 2/8 🟡)

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

### 1.3 Architecture Multi-tenant — 🟡 DÉMARRÉ (7/10, via les Étapes 1.2.2, 1.2.4, 1.3.3, 1.3.4, 1.3.5, 1.3.6, 1.3.7, 1.3.8, 1.3.9)

| # | Fonctionnalité | Implémentation prévue | Statut |
|---|---|---|---|
| 1.3.1 | Organizations | Table organizations, FK sur toutes les tables métier | ✅ (`api/models/organization.py`, aucune AUTRE table métier n'a encore de FK vers elle -- c'est la prochaine étape logique une fois que du contenu org-scopé existe) |
| 1.3.2 | Workspaces | Table workspaces (FK org), regroupe KB + agents | 🟡 (table `workspaces` créée à l'Étape 1.2.4 avec CRUD complet -- `id`, `organization_id`, `name`, `created_by`, timestamps -- mais délibérément minimale : pas encore de lien vers une KB ou des agents, puisqu'aucun des deux n'existe encore. Le "regroupe KB + agents" de la portée complète reste à faire une fois que ces briques existeront) |
| 1.3.3 | Teams | Table teams (FK org), M2M avec users | ✅ (`api/models/team.py` : `Team` -- FK `organizations` [pas `workspace`, voir note ci-dessous] -- et `TeamMember` [rôle propre `admin`/`member`, scopé à l'équipe]. Migration 0018, `ON DELETE CASCADE` en cascade double : org→teams et teams→team_members. 9 endpoints dans `api/routers/teams.py`. Deux axes de permission combinés dans `api/security/teams.py` : le rôle d'équipe (admin/member) gère QUI est dans l'équipe ; renommer/supprimer l'équipe elle-même reste Manager+ au niveau organisation (jamais délégué au simple admin d'équipe). Un Owner/Admin/Manager de l'org peut toujours accéder à n'importe quelle équipe même sans en être membre (garde-fou anti-verrouillage). Nettoyage ajouté dans `remove_organization_member` : retirer un utilisateur de l'organisation le retire aussi de toutes ses équipes. **Note** : le cahier des charges original disait "FK workspace" pour `teams` ; la spec réellement fournie pour cette étape demandait explicitement "FK → organizations", suivie telle quelle. 19 tests SQLite + 1 test de cascade double contre le vrai Postgres, voir `tests/test_teams.py`) |
| 1.3.4 | Invitations (email+lien) | Table invitations (token, email, rôle, expiry) | ✅ (`api/models/invitation.py`, migration 0020, `ON DELETE CASCADE` depuis `organizations`. Chemin ADDITIF à côté de l'ajout immédiat existant (1.2.3/1.2.4, inchangé) -- celui-ci crée une invitation en attente qu'une adresse email accepte à son rythme, compte existant ou non. Token stocké HASHÉ (`token_hash`, jamais le token brut), `secrets.token_urlsafe(48)` (même générateur que le reset de mot de passe), expire après `INVITATION_EXPIRE_DAYS` (7j). Une seule ligne par (org, email) -- réinviter réémet la même ligne (nouveau token, nouvelle expiration) plutôt que d'échouer sur la contrainte unique. Le garde-fou anti-escalade de 1.2.4 (Manager ne peut inviter qu'en member/viewer) est repris à l'identique pour ce nouveau chemin. Acceptation en deux branches : compte existant → ajouté à l'org SANS connexion automatique (même posture que le reset de mot de passe, qui révoque plutôt qu'il n'auto-connecte) ; compte inexistant → créé avec la même validation que `/auth/register` (breach check, similarité, historique de mots de passe) puis connecté automatiquement, mais SANS l'organisation par défaut auto-créée à l'inscription (rejoint l'organisation invitante à la place). 16 tests SQLite + 1 test de cascade contre le vrai Postgres, voir `tests/test_invitations.py`) |
| 1.3.5 | Isolation des données | org_id obligatoire sur chaque requête + collection Chroma dédiée | 🟡 (isolation réelle et testée depuis 1.2.2-1.3.4 : chaque requête org-scopée filtre explicitement par `organization_id` en Python (`require_org_member` et toute sa famille) -- vérifié par des dizaines de tests d'isolation cross-org tout au long de cette session. **Row Level Security activée sur les 24/24 tables réelles** (vérifié directement contre le vrai Postgres, voir `tests/test_postgres_integration.py`), mais **délibérément non fonctionnelle pour cette appli** : le rôle de connexion (`postgres`) a `BYPASSRLS`, confirmé en interrogeant `pg_roles` -- RLS y est activée depuis la toute première migration (0002) exactement comme défense en profondeur contre une future exposition accidentelle via PostgREST/SDK Supabase, pas comme isolation fonctionnelle pour cette appli. Décision explicite (validée avec l'utilisateur) de NE PAS construire de RLS réellement appliquée -- un rôle Postgres restreint + injection de session par requête + politiques SQL dupliquant la logique Python déjà testée serait un chantier à fort risque pour un gain nul tant qu'aucun accès direct non-fiable à Postgres n'existe. Aucune collection Chroma dédiée par org -- n'existe pas encore, dépend de la Partie 2/3. Voir `docs/AUTH_BACKEND_SETUP.md` pour l'état des lieux complet et le raisonnement) |
| 1.3.6 | Quotas par organisation | Table organization_limits, vérifiées en middleware | ✅ (`api/models/organization_quota.py`, migration 0021, `ON DELETE CASCADE` depuis `organizations`, créée automatiquement avec chaque organisation dans la même transaction que le propriétaire fondateur. 10 dimensions demandées, mais **seules 3 sont réellement appliquées** aujourd'hui : `users`/`workspaces`/`teams`, les seules avec une vraie table à compter -- les 7 autres (documents, stockage, requêtes/jour/mois, appels API, agents, taille KB) n'ont ni table ni endpoint (Parties 2/5/9, inexistantes), donc stockées comme configuration mais non appliquées, `check_quota` renvoyant `True` et `get_quota_usage` renvoyant `None` (pas `0`, qui mentirait sur "rien utilisé"). L'usage des 3 dimensions réelles est un **COMPTAGE EN DIRECT** (`SELECT COUNT(*)`) contre la vraie table, jamais un compteur maintenu séparément -- élimine toute dérive possible, et rend `increment_usage` (4e fonction demandée) un no-op honnête et documenté. Branché sur 3 endpoints réels (`invite`, `create_workspace`, `create_team`) **plus, au-delà de la liste littérale du spec, les deux branches d'acceptation d'invitation (1.3.4)** -- sans quoi `max_users` aurait eu une faille béante via le chemin d'invitation par email construit à l'étape précédente. Erreur `402 Payment Required` (pas 403/429) en cas de dépassement. `GET` (Admin+) / `PATCH` (Owner uniquement, mise à jour partielle, `0` autorisé pour bloquer totalement une ressource). Valeurs par défaut configurables via `.env` (10 réglages `QUOTA_DEFAULT_MAX_*`). 11 tests SQLite + 2 tests contre le vrai Postgres, voir `tests/test_quotas.py`) |
| 1.3.7 | Limites par utilisateur | Colonne daily_request_limit sur organization_members | ✅ (6 colonnes ajoutées à `organization_members` [pas une table séparée], migration 0022 -- `daily_request_limit`/`max_documents`/`max_conversations` (mêmes 3 non-appliqués que 1.3.6, aucune table/endpoint réel derrière) et 3 booléens **délibérément asymétriques** : `can_create_workspaces`/`can_create_teams` (défaut `True`) sont des portes ET RESTRICTIVES par-dessus `require_org_manager` (n'accordent rien à un rôle inférieur, permettent seulement de RETIRER la capacité à un Manager précis) ; `can_invite_members` (défaut `False`) est une porte OU ADDITIVE (accorde la capacité d'inviter à un Member/Viewer précis sans le promouvoir). Choisir la même direction pour les trois aurait cassé des tests déjà livrés dans un sens ou dans l'autre -- démontré et vérifié explicitement. Garde-fou anti-escalade d'invitation élargi de `role == manager` à `role not in (owner, admin)` pour couvrir le nouveau chemin additif. `GET /users/me/limits` renvoie une LISTE (un utilisateur appartient à plusieurs organisations, chacune avec ses propres limites sur cette même ligne d'appartenance). `GET/PATCH /organizations/{id}/members/{user_id}/limits` (Admin+, Owner protégé). 15 tests SQLite + 1 test contre le vrai Postgres, voir `tests/test_user_limits.py`) |
| 1.3.8 | Usage par organisation | Agrégation telemetry filtrée par org_id | ✅ (deux tables -- `api/models/organization_usage.py`, migration 0023, `ON DELETE CASCADE` depuis `organizations` : `organization_usage` [agrégat journalier, une ligne par (org, jour, métrique), contrainte unique] et `organization_usage_details` [un événement par ligne, jamais agrégé, traçabilité -- qui a fait quoi, quand, contexte JSON libre]. **Même honnêteté de périmètre que 1.3.6/1.3.7** : les métriques nommées par le spec (`requetes`, `tokens_input`, `tokens_output`, `documents_processed`, `storage_mb`) appartiennent à `/v1/chat`, `/v1/agents/run` et `POST /documents` -- recherche exhaustive confirmée, zéro référence à ces routes nulle part dans ce code (Partie 9 et 2.2.1, toutes deux à 0%). `record_usage`/`get_usage`/`get_usage_summary` (`api/security/usage.py`) sont génériques -- n'importe quel appelant peut enregistrer n'importe quelle métrique. Branché en réel sur 4 points d'intégration existants : création de workspace (`workspaces_created`), création d'équipe (`teams_created`), invitation directe ET acceptation par email (`members_invited` sur les deux chemins), et **un dépassement de quota (1.3.6) enregistre désormais un événement `quota_exceeded`** -- répond avec du code réel, pas seulement une note de design, à la question de la vision critique sur le lien quotas/usage. Agrégation en temps réel (lecture-puis-écriture sur la ligne du jour à chaque appel, pas de job batch), portable SQLite/Postgres comme le reste du projet (pas d'`ON CONFLICT` propre à un dialecte). Pas de dispatch Celery -- décision explicite, pas un oubli : tous les points d'intégration actuels sont des écritures peu fréquentes déclenchées par un admin, très loin d'un volume justifiant une file d'attente ; la signature de `record_usage` permettrait de le faire plus tard sans toucher un seul appelant. Pas de politique de rétention implémentée -- non demandée par ce spec, recommandation documentée dans `docs/AUTH_BACKEND_SETUP.md` pour quand ce sera nécessaire. 3 endpoints (`GET .../usage`, `GET .../usage/details` paginé, `GET .../usage/export` en CSV/JSON), tous Admin+. `GET .../usage/details` indexée sur `(organization_id, metric, timestamp)` -- seul pattern de lecture utilisé ; l'export lit l'agrégat journalier, jamais le journal détaillé non borné. 14 tests SQLite + 2 tests contre le vrai Postgres, voir `tests/test_usage.py`) |
| 1.3.9 | Configuration par organisation | Table organization_settings (JSON) | ✅ (`api/models/organization_settings.py`, migration 0024, `ON DELETE CASCADE` depuis `organizations`, créée automatiquement avec chaque organisation dans la même transaction que le propriétaire fondateur et les quotas par défaut. Une ligne ne stocke QUE les overrides explicites (`settings` JSON, `{}` au départ) -- jamais une copie complète des 14 valeurs par défaut, qui sont définies une seule fois dans `DEFAULT_SETTINGS` (`api/security/organization_settings.py`) et fusionnées à la lecture (`get_org_settings`). **Contrairement à 1.3.6/1.3.7/1.3.8, les 14 dimensions sont ici toutes réellement stockées ET servies** -- rien à mesurer, une config n'a pas de "pas encore trackable". Ce qui reste non branché : **chaque valeur est vérifiée être encore en dur dans `src/`** (le pipeline RAG, qui n'importe rien de `api/` et n'a aucune notion d'organisation) -- `CHUNK_SIZE_TOKENS=512`/`CHUNK_OVERLAP_TOKENS` (`src/indexing.py`), `EMBEDDING_MODEL_NAME` (dupliqué dans `src/indexing.py` ET `src/retrieval.py`), `CROSS_ENCODER_MODEL_NAME`/`FINAL_TOP_K=5` (`src/retrieval.py`), `MODEL_NAME=claude-sonnet-5` (`src/generation.py`, **différent** du défaut de cette table `claude-3-sonnet-20240229`), `MAX_TOKENS=1024`/`AGENT_MAX_TOKENS=1024` (`src/generation.py`/`src/agent.py`, différents du défaut `4096`), `SYSTEM_PROMPT`/`AGENT_SYSTEM_PROMPT` (prompts FastAPI-spécifiques, rien à voir avec le défaut générique) -- `temperature`/`retrieval_strategy`/`citation_required`/`language` n'ont aucun équivalent dans `src/` du tout. Brancher pour de vrai demanderait de rendre `src/` conscient des organisations pour la première fois -- travail réel des Parties 3/4/9, pas un effet de bord de l'ajout d'une table de config au backend SaaS multi-tenant. Validation réelle sur PATCH (pas des types en façade) : `llm_provider`/`retrieval_strategy` en enums fermés, `temperature` bornée `[0, 2]`, `timezone` vérifiée contre `zoneinfo.available_timezones()`, `language` par regex, et une validation croisée `chunk_overlap < chunk_size` calculée sur la PAIRE EFFECTIVE résultante (pas seulement les champs envoyés, puisqu'un PATCH partiel peut ne toucher qu'un des deux). `GET` (Admin+) / `PATCH` (Owner uniquement, mise à jour partielle). Pas de cache Redis -- aucun appelant à chaud n'existe encore pour justifier un cache. Pas de migration de backfill pour les organisations pré-existantes -- `get_org_settings`/`update_org_settings` dégradent proprement vers les defaults purs (lecture) ou créent la ligne à la volée (écriture) si elle n'existe pas. 20 tests SQLite + 2 tests contre le vrai Postgres, voir `tests/test_organization_settings.py`) |

Reste de la table originale, pour référence :

| # | Fonctionnalité | Implémentation prévue |
|---|---|---|
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

## Total recompté (mis à jour après Étape 1.2.8, 2026-09-02)

Compté précisément item par item sur les Parties 1.1 à 14 (500 items
identifiés) ; la Partie 15 (~15 items pour atteindre les 515 annoncés)
reste de taille inconnue, son texte original n'ayant jamais été retrouvé
au-delà de "15.1.1 Ticke...".

| | Items (/500 connus) | % |
|---|---|---|
| ✅ Fait | 52 | 10.4% |
| 🟡 Partiel | 60 | 12.0% |
| ⬜ Non commencé | 388 | 77.6% |

**Complétion globale (/515, Partie 15 incluse en approximation)** :
- Strictement ✅ : **52/515 (~10.1%)**
- ✅ + 🟡 touchés d'une manière ou d'une autre : **112/515 (~21.7%)**
- Pondéré (✅=1, 🟡=0.5) : **~82/515 (~15.9%)** -- le chiffre le plus représentatif de l'avancement réel.

Mis à jour après Partie 1.3.9 (Configuration par organisation, 2026-09-02) :
Partie 1.3 passe de 6✅/2🟡/2⬜ à 7✅/2🟡/1⬜ sur 10.

Voir le rapport détaillé livré en conversation (état des lieux du
2026-09-02) pour le détail exact par Partie -- tableau récapitulatif,
statut de chaque item des Parties 1.1/1.2/1.3/1.4/2, et résumé par
Partie pour 3 à 15.

---

## Feuille de route — Étapes de travail (mise à jour 2026-09-02)

Principe inchangé : **finir ce qui est partiel avant d'ouvrir un nouveau
chantier**, une Étape = une Partie (ou un regroupement cohérent), jamais
deux en même temps.

### ✅ Étape A — Partie 1.2 (Rôles & Permissions) — TERMINÉE (8/10)

1.2.1 à 1.2.8 tous livrés et vérifiés en CI réelle (Étapes 1.2.1 à
1.2.8, voir le tableau détaillé de la section 1.2 ci-dessus). Ce qui
reste ouvertement non fait dans cette Partie, pour mémoire :
- **1.2.7 (RBAC Casbin)** : moteur réel construit et vérifié contre le
  vrai Postgres, mais PAS branché sur `require_org_manager`/`admin`/`owner`
  -- bloqué sur un problème réel trouvé en testant : la fixture `client`
  de `tests/conftest.py` ne déclenche jamais le `lifespan` de l'app, donc
  brancher Casbin ferait planter (500) la quasi-totalité des tests
  existants. **Prochaine étape concrète si on reprend ce chantier** :
  corriger `tests/conftest.py` pour déclencher réellement le lifespan
  (`asgi-lifespan`'s `LifespanManager`), PUIS basculer
  `require_org_manager`/`admin`/`owner` un par un vers Casbin, chacun
  re-vérifié contre sa propre suite de tests avant de passer au suivant.
- **1.2.8 (permissions granulaires)** : branché en direct sur
  `PATCH/DELETE /workspaces/{id}` uniquement. Pas branché sur
  `organizations.py` (rename/delete, Owner-only) -- décision délibérée
  de risque, pas un oubli. À étendre une fois qu'un vrai besoin business
  le justifie (ex: un Owner veut déléguer la suppression d'organisation
  à un Admin de confiance sans lui donner le rôle Owner).
- Aucun endpoint `documents`/`conversations`/`agents`/`knowledge_base` --
  attendu, ces ressources n'existent pas avant la Partie 2/3/5.

### Prochaines étapes, par ordre de priorité recommandé

1. **Partie 1.3 (Multi-tenant), le reste** -- fondation bloquante pour
   beaucoup d'autres Parties (1.4, 2, 3.3, 9, 12). `organizations`/
   `workspaces`/`teams`/`invitations`/`quotas`/`limites par membre`/
   `usage`/`configuration` existent déjà (1.3.1 ✅, 1.3.2 🟡, 1.3.3 ✅,
   1.3.4 ✅, 1.3.6 ✅, 1.3.7 ✅, 1.3.8 ✅, 1.3.9 ✅), et l'isolation des
   données est réelle et testée au niveau applicatif (1.3.5 🟡 -- RLS
   activée sur toutes les tables mais délibérément non fonctionnelle
   pour cette appli, `postgres` étant BYPASSRLS ; décision explicite de
   ne pas construire de RLS réellement appliquée tant qu'aucun accès
   direct non-fiable à Postgres n'existe). Les quotas (1.3.6), les
   limites par membre (1.3.7) et l'usage (1.3.8) ne couvrent réellement
   que les dimensions avec une vraie table (users/workspaces/teams pour
   les quotas ; can_create_workspaces/can_create_teams/can_invite_members
   pour les limites ; workspaces_created/teams_created/members_invited/
   quota_exceeded pour l'usage), le reste attendant les Parties 2/3/5/8/9.
   La configuration (1.3.9) est, elle, entièrement stockée et servie
   pour les 14 dimensions -- ce qui manque n'est pas le stockage mais la
   consommation : `src/` (le pipeline RAG) reste indépendant de `api/`
   et garde ses propres valeurs en dur, vérifiées une par une (voir
   `docs/AUTH_BACKEND_SETUP.md`). Il ne manque plus que le branding
   (1.3.10, 1 item).
2. **Partie 10 (Sécurité & Governance), le reste** : SSRF protection,
   guardrails IA (PII/toxicity/jailbreak), secret management (Vault),
   request/trace IDs, Sentry -- projet piloté par un audit sécurité, ces
   items ont un poids disproportionné par rapport à leur effort.
3. **Partie 13 (Developer Experience)** : ruff/mypy/pre-commit/
   dependabot/bandit, lint+type-check en CI -- gains rapides et peu
   coûteux, réduisent la dette avant que le projet grossisse encore.
4. **Partie 2 (Knowledge Base multi-format)** -- le cœur produit d'un
   "RAG SaaS platform" ; dépend de 1.3 pour le scoping par organisation/
   workspace. Gros chantier (35 items, plusieurs parsers + jobs Celery),
   à découper en sous-étapes (import, gestion documents, sync).
5. **Partie 6 (Citations & Anti-hallucination), validation réelle** --
   le code existe déjà (`hallucination_detection.py`, `llm_judge.py`),
   juste jamais validé en conditions réelles faute de crédit API
   Anthropic -- rapport effort/valeur excellent dès que le crédit est
   disponible.

### Reste du non-commencé (après les 5 priorités ci-dessus)

- Partie 1.4 (White-label) -- dépend de 1.3.10 (branding par org, seul item restant de 1.3.9/1.3.10)
- Partie 3 (Pipeline RAG), le reste -- chunking avancé, query expansion/HyDE, MMR
- Partie 4 (Multi-LLM) -- abstraction LiteLLM, actuellement un seul provider en dur
- Partie 5.3/5.4 (Agent Builder / Workflow Builder) -- aucune table `agents`, aucune UI
- Partie 7 (Evaluation Lab), le reste -- attention au data-leakage déjà documenté dans AUDIT.md
- Partie 8 (Interface Utilisateur) -- Streamlit actuel n'est PAS le Next.js/React prévu
- Partie 9 (API publique) -- aucun endpoint `/v1/*` au-delà de l'auth
- Partie 11 (Admin Dashboard & Analytics), le reste -- health/ready/metrics existent, le reste non
- Partie 12 (Facturation) -- aucune intégration paiement
- Partie 14 (Documentation), le reste -- guide admin, guide utilisateur, FAQ
- Partie 15 (Human-in-the-loop) -- dès que le contenu complet du cahier des charges original est retrouvé

**On commence par laquelle ?**
