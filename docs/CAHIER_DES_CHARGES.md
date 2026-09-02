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

### 1.3 Architecture Multi-tenant — 🟡 DÉMARRÉ (8/10, via les Étapes 1.2.2, 1.2.4, 1.3.3, 1.3.4, 1.3.5, 1.3.6, 1.3.7, 1.3.8, 1.3.9, 1.3.10 -- les 10 items sont désormais tous touchés, 8✅/2🟡/0⬜)

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
| 1.3.10 | Branding par organisation | Table organization_branding | ✅ (`api/models/organization_branding.py`, migration 0025, `ON DELETE CASCADE` depuis `organizations`, créée automatiquement avec la même transaction que le quota et la configuration par défaut. **Contrairement à 1.3.9, table de colonnes typées avec vraies valeurs par défaut sur la ligne elle-même** (même forme que `OrganizationQuota`, pas un blob JSON) -- 8 champs fixes, pas un ensemble ouvert. **`GET` est délibérément PUBLIC** -- la seule exception dans tout ce code à la règle "toute route `/organizations/{org_id}/...` exige au moins `require_org_member`" : le branding existe pour être affiché à un VISITEUR avant même qu'il soit authentifié (écran de connexion, widget embarqué) ; seul un `organization_id` réellement inexistant renvoie 404, le 404 anti-énumération des autres routes ne s'applique pas ici par conception. `PATCH` et les 4 endpoints d'upload/suppression restent Owner uniquement. **Sécurité upload réelle** (`api/services/storage.py`) : taille (2MB logo/512KB favicon), format réel par octets magiques (jamais le Content-Type déclaré, comme les avatars), ET un vrai décodage Pillow + vérification des dimensions en pixels (2000×2000/512×512) -- `Pillow` passe de dépendance transitive (`qrcode[pil]`) à directe. **Stockage** : réutilise le MÊME bucket S3 que les avatars sous un préfixe `branding/{org_id}/` -- aucun second bucket, aucun nouveau réglage `S3_*`, aucun changement CI ; clé aléatoire à chaque upload, ancien objet explicitement supprimé du stockage au remplacement ou à la suppression (jamais orphelin). **`custom_css` -- mitigation réelle et testée** contre l'injection CSS (`expression()`, `-moz-binding`, `behavior:`, `@import`, `<script`) puisque c'est du contenu contrôlé par l'Owner mais servi à tout visiteur anonyme de la page publique de l'organisation. Pas de cache Redis -- même raisonnement que 1.3.9. **Intégration frontend : n'existe pas à intégrer** -- aucun projet Next.js/React nulle part dans ce dépôt (vérifié : zéro `package.json`, zéro fichier `.tsx`/`.jsx`), seule UI existante `dashboard/app.py` (Streamlit mono-utilisateur, sans rapport avec les organisations, Partie 8 à 0%) ; l'API construite ici (`GET .../branding` public) est précisément ce qu'un futur frontend consommerait, pas quelque chose à brancher dans du code qui n'existe pas. 22 tests SQLite (permissions/branchement) + 10 tests SQLite (validation réelle, `tests/test_storage.py`) + 2 tests contre le vrai Postgres (cascade + defaults) + 6 tests contre le vrai S3/MinIO (upload/remplacement/suppression bout-en-bout), voir `tests/test_organization_branding.py` et `tests/test_branding_storage_integration.py`) |

### 1.4 Domaine & White-label — 🟡 DÉMARRÉ (5✅/4🟡/1⬜ sur 10, via les Étapes 1.4.1/1.4.2/1.4.3/1.4.4/1.4.5 + réutilisation honnête de 1.3.9/1.3.10)

| # | Fonctionnalité | Implémentation prévue | Statut |
|---|---|---|---|
| 1.4.1 | Custom domains | Table custom_domains, reverse-proxy dynamique (Caddy/Traefik) | ✅ (`api/models/custom_domain.py`, migration 0026, `ON DELETE CASCADE` depuis `organizations`, `UNIQUE(domain)` global -- deux organisations ne peuvent jamais revendiquer le même hostname. **Honnêteté de périmètre vérifiée avant d'écrire une ligne de code** : ce déploiement n'a AUCUN reverse-proxy routant par Host header (`render.yaml` déploie un unique conteneur Streamlit, `docker-compose.yml` est local-only, zéro config Traefik/Caddy nulle part dans ce dépôt) -- un domaine passant à `active` ne fait donc PAS réellement servir l'application sur `app.ma-boite.com`, ça demande une vraie infrastructure (1.4.3, non construite). Ce qui EST réel : un vrai enregistrement d'intention en base, un token de vérification vraiment aléatoire (`secrets.token_urlsafe(32)`, même générateur que reset de mot de passe/invitations), et une vraie recherche DNS TXT asynchrone (`dns.asyncresolver`, `dnspython` passé de dépendance transitive à directe) qui prouve le contrôle de la zone DNS avant toute vérification. Sous-domaine dédié `_rag-saas-verify.<domaine>` pour le challenge TXT (jamais le domaine nu, pour ne jamais entrer en collision avec des enregistrements SPF/DKIM existants). Une vérification échouée renvoie `200` avec `status="failed"`, jamais une erreur -- "DNS pas encore propagé" est le cas normal attendu, pas une exception ; l'Owner peut redemander la vérification autant de fois que nécessaire. `GET .../verify/{token}` délibérément public (le token est la preuve d'autorisation), recherché par (org_id, token) ensemble pour empêcher un token erroné de servir de sonde DNS arbitraire. `ssl_cert`/`ssl_key` sont des colonnes prévues pour 1.4.3, non utilisées ici -- documentées explicitement comme un risque si jamais remplies sans passer par `api/security/secret_encryption.py`. 26 tests SQLite (DNS mocké) + 4 tests contre le vrai DNS public (`tests/test_dns_verification_integration.py`, jamais de contenu externe précis vérifié, seulement le mécanisme) + 1 test contre le vrai Postgres, voir `tests/test_custom_domains.py`) |
| 1.4.2 | Instructions DNS | Page générée avec les enregistrements CNAME/TXT attendus | ✅ (chaque `DnsRecordEntry` porte désormais un champ `instructions` bilingue (`{"fr":..., "en":...}`), et chaque réponse de domaine porte un `setup_steps` -- une marche à suivre ordonnée, elle aussi bilingue, pensée pour un non-technicien (se connecter chez son fournisseur DNS, trouver la bonne section, ajouter les enregistrements, patienter, vérifier). Rien n'est stocké, tout recalculé à la volée (`api/security/custom_domains.py`'s `dns_records_for`/`setup_steps`). **Le texte des instructions décrit uniquement l'action DNS elle-même** ("ce CNAME relie votre domaine à notre plateforme", jamais "votre site est en ligne") -- cohérent avec l'absence réelle de reverse-proxy documentée en 1.4.1, pas de promesse de routage fonctionnel qui serait fausse. Seul reste un artefact frontend au sens littéral du spec original ("page générée") -- Partie 8 à 0%, même limite que 1.3.10 ; l'API elle-même est ce qu'un futur frontend consommerait. 3 tests dédiés (présence pour un domaine existant, valeurs correctes injectées dans le texte, présence ET différence réelle du FR et de l'EN -- pas une simple copie d'une langue vers l'autre), voir `tests/test_custom_domains.py`) |
| 1.4.3 | SSL auto (Let's Encrypt) | Traefik + resolver ACME, ou Caddy | 🟡 (`api/models/acme_account.py` + `api/models/ssl_certificate.py`, migration 0027 -- un vrai client ACME v2/RFC 8555 (`acme`/`josepy`, les mêmes bibliothèques que certbot), pas une réimplémentation du protocole. **Verdict 🟡 et non ✅, précisément parce que** le mot "auto" du titre de cet item n'est pas atteint : DNS-01 (le seul challenge que ce déploiement puisse supporter du tout, aucun reverse-proxy pour HTTP-01, voir 1.4.1) exige qu'un humain publie un enregistrement TXT à chaque émission ET à chaque renouvellement, puisqu'aucune intégration API fournisseur DNS n'existe pour le faire à sa place. Tout ce que cette application contrôle elle-même est en revanche réel et vérifié contre le vrai serveur de staging Let's Encrypt : inscription de compte, création de commande, calcul du challenge DNS-01, complétion réelle, et surtout **l'échec de validation sans jamais publier le vrai enregistrement DNS est confirmé produire une vraie erreur `ValidationError` du serveur réel**, exactement ce que le code gère. Flux réel en deux phases (premier appel : ouvre une commande, calcule le challenge, ne répond JAMAIS au challenge avant que le TXT soit publié -- y répondre trop tôt invaliderait le challenge définitivement ; second appel : répond, sonde brièvement, finalise si valide). Clé privée du certificat ET clé de compte ACME chiffrées via `api/security/secret_encryption.py` (même module que JWTSigningKey/EnterpriseSSOConnection) -- jamais retournées par aucune réponse API, à aucun rôle. Révocation ACME réelle possible sans challenge (preuve par le compte ou la clé du certificat, RFC 8555 §7.6). 2 tâches Celery périodiques réelles (`check_ssl_renewals`/`check_ssl_expirations`, item 5) -- pont vers le code asynchrone via `asyncio.run()`, un écart délibéré et documenté par rapport aux autres tâches Celery de ce projet (toutes synchrones), puisque dupliquer cette logique ACME réelle en synchrone serait une duplication substantielle et risquée pour aucun bénéfice réel. `ACME_DIRECTORY_URL` par défaut sur le staging Let's Encrypt, jamais la production. 20 tests SQLite (ACME mocké) + 4 tests contre le vrai staging Let's Encrypt (`tests/test_acme_integration.py`) + 5 tests contre le vrai Postgres pour les tâches Celery (`tests/test_ssl_certificate_renewal_integration.py`) + 1 test de cascade à deux niveaux (organisation → domaine → certificat) contre le vrai Postgres, voir `tests/test_ssl_certificates.py`) |
| 1.4.4 | Vérification domaine | Challenge TXT DNS, job Celery de polling | ✅ (le challenge TXT DNS lui-même était déjà réel depuis 1.4.1 ; cette étape ajoute le job Celery de polling qui manquait -- deux nouvelles colonnes sur `custom_domains` (migration 0028) : `verification_attempts`/`last_verification_attempt_at`, pas de nouvelle table. **Trois chemins de vérification délibérément séparés, pas unifiés** : le lien public à token (1.4.1) et le nouvel endpoint manuel Owner-authentifié vérifient immédiatement et échouent dès le premier échec DNS, exactement le comportement déjà livré et testé par 1.4.1 -- les unifier aurait changé ce comportement existant (régression). Seuls les chemins réellement automatiques (`poll_domain_verification`/`check_all_pending_domains`, tâche Celery Beat toutes les `DOMAIN_VERIFICATION_INTERVAL_SECONDS`, 5 min par défaut) comptent les tentatives et appliquent l'échec après épuisement -- deux limites indépendantes, `DOMAIN_VERIFICATION_MAX_ATTEMPTS` (12) ET `DOMAIN_VERIFICATION_TIMEOUT_MINUTES` (60), l'une ou l'autre suffit, ce qui protège un domaine même si le sweep périodique tourne moins souvent que prévu (panne worker, tick de beat manqué). **Scalabilité "milliers de domaines"** : les recherches DNS de `check_all_pending_domains` tournent en CONCURRENT (bornées par un sémaphore à 50), les écritures en base restent séquentielles (une seule `AsyncSession` n'est pas sûre en accès concurrent) -- une boucle purement séquentielle aurait pu faire durer un seul sweep plus longtemps que l'intervalle lui-même. Un check-and-schedule best-effort (`schedule_domain_verification`, enveloppé dans un `try/except` large) donne à un domaine tout juste créé une longueur d'avance sur le prochain sweep, sans jamais faire échouer la création elle-même si le broker est injoignable. 2 endpoints Owner (`POST .../verify` manuel, `GET .../status` avec `timeout_at` calculé à la volée). Tests SQLite (DNS mocké) pour toute la logique + tests contre le vrai Postgres pour les deux vraies tâches Celery, voir `tests/test_domain_verification.py`/`tests/test_domain_verification_integration.py`) |
| 1.4.5 | Custom email domain | Resend/SES avec domaine vérifié (DKIM/SPF) par org | 🟡 (neuf nouvelles colonnes sur `custom_domains`, migration 0029 -- pas de nouvelle table. **Vérifié contre la vraie documentation API de Resend avant d'écrire une ligne de code** : Resend génère et gère LUI-MÊME sa clé DKIM côté serveur pour chaque domaine, sous un sélecteur FIXE (`"resend"`) -- son API Domains réelle n'a aucun champ pour accepter une clé ou un sélecteur DKIM fourni par l'appelant. Ça crée un écart honnête, documenté explicitement (`api/security/email_domains.py`) : `generate_dkim_keys`/`get_dkim_dns_records`/`verify_dkim` (les noms de fonctions littéraux du spec) sont une infrastructure RÉELLE et testée (vraie paire RSA-2048, vraie vérification DNS de publication) mais ne signent PAS réellement le courrier sortant -- tout email de cette app passe par l'appel Resend `api/services/email.py`, qui signe DKIM avec SA PROPRE clé. Ce qui compte réellement pour la délivrabilité est l'intégration Resend elle-même (`api/services/resend_domains.py`, httpx brut, même convention "pas de SDK" que `api/services/email.py`) : `create_resend_domain`/`get_resend_domain`/`trigger_resend_domain_verification`/`delete_resend_domain`, exposés ensemble avec les 2 enregistrements maison via `GET .../email/dns`. **Verdict 🟡 et non ✅, découverte réelle en testant, pas hypothétique** : la vraie `RESEND_API_KEY` de ce projet (déjà utilisée pour de vrais envois) est restreinte à l'envoi seul -- l'API Domains de Resend la rejette avec une vraie erreur `401 restricted_api_key`. Le code détecte et remonte ça correctement (jamais avalé ni maquillé), et se dégrade proprement (`resend_domain_id` reste vide, retenté au prochain appel), mais la création/vérification réelle d'un domaine chez Resend n'a pas pu être prouvée de bout en bout dans cet environnement sans une clé à accès complet. Vérification de propriété réelle et asynchrone via un TXT dédié `_rag-verify.<domaine>` (piste séparée de celle de 1.4.1), avec timeout indépendant (`EMAIL_DOMAIN_VERIFICATION_TIMEOUT_HOURS`, 24h par défaut). Clé privée DKIM chiffrée via `api/security/secret_encryption.py`, jamais retournée par aucune réponse API. Envoi réel testé honnêtement : `send_via_custom_email_domain` (nouveau, dans `api/services/email.py`) envoie pour de vrai via Resend avec un `from:` personnalisé, et le test d'intégration prouve le VRAI rejet par Resend tant que son propre objet domaine n'est pas vérifié -- pas un faux succès maquillé. 3 endpoints Owner (`POST .../email/verify`, `GET .../email/status`, `GET .../email/dns`). 34 tests SQLite (DNS + Resend mockés) + 8 tests contre le vrai DNS public, la vraie API Resend, et le vrai Postgres, voir `tests/test_email_domains.py`/`tests/test_email_domains_integration.py`) |
| 1.4.6 | White-label complet | Flag hide_platform_branding + templates conditionnels | ⬜ |
| 1.4.7 | Logo/favicon/brand name | Champs dans organization_branding | ✅ (déjà livré par 1.3.10 -- `organization_branding.logo_url`/`favicon_url`/`brand_name` sont exactement ces champs ; aucun travail supplémentaire nécessaire) |
| 1.4.8 | Couleurs/polices/thème | CSS custom properties depuis organization_branding.theme_json | 🟡 (couleurs et police déjà livrés par 1.3.10 -- mais comme des colonnes typées et validées individuellement, pas un blob `theme_json` générique comme le spec original l'envisageait ; `custom_css` couvre l'extension libre. Aucune page pour injecter ces variables CSS -- même limite que 1.3.10, Partie 8 à 0%) |
| 1.4.9 | Email sender custom | En-tête From: dynamique selon domaine vérifié | 🟡 (partiellement satisfait par 1.4.5 -- `send_via_custom_email_domain` fait exactement ça, un en-tête `From:` dynamique selon le domaine vérifié, réel et testé contre la vraie API Resend. Ce qui manque : rien dans ce dépôt n'appelle encore cette fonction pour les emails réels de l'application -- les ~30 fonctions `send_*_email` d'`api/services/email.py` (reset mot de passe, invitations, etc.) utilisent toujours `EMAIL_FROM_ADDRESS` sans exception ; câbler un choix d'expéditeur par organisation dans ces flux existants est un chantier séparé, non demandé par la liste d'actions littérale de 1.4.5) |
| 1.4.10 | System prompt/persona IA | Colonne organization_settings.system_prompt | ✅ (déjà livré par 1.3.9 -- `system_prompt` fait partie des 14 réglages de `DEFAULT_SETTINGS`, lisible/modifiable via `GET`/`PATCH /organizations/{id}/settings` ; même réserve que 1.3.9 : rien dans `src/` ne le consomme encore, `AGENT_SYSTEM_PROMPT`/`SYSTEM_PROMPT` y restent en dur) |

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
| ✅ Fait | 58 | 11.6% |
| 🟡 Partiel | 64 | 12.8% |
| ⬜ Non commencé | 378 | 75.6% |

**Complétion globale (/515, Partie 15 incluse en approximation)** :
- Strictement ✅ : **58/515 (~11.3%)**
- ✅ + 🟡 touchés d'une manière ou d'une autre : **122/515 (~23.7%)**
- Pondéré (✅=1, 🟡=0.5) : **~90.0/515 (~17.5%)** -- le chiffre le plus représentatif de l'avancement réel.

Mis à jour après Partie 1.4.5 (Custom email domain, 2026-09-03) :
Partie 1.4 : 5✅/3🟡/2⬜ → 5✅/4🟡/1⬜ sur 10 (1.4.5 passe de ⬜ à 🟡 --
DKIM auto-généré réel + intégration Resend réelle, mais restée 🟡 car
la clé Resend de cet environnement s'est révélée, en testant pour de
vrai, restreinte à l'envoi seul -- la création/vérification de domaine
côté Resend n'a pas pu être prouvée de bout en bout sans une clé à
accès complet. 1.4.9 corrigé de ⬜ à 🟡 en même temps : la fonction
qu'il demande existe désormais et fonctionne réellement, mais n'est
câblée dans aucun des ~30 envois existants de l'application).

Précédemment, après Partie 1.4.4 (Vérification domaine périodique, 2026-09-02) :
Partie 1.4 : 4✅/3🟡/3⬜ → 5✅/3🟡/2⬜ sur 10 (1.4.4 passe de 🟡 à ✅ --
le job Celery de polling périodique qui manquait est désormais réel et
testé contre le vrai Postgres ; voir le tableau détaillé ci-dessus pour
la conception à trois chemins de vérification séparés et les deux
limites d'épuisement indépendantes).

Précédemment, après Partie 1.4.3 (SSL auto Let's Encrypt, 2026-09-02) :
Partie 1.4 : 4✅/2🟡/4⬜ → 4✅/3🟡/3⬜ sur 10 (1.4.3 reste 🟡, jamais ✅
-- le protocole ACME est réel et vérifié contre le vrai staging Let's
Encrypt, mais le mot "auto" du titre n'est pas atteint : DNS-01 exige
une action manuelle de l'Owner à chaque émission ET à chaque
renouvellement, faute d'intégration API fournisseur DNS).

Précédemment, après Partie 1.4.2 (Instructions DNS, 2026-09-02) :
Partie 1.4 : 3✅/3🟡/4⬜ → 4✅/2🟡/4⬜ sur 10 (1.4.2 passe de 🟡 à ✅ --
instructions bilingues réellement testées, seul l'artefact "page"
littéral du spec original reste hors de portée, Partie 8 à 0%).

Précédemment, après Partie 1.4.1 (Custom domains) :
Partie 1.4 démarre : 0✅/0🟡/10⬜ → 3✅/3🟡/4⬜ sur 10. Les items
supplémentaires en ✅ (1.4.7, 1.4.10) et en 🟡 (1.4.4, 1.4.8) ne
sont PAS du travail livré à cette étape -- ce sont des items du cahier
original déjà satisfaits, en totalité ou en partie, par 1.3.9
(system_prompt) et 1.3.10 (logo/favicon/brand_name, couleurs/police),
corrigés ici pour que le tableau reflète la réalité du code plutôt que
de compter deux fois le même travail sous deux numéros différents.

Précédemment, après Partie 1.3.10 (Branding par organisation) :
Partie 1.3 passe de 7✅/2🟡/1⬜ à 8✅/2🟡/0⬜ sur 10 -- **les 10 items de la Partie 1.3 sont désormais tous touchés** (aucun ⬜ restant ; 1.3.2 Workspaces et 1.3.5 Isolation des données restent 🟡, volontairement incomplets par rapport à la portée complète du spec, voir leurs lignes ci-dessus pour le détail exact de ce qui manque).

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

### ✅ Étape B — Partie 1.3 (Multi-tenant) — TERMINÉE au sens "tous les items touchés" (8✅/2🟡/0⬜ sur 10)

1.3.1, 1.3.3, 1.3.4, 1.3.6, 1.3.7, 1.3.8, 1.3.9, 1.3.10 tous livrés et
vérifiés en CI réelle. Ce qui reste ouvertement partiel dans cette
Partie, pour mémoire :
- **1.3.2 (Workspaces)** : CRUD complet mais délibérément minimal --
  pas encore de lien vers une KB ou des agents, puisqu'aucun des deux
  n'existe encore (Parties 2/5).
- **1.3.5 (Isolation des données)** : isolation applicative réelle et
  testée, mais RLS activée sur toutes les tables reste délibérément non
  fonctionnelle (`postgres` a `BYPASSRLS`) -- décision explicite de ne
  pas construire de RLS réellement appliquée tant qu'aucun accès direct
  non-fiable à Postgres n'existe.
- Les quotas (1.3.6), les limites par membre (1.3.7) et l'usage (1.3.8)
  ne couvrent réellement que les dimensions avec une vraie table
  (users/workspaces/teams pour les quotas ; can_create_workspaces/
  can_create_teams/can_invite_members pour les limites ;
  workspaces_created/teams_created/members_invited/quota_exceeded pour
  l'usage), le reste attendant les Parties 2/3/5/8/9.
- La configuration (1.3.9) et le branding (1.3.10) sont, eux,
  entièrement stockés et servis pour toutes leurs dimensions -- ce qui
  manque n'est pas le stockage mais la consommation : `src/` (le
  pipeline RAG) et le frontend (inexistant, Partie 8 à 0%) restent tous
  les deux indépendants de `api/` (voir `docs/AUTH_BACKEND_SETUP.md`).

### Prochaines étapes, par ordre de priorité recommandé

1. **Partie 10 (Sécurité & Governance), le reste** : SSRF protection,
   guardrails IA (PII/toxicity/jailbreak), secret management (Vault),
   request/trace IDs, Sentry -- projet piloté par un audit sécurité, ces
   items ont un poids disproportionné par rapport à leur effort.
2. **Partie 13 (Developer Experience)** : ruff/mypy/pre-commit/
   dependabot/bandit, lint+type-check en CI -- gains rapides et peu
   coûteux, réduisent la dette avant que le projet grossisse encore.
3. **Partie 2 (Knowledge Base multi-format)** -- le cœur produit d'un
   "RAG SaaS platform" ; dépend de 1.3 (désormais tous les items
   touchés) pour le scoping par organisation/workspace. Gros chantier
   (35 items, plusieurs parsers + jobs Celery), à découper en
   sous-étapes (import, gestion documents, sync).
4. **Partie 6 (Citations & Anti-hallucination), validation réelle** --
   le code existe déjà (`hallucination_detection.py`, `llm_judge.py`),
   juste jamais validé en conditions réelles faute de crédit API
   Anthropic -- rapport effort/valeur excellent dès que le crédit est
   disponible.

### Reste du non-commencé (après les priorités ci-dessus)

- Partie 1.4 (White-label), le reste -- démarrée (5✅/4🟡/1⬜ sur 10,
  voir le tableau détaillé ci-dessus) : 1.4.1 (custom domains), 1.4.2
  (instructions DNS bilingues), 1.4.3 (SSL via un vrai client ACME,
  🟡 -- DNS-01 fonctionnel et vérifié contre le vrai staging Let's
  Encrypt, mais pas "auto" sans intégration API fournisseur DNS), 1.4.4
  (vérification domaine périodique, job Celery de polling réel) et
  1.4.5 (custom email domain, 🟡 -- DKIM auto-généré réel + intégration
  Resend réelle, mais la clé Resend de cet environnement s'est révélée
  restreinte à l'envoi seul en testant pour de vrai, empêchant de
  prouver la création/vérification de domaine chez Resend de bout en
  bout) livrés ; 1.4.7/1.4.8/1.4.10 déjà satisfaits en tout ou partie
  par 1.3.9/1.3.10, et 1.4.9 partiellement par 1.4.5 (la fonction existe
  et fonctionne réellement, mais n'est câblée dans aucun envoi
  existant). Ce qui manque reste réel infrastructure (un reverse-proxy
  dynamique routant réellement le trafic par Host header, dont 1.4.1 ET
  1.4.3 dépendent tous les deux pour qu'un domaine "actif" serve
  vraiment quelque chose), et 1.4.6 (flag white-label + templates
  conditionnels)
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
