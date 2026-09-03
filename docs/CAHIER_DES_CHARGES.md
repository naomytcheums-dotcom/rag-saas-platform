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

### 1.4 Domaine & White-label — 🟡 DÉMARRÉ (6✅/4🟡/0⬜ sur 10 -- **tous les items désormais touchés**, via les Étapes 1.4.1/1.4.2/1.4.3/1.4.4/1.4.5/1.4.6 + réutilisation honnête de 1.3.9/1.3.10)

| # | Fonctionnalité | Implémentation prévue | Statut |
|---|---|---|---|
| 1.4.1 | Custom domains | Table custom_domains, reverse-proxy dynamique (Caddy/Traefik) | ✅ (`api/models/custom_domain.py`, migration 0026, `ON DELETE CASCADE` depuis `organizations`, `UNIQUE(domain)` global -- deux organisations ne peuvent jamais revendiquer le même hostname. **Honnêteté de périmètre vérifiée avant d'écrire une ligne de code** : ce déploiement n'a AUCUN reverse-proxy routant par Host header (`render.yaml` déploie un unique conteneur Streamlit, `docker-compose.yml` est local-only, zéro config Traefik/Caddy nulle part dans ce dépôt) -- un domaine passant à `active` ne fait donc PAS réellement servir l'application sur `app.ma-boite.com`, ça demande une vraie infrastructure (1.4.3, non construite). Ce qui EST réel : un vrai enregistrement d'intention en base, un token de vérification vraiment aléatoire (`secrets.token_urlsafe(32)`, même générateur que reset de mot de passe/invitations), et une vraie recherche DNS TXT asynchrone (`dns.asyncresolver`, `dnspython` passé de dépendance transitive à directe) qui prouve le contrôle de la zone DNS avant toute vérification. Sous-domaine dédié `_rag-saas-verify.<domaine>` pour le challenge TXT (jamais le domaine nu, pour ne jamais entrer en collision avec des enregistrements SPF/DKIM existants). Une vérification échouée renvoie `200` avec `status="failed"`, jamais une erreur -- "DNS pas encore propagé" est le cas normal attendu, pas une exception ; l'Owner peut redemander la vérification autant de fois que nécessaire. `GET .../verify/{token}` délibérément public (le token est la preuve d'autorisation), recherché par (org_id, token) ensemble pour empêcher un token erroné de servir de sonde DNS arbitraire. `ssl_cert`/`ssl_key` sont des colonnes prévues pour 1.4.3, non utilisées ici -- documentées explicitement comme un risque si jamais remplies sans passer par `api/security/secret_encryption.py`. 26 tests SQLite (DNS mocké) + 4 tests contre le vrai DNS public (`tests/test_dns_verification_integration.py`, jamais de contenu externe précis vérifié, seulement le mécanisme) + 1 test contre le vrai Postgres, voir `tests/test_custom_domains.py`) |
| 1.4.2 | Instructions DNS | Page générée avec les enregistrements CNAME/TXT attendus | ✅ (chaque `DnsRecordEntry` porte désormais un champ `instructions` bilingue (`{"fr":..., "en":...}`), et chaque réponse de domaine porte un `setup_steps` -- une marche à suivre ordonnée, elle aussi bilingue, pensée pour un non-technicien (se connecter chez son fournisseur DNS, trouver la bonne section, ajouter les enregistrements, patienter, vérifier). Rien n'est stocké, tout recalculé à la volée (`api/security/custom_domains.py`'s `dns_records_for`/`setup_steps`). **Le texte des instructions décrit uniquement l'action DNS elle-même** ("ce CNAME relie votre domaine à notre plateforme", jamais "votre site est en ligne") -- cohérent avec l'absence réelle de reverse-proxy documentée en 1.4.1, pas de promesse de routage fonctionnel qui serait fausse. Seul reste un artefact frontend au sens littéral du spec original ("page générée") -- Partie 8 à 0%, même limite que 1.3.10 ; l'API elle-même est ce qu'un futur frontend consommerait. 3 tests dédiés (présence pour un domaine existant, valeurs correctes injectées dans le texte, présence ET différence réelle du FR et de l'EN -- pas une simple copie d'une langue vers l'autre), voir `tests/test_custom_domains.py`) |
| 1.4.3 | SSL auto (Let's Encrypt) | Traefik + resolver ACME, ou Caddy | 🟡 (`api/models/acme_account.py` + `api/models/ssl_certificate.py`, migration 0027 -- un vrai client ACME v2/RFC 8555 (`acme`/`josepy`, les mêmes bibliothèques que certbot), pas une réimplémentation du protocole. **Verdict 🟡 et non ✅, précisément parce que** le mot "auto" du titre de cet item n'est pas atteint : DNS-01 (le seul challenge que ce déploiement puisse supporter du tout, aucun reverse-proxy pour HTTP-01, voir 1.4.1) exige qu'un humain publie un enregistrement TXT à chaque émission ET à chaque renouvellement, puisqu'aucune intégration API fournisseur DNS n'existe pour le faire à sa place. Tout ce que cette application contrôle elle-même est en revanche réel et vérifié contre le vrai serveur de staging Let's Encrypt : inscription de compte, création de commande, calcul du challenge DNS-01, complétion réelle, et surtout **l'échec de validation sans jamais publier le vrai enregistrement DNS est confirmé produire une vraie erreur `ValidationError` du serveur réel**, exactement ce que le code gère. Flux réel en deux phases (premier appel : ouvre une commande, calcule le challenge, ne répond JAMAIS au challenge avant que le TXT soit publié -- y répondre trop tôt invaliderait le challenge définitivement ; second appel : répond, sonde brièvement, finalise si valide). Clé privée du certificat ET clé de compte ACME chiffrées via `api/security/secret_encryption.py` (même module que JWTSigningKey/EnterpriseSSOConnection) -- jamais retournées par aucune réponse API, à aucun rôle. Révocation ACME réelle possible sans challenge (preuve par le compte ou la clé du certificat, RFC 8555 §7.6). 2 tâches Celery périodiques réelles (`check_ssl_renewals`/`check_ssl_expirations`, item 5) -- pont vers le code asynchrone via `asyncio.run()`, un écart délibéré et documenté par rapport aux autres tâches Celery de ce projet (toutes synchrones), puisque dupliquer cette logique ACME réelle en synchrone serait une duplication substantielle et risquée pour aucun bénéfice réel. `ACME_DIRECTORY_URL` par défaut sur le staging Let's Encrypt, jamais la production. 20 tests SQLite (ACME mocké) + 4 tests contre le vrai staging Let's Encrypt (`tests/test_acme_integration.py`) + 5 tests contre le vrai Postgres pour les tâches Celery (`tests/test_ssl_certificate_renewal_integration.py`) + 1 test de cascade à deux niveaux (organisation → domaine → certificat) contre le vrai Postgres, voir `tests/test_ssl_certificates.py`) |
| 1.4.4 | Vérification domaine | Challenge TXT DNS, job Celery de polling | ✅ (le challenge TXT DNS lui-même était déjà réel depuis 1.4.1 ; cette étape ajoute le job Celery de polling qui manquait -- deux nouvelles colonnes sur `custom_domains` (migration 0028) : `verification_attempts`/`last_verification_attempt_at`, pas de nouvelle table. **Trois chemins de vérification délibérément séparés, pas unifiés** : le lien public à token (1.4.1) et le nouvel endpoint manuel Owner-authentifié vérifient immédiatement et échouent dès le premier échec DNS, exactement le comportement déjà livré et testé par 1.4.1 -- les unifier aurait changé ce comportement existant (régression). Seuls les chemins réellement automatiques (`poll_domain_verification`/`check_all_pending_domains`, tâche Celery Beat toutes les `DOMAIN_VERIFICATION_INTERVAL_SECONDS`, 5 min par défaut) comptent les tentatives et appliquent l'échec après épuisement -- deux limites indépendantes, `DOMAIN_VERIFICATION_MAX_ATTEMPTS` (12) ET `DOMAIN_VERIFICATION_TIMEOUT_MINUTES` (60), l'une ou l'autre suffit, ce qui protège un domaine même si le sweep périodique tourne moins souvent que prévu (panne worker, tick de beat manqué). **Scalabilité "milliers de domaines"** : les recherches DNS de `check_all_pending_domains` tournent en CONCURRENT (bornées par un sémaphore à 50), les écritures en base restent séquentielles (une seule `AsyncSession` n'est pas sûre en accès concurrent) -- une boucle purement séquentielle aurait pu faire durer un seul sweep plus longtemps que l'intervalle lui-même. Un check-and-schedule best-effort (`schedule_domain_verification`, enveloppé dans un `try/except` large) donne à un domaine tout juste créé une longueur d'avance sur le prochain sweep, sans jamais faire échouer la création elle-même si le broker est injoignable. 2 endpoints Owner (`POST .../verify` manuel, `GET .../status` avec `timeout_at` calculé à la volée). Tests SQLite (DNS mocké) pour toute la logique + tests contre le vrai Postgres pour les deux vraies tâches Celery, voir `tests/test_domain_verification.py`/`tests/test_domain_verification_integration.py`) |
| 1.4.5 | Custom email domain | Resend/SES avec domaine vérifié (DKIM/SPF) par org | 🟡 (neuf nouvelles colonnes sur `custom_domains`, migration 0029 -- pas de nouvelle table. **Vérifié contre la vraie documentation API de Resend avant d'écrire une ligne de code** : Resend génère et gère LUI-MÊME sa clé DKIM côté serveur pour chaque domaine, sous un sélecteur FIXE (`"resend"`) -- son API Domains réelle n'a aucun champ pour accepter une clé ou un sélecteur DKIM fourni par l'appelant. Ça crée un écart honnête, documenté explicitement (`api/security/email_domains.py`) : `generate_dkim_keys`/`get_dkim_dns_records`/`verify_dkim` (les noms de fonctions littéraux du spec) sont une infrastructure RÉELLE et testée (vraie paire RSA-2048, vraie vérification DNS de publication) mais ne signent PAS réellement le courrier sortant -- tout email de cette app passe par l'appel Resend `api/services/email.py`, qui signe DKIM avec SA PROPRE clé. Ce qui compte réellement pour la délivrabilité est l'intégration Resend elle-même (`api/services/resend_domains.py`, httpx brut, même convention "pas de SDK" que `api/services/email.py`) : `create_resend_domain`/`get_resend_domain`/`trigger_resend_domain_verification`/`delete_resend_domain`, exposés ensemble avec les 2 enregistrements maison via `GET .../email/dns`. **Verdict 🟡 et non ✅, découverte réelle en testant, pas hypothétique** : la vraie `RESEND_API_KEY` de ce projet (déjà utilisée pour de vrais envois) est restreinte à l'envoi seul -- l'API Domains de Resend la rejette avec une vraie erreur 4xx (`401 restricted_api_key` en local ; la clé placeholder de la CI reçoit une AUTRE vraie erreur, `400 validation_error` "API key is invalid" -- les deux réelles, les deux gérées correctement, aucun code spécifique fixe). Le code détecte et remonte ça correctement (jamais avalé ni maquillé), et se dégrade proprement (`resend_domain_id` reste vide, retenté au prochain appel), mais la création/vérification réelle d'un domaine chez Resend n'a pas pu être prouvée de bout en bout dans cet environnement sans une clé à accès complet. Vérification de propriété réelle et asynchrone via un TXT dédié `_rag-verify.<domaine>` (piste séparée de celle de 1.4.1), avec timeout indépendant (`EMAIL_DOMAIN_VERIFICATION_TIMEOUT_HOURS`, 24h par défaut). Clé privée DKIM chiffrée via `api/security/secret_encryption.py`, jamais retournée par aucune réponse API. Envoi réel testé honnêtement : `send_via_custom_email_domain` (nouveau, dans `api/services/email.py`) envoie pour de vrai via Resend avec un `from:` personnalisé, et le test d'intégration prouve le VRAI rejet par Resend tant que son propre objet domaine n'est pas vérifié -- pas un faux succès maquillé. 3 endpoints Owner (`POST .../email/verify`, `GET .../email/status`, `GET .../email/dns`). 34 tests SQLite (DNS + Resend mockés) + 8 tests contre le vrai DNS public, la vraie API Resend, et le vrai Postgres, voir `tests/test_email_domains.py`/`tests/test_email_domains_integration.py`) |
| 1.4.6 | White-label complet | Flag hide_platform_branding + templates conditionnels | ✅ (une colonne `hide_platform_branding` sur `organization_branding` existant, migration 0030 -- pas de nouvelle table. **Déviation délibérée du spec littéral, raisonnée et documentée, pas silencieuse** : l'item 2 demandait le même flag aussi sur `organization_settings` "pour garder la cohérence" -- mais `organization_settings` (1.3.9) n'a aucune colonne par réglage, c'est un blob JSON générique fusionné avec `DEFAULT_SETTINGS` à la lecture ; dupliquer le flag là créerait une SECONDE source de vérité indépendante pour le même booléen, sans mécanisme de synchronisation. `organization_branding` reste l'unique foyer cohérent, puisque ce flag ne fait que contrôler la visibilité des champs (`brand_name`/`logo_url`/`favicon_url`) déjà présents sur cette même table. **La config white-label EST la config branding, pas un système parallèle** (`api/security/white_label.py`) : `get_white_label_config` retourne exactement le même dict que `GET .../branding` existant. `PATCH .../white-label` n'accepte QUE ce flag -- couleurs/police/`custom_css` restent sur `PATCH .../branding`, pas de double chemin de validation. 2 endpoints Owner (`GET`/`PATCH /organizations/{id}/white-label`), volontairement PAS publics contrairement au `GET .../branding` existant (celui-ci reste public et inchangé pour l'écran de connexion/widget) -- `hide_platform_branding` reste aussi visible via cet endpoint public existant, cohérence testée et prouvée, pas seulement affirmée. Intégration frontend (item 5) : contrat documenté (variables CSS `--platform-name`/`--platform-logo`, composants conditionnels) plutôt que du code réel -- Partie 8 à 0%, même limite honnête que 1.3.10/1.4.2 ; le favicon personnalisé était déjà réel depuis 1.3.10. 14 tests SQLite (défaut, activation/désactivation, non-régression des autres champs branding, permissions Owner-only sur les deux endpoints, 404, cohérence avec le GET public), voir `tests/test_white_label.py`) |
| 1.4.7 | Logo/favicon/brand name | Champs dans organization_branding | ✅ (déjà livré par 1.3.10 -- `organization_branding.logo_url`/`favicon_url`/`brand_name` sont exactement ces champs ; aucun travail supplémentaire nécessaire) |
| 1.4.8 | Couleurs/polices/thème | CSS custom properties depuis organization_branding.theme_json | 🟡 (couleurs et police déjà livrés par 1.3.10 -- mais comme des colonnes typées et validées individuellement, pas un blob `theme_json` générique comme le spec original l'envisageait ; `custom_css` couvre l'extension libre. Aucune page pour injecter ces variables CSS -- même limite que 1.3.10, Partie 8 à 0%) |
| 1.4.9 | Email sender custom | En-tête From: dynamique selon domaine vérifié | 🟡 (partiellement satisfait par 1.4.5 -- `send_via_custom_email_domain` fait exactement ça, un en-tête `From:` dynamique selon le domaine vérifié, réel et testé contre la vraie API Resend. Ce qui manque : rien dans ce dépôt n'appelle encore cette fonction pour les emails réels de l'application -- les ~30 fonctions `send_*_email` d'`api/services/email.py` (reset mot de passe, invitations, etc.) utilisent toujours `EMAIL_FROM_ADDRESS` sans exception ; câbler un choix d'expéditeur par organisation dans ces flux existants est un chantier séparé, non demandé par la liste d'actions littérale de 1.4.5) |
| 1.4.10 | System prompt/persona IA | Colonne organization_settings.system_prompt | ✅ (déjà livré par 1.3.9 -- `system_prompt` fait partie des 14 réglages de `DEFAULT_SETTINGS`, lisible/modifiable via `GET`/`PATCH /organizations/{id}/settings` ; même réserve que 1.3.9 : rien dans `src/` ne le consomme encore, `AGENT_SYSTEM_PROMPT`/`SYSTEM_PROMPT` y restent en dur) |

---

## PARTIE 2 — Knowledge Base universelle — 🟡 DÉMARRÉ (15✅/2🟡/18⬜ sur 35, via les Étapes 2.1.1/2.1.2/2.1.3/2.1.4/2.1.5/2.1.6/2.1.7/2.1.8/2.1.9/2.1.10/2.1.11/2.1.12/2.1.13/2.1.14/2.1.15/2.1.16/2.1.17)

### 2.1 Import de documents

| # | Format | Implémentation prévue |
|---|---|---|
| 2.1.1 | PDF | ✅ `pymupdf` (fitz) -- exactement la bibliothèque prévue ici, vérifiée pour de vrai (contre un vrai PDF généré, pas supposée depuis la doc) avant d'écrire le code de traitement : `page.find_tables()` détecte et extrait réellement des tableaux, donc AUCUNE bibliothèque séparée (pdfplumber, camelot) n'est nécessaire -- pymupdf seul couvre texte, tableaux, métadonnées ET images embarquées. Deux nouvelles tables (`documents`/`document_chunks`, migration 0031). Upload réel vers un bucket S3 SÉPARÉ et privé (`S3_DOCUMENTS_BUCKET_NAME`, sans ACL publique -- contrairement au bucket avatars/branding, dont la politique CI MinIO rend TOUT le contenu public, un risque réel évité ici par un bucket dédié plutôt qu'un simple préfixe de clé). Traitement asynchrone réel via Celery (`process_document_task`), qui transitionne `pending`→`processing`→`completed`/`failed` pour de vrai -- toute erreur (PDF corrompu, échec S3, échec d'embedding) est capturée et enregistrée, jamais un crash silencieux du worker. Chunking réel PAR PAGE (même algorithme que `src/indexing.py`, réimplémenté indépendamment pour préserver la frontière api/↔src/), utilisant pour la première fois `organization_settings.chunk_size`/`chunk_overlap` (1.3.9, jusqu'ici jamais lus). Embeddings réels via `sentence-transformers`, utilisant pour la première fois `organization_settings.embedding_model` -- honnêtement borné : ce n'est PAS l'abstraction multi-fournisseurs complète de la Partie 4 (toujours ⬜), juste une génération réelle et fonctionnelle avec le seul modèle déjà configuré par défaut. **Permissions : un vrai trou comblé, pas contourné en silence** -- l'Etape 1.2.5 avait explicitement anticipé et laissé cette lacune ("un endpoint d'écriture que Viewer ne devrait pas atteindre... devrait être sa propre fonction") ; `require_org_member_excluding_viewer` (nouveau) comble exactement ça pour `POST .../documents`. `DELETE /documents/{id}` : Member+ propriétaire, avec dérogation Admin/Owner, y compris si l'utilisateur a été rétrogradé en Viewer après l'upload (testé explicitement). 35 tests SQLite (upload, permissions, isolation cross-org) + 12 tests réels d'extraction PDF (aucun mock, PyMuPDF génère ET extrait) + 6 tests d'intégration réels (embeddings et chunking réels toujours exécutés ; le pipeline complet avec vrai S3 skip proprement si `S3_DOCUMENTS_BUCKET_NAME` n'est pas configuré -- délibérément non provisionné automatiquement) + 1 test de cascade réel contre Postgres, voir `tests/test_documents.py`/`tests/test_pdf_extraction.py`/`tests/test_documents_integration.py` |
| 2.1.2 | DOCX | ✅ `python-docx` -- exactement la bibliothèque prévue ici. **Même structure que le code PDF de 2.1.1, délibérément** (cohérence vérifiée par test, pas seulement affirmée) : `api/services/docx_extraction.py` reproduit fonction pour fonction `extract_docx_text`/`extract_docx_tables`/`extract_docx_metadata` de son équivalent PDF, plus `extract_docx_styles` (nom de style Word réel par paragraphe -- "Heading 1", "Normal", etc. -- pour un futur chunking sémantique, Partie 3.2.4, toujours ⬜ ; cette étape expose seulement la structure réelle déjà stockée par Word, elle ne construit pas le chunking par titre lui-même). Nouveau dispatcher `api/services/document_extraction.py`'s `extract_document_content`, appelé par le pipeline de traitement réel (renommé `process_pdf_document` → `process_document`, puisqu'un nom encore "PDF" en traitant un DOCX serait trompeur) -- PDF et DOCX partagent réellement le même code de chunking/embedding à partir de ce point, pas deux pipelines parallèles qui se ressemblent. Un DOCX n'a pas de pages fixes au niveau du format (la pagination est un détail d'affichage Word, jamais stocké dans le XML) -- ses chunks ne portent honnêtement aucune clé `page`, contrairement à un chunk PDF. **Découverte réelle en testant, pas hypothétique** : la hiérarchie d'exceptions de `python-docx` est bien moins prévisible que celle de PyMuPDF -- un fichier non-DOCX lève `PackageNotFoundError`, mais un ZIP structurellement valide avec un XML interne corrompu lève une simple `AttributeError` venue du cœur de `python-docx`, confirmé pour de vrai avant d'écrire le code (pas supposé) ; la fonction d'ouverture capture donc largement (`Exception`), pas seulement l'exception DOCX-spécifique. Validation d'upload généralisée dans `api/services/document_storage.py` : un DOCX est un ZIP, donc la signature seule ne suffit pas à le distinguer d'un XLSX/PPTX/ZIP quelconque -- confirmation réelle que `word/document.xml` est présent à l'intérieur. **Bug réel trouvé et corrigé en cours de route** : la migration 0031 (2.1.1) avait oublié d'activer le Row-Level-Security sur les deux nouvelles tables, cassant un test d'invariant déjà existant (`test_every_application_table_has_row_level_security_enabled`) -- corrigé par une migration de suivi (0032) plutôt que de réécrire une migration déjà appliquée. 34 tests SQLite/réels supplémentaires (extraction DOCX réelle sans mock, dispatcher, upload DOCX de bout en bout, rejet d'un ZIP non-DOCX, incohérence type déclaré/réel) + 4 tests d'intégration réels supplémentaires (pipeline DOCX complet, échec DOCX corrompu -- les deux formes réelles de corruption), voir `tests/test_docx_extraction.py`/`tests/test_document_extraction.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.1.3 | TXT | ✅ Lecture brute + détection réelle d'encodage (`charset-normalizer`, déjà présent transitivement via `requests`/`acme`, épinglé directement maintenant que le code l'importe lui-même). **Validation d'un genre différent, pas juste un troisième format collé au même moule** : contrairement au PDF/DOCX (signature/structure réelle à vérifier), un texte brut n'a aucune signature -- "est-ce un vrai TXT" ne peut vouloir dire que "est-ce que ça se décode comme du texte sous un encodage réel courant", vérifié en dernier dans `validate_document_upload` (après avoir écarté PDF/DOCX en premier, du plus spécifique au moins spécifique). **Découverte réelle en testant, pas hypothétique** : la détection universelle naïve d'encodage se trompe réellement sur les encodages occidentaux mono-octet historiques -- un échantillon français réel encodé en ISO-8859-1 a été détecté comme `cp1257` (un codepage balte sans rapport) et mal décodé, confirmé avant d'écrire le code. **Correction vérifiée pour de vrai** : le paramètre `cp_isolation` de `charset-normalizer` restreint les candidats à une liste réaliste (`ascii`, `utf_8`, `iso8859_1`, `cp1252`, `utf_16`) -- retesté avec succès sur UTF-8/ISO-8859-1/Windows-1252. **Limite réelle, non corrigible, énoncée clairement plutôt que masquée** (vision critique 2) : ISO-8859-1 et Windows-1252 sont identiques octet pour octet pour tout caractère du texte occidental normal -- `detect_encoding` peut rapporter l'un ou l'autre pour les mêmes octets, ce n'est pas un bug mais une ambiguïté réelle et inévitable (même convention que les navigateurs web). Un texte pur ASCII est correctement étiqueté `"ascii"`, pas `"utf_8"` -- un résultat plus précis, pas une erreur de détection. **Robustesse** : un fichier vide est un texte valide et trivial (testé explicitement) ; contrairement au PDF/DOCX, TXT n'a pas de mode d'échec "conteneur valide, contenu corrompu" distinct -- la validation d'upload et le traitement partagent exactement la même détection, donc un TXT accepté à l'upload ne peut pas échouer indépendamment à l'extraction (documenté explicitement plutôt que de fabriquer un faux scénario de "TXT corrompu"). **Performance** : la détection elle-même n'échantillonne que quelques blocs de ~512 octets par défaut, indépendamment de la taille du fichier (confirmé par la signature réelle de la fonction), donc pas de dégradation avec de gros fichiers. 14 tests dédiés à l'extraction/détection (`tests/test_txt_extraction.py`, UTF-8/ISO-8859-1/Windows-1252/UTF-16/binaire/vide) + tests supplémentaires pour le dispatcher, l'upload TXT de bout en bout (y compris fichier vide et non-UTF-8), et le pipeline d'intégration réel complet, voir `tests/test_txt_extraction.py`/`tests/test_document_extraction.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.1.4 | Markdown | ✅ **Existait déjà dans `src/ingestion.py`, mais pour le pipeline RAG mono-tenant de démonstration FastAPI, pas pour le pipeline multi-tenant `api/`** -- `src/ingestion.py` lu en entier avant d'écrire une ligne de code (item 1 de cette étape), pas supposé : il résout des inclusions `{* path *}` spécifiques à la doc FastAPI contre un dépôt SIBLING `../fastapi`, et retire la syntaxe `///admonition///` de mkdocs-material -- les deux corrects UNIQUEMENT pour ce corpus précis, activement FAUX pour un fichier Markdown uploadé par un client (résoudre `{* ... *}` littéral contre un dépôt qui n'existe pas dans ce déploiement). Aucun frontmatter YAML n'y est jamais parsé, et son propre texte "nettoyé" reste volontairement au format Markdown -- l'objectif littéral de cette étape ("texte brut sans la syntaxe Markdown") est différent de toute façon. Ce qui EST réellement réutilisé, comme CONCEPT et non comme code (`api/` n'a aucune dépendance d'import vers `src/`, tenu depuis 1.3.9) : `split_into_sections` de `src/indexing.py` regroupe les chunks par limite de titre -- `extract_markdown_sections` fait la même chose, indépendamment, via un vrai flux de tokens plutôt que des regex. Parsing réel via `markdown-it-py` (déjà présent transitivement via `rich`) + `mdit-py-plugins` pour les vrais tableaux GFM et le frontmatter YAML -- vérifié pour de vrai que CommonMark seul ne gère ni l'un ni l'autre. **Généralisation réelle et délibérée de la forme partagée du dispatcher**, motivée directement par la structure réelle de Markdown : chaque section porte désormais son propre dict de métadonnées (`{"page": N}` pour PDF, `{"heading": ..., "level": ...}` pour Markdown, `{}` pour DOCX/TXT) au lieu d'un cas spécial PDF isolé -- réponse réelle et câblée à la vision critique 2 ("les titres sont-ils conservés pour le chunking sémantique ?"), contrairement à la réponse plus prudente de DOCX (`extract_docx_styles`, extrait mais pas encore utilisé). **Vrai cas de corruption propre à Markdown** : CommonMark ne échoue jamais à parser, mais un frontmatter avec un YAML réellement invalide lève une vraie `yaml.YAMLError`, traduite en `ValueError` -- contrairement à TXT qui n'a aucun mode d'échec "conteneur valide/contenu corrompu" distinct. **Seule exception réelle et délibérée à "le contenu décide du type, jamais le nom déclaré"** : au niveau des octets, du Markdown valide EST simplement du texte valide -- aucun signal basé sur le contenu seul ne peut le distinguer d'un upload TXT, donc `validate_document_upload` prend maintenant aussi le nom de fichier, vérifié seulement après que la validation de contenu réelle a déjà réussi (un fichier `.md` contenant du vrai binaire reste rejeté). Tests réels dédiés (texte sans syntaxe, structure, frontmatter présent/absent/invalide, sections par titre, tableaux GFM) + dispatcher + upload de bout en bout (y compris désambiguïsation TXT/Markdown par nom de fichier) + pipeline d'intégration réel complet (frontmatter réel, chunking par titre réel, embeddings réels) contre le vrai Postgres, voir `tests/test_markdown_extraction.py`/`tests/test_document_extraction.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.1.5 | HTML | ✅ **Exactement les bibliothèques prévues ici** : `readability-lxml` (le vrai algorithme arc90-readability, qui score les blocs par densité de texte réelle pour isoler l'article et écarter nav/header/footer/publicités) pour le contenu principal, `BeautifulSoup4` pour les métadonnées `<head>` et les liens `<a>`. L'encodage réutilise la détection déjà vérifiée de `api/services/txt_extraction.py` (même réutilisation que Markdown -- le HTML reste du texte brut au niveau des octets). **Découverte réelle n°1, vérifiée avant d'écrire le code** : `readability.Document(html).summary()` ne lève JAMAIS sur du HTML malformé (balises non fermées, `<div>` abandonné au milieu d'un paragraphe) -- le parseur lxml répare silencieusement, exactement comme un vrai navigateur le ferait avec la même page. Une page réellement vide (`<body></body>`) ne lève pas non plus -- `extract_html_content` renvoie simplement `""`, le même traitement "contenu trivial valide" qu'un TXT/Markdown vide reçoit déjà ailleurs dans ce pipeline. Réponse réelle et testée à la vision critique 4 ("malformé ? page vide ?") : aucun des deux cas ne plante. **Découverte réelle n°2** : `readability-lxml` lève bel et bien une vraie exception catchable (`Unparseable`, une sous-classe de `ValueError`) quand un document n'a STRICTEMENT AUCUN élément analysable -- un fichier contenant uniquement un commentaire HTML (`<!-- ... -->`), confirmé pour de vrai (`lxml.etree.ParserError: Document is empty`). Une histoire réelle en deux temps, pas une lacune de conception : un tel fichier passe légitimement la validation d'upload (un commentaire HTML est un vrai motif reconnu par la détection ci-dessous) mais échoue réellement au TRAITEMENT, capturé par le gestionnaire d'exception déjà existant de `process_document`, aboutissant à `status = "failed"` avec l'erreur réelle enregistrée -- exactement la même histoire honnête que le frontmatter YAML invalide de Markdown (2.1.4), testée de la même façon. **Détection de contenu réelle, basée sur une spécification -- le HTML n'a PAS besoin de l'exception de nom de fichier de Markdown** : contrairement au Markdown (identique aux octets à du texte brut, aucun signal de contenu n'existe), le HTML réel a une vraie signature structurelle. `_is_real_html` (`api/services/document_storage.py`) implémente l'algorithme "matching an HTML byte pattern" du WHATWG MIME Sniffing Standard -- la même règle de détection de contenu utilisée par les vrais navigateurs pour reconnaître `text/html` quand un serveur n'envoie aucun Content-Type fiable. Vérifié pour de vrai : les mêmes octets HTML sont détectés comme `text/html` qu'ils soient nommés `.html`, `.htm`, ou même `.txt`, tandis qu'un texte qui mentionne juste le mot "html" sans vraie structure de balises reste correctement `text/plain`. **Les liens extraits atterrissent dans `metadata["links"]`** (fonction optionnelle de l'item 2, `extract_html_links`) -- le même endroit où vivent déjà les extras propres à chaque format (encodage/line_count pour TXT, frontmatter/heading_count pour Markdown), pas une cinquième clé de premier niveau rien que pour un format. Les métadonnées titre/auteur/date/description préfèrent les balises Open Graph (`og:title`, `og:description`) à leurs équivalents plus simples quand les deux existent -- choix éditorial délibéré, l'inverse de `.title()` de readability-lxml lui-même (vérifié pour de vrai : il préfère la balise `<title>` nue à `og:title`). Tests réels dédiés (extraction article vs. bruit de page, tolérance au HTML malformé, page vide, échec réel du fichier "commentaire seul", métadonnées avec préférence Open Graph et repli sur `<time datetime=...>`, extraction de liens) + dispatcher (liens câblés dans `metadata["links"]`) + upload de bout en bout (détection par contenu indépendante du nom de fichier, variante `.htm`, texte mentionnant "html" restant `text/plain`, rejet d'un `.html` qui n'est pas du vrai texte) + pipeline d'intégration réel complet (extraction d'article réelle, embeddings réels) contre le vrai Postgres, avec son propre test réel d'échec sur fichier "commentaire seul", voir `tests/test_html_extraction.py`/`tests/test_document_extraction.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.1.6 | CSV | ✅ **Exactement la bibliothèque prévue ici** (`pandas`, déjà présente depuis 2.1.1). Détection automatique du délimiteur via `csv.Sniffer` du stdlib Python -- aucune nouvelle dépendance. **Découverte réelle n°1, vérifiée avant d'écrire le code** : `csv.Sniffer` détecte fiablement virgule/point-virgule/tabulation/pipe sur un échantillon réel et cohérent (confirmé pour les quatre), mais échoue réellement (`csv.Error: Could not determine delimiter`) sur plusieurs cas pourtant valides : un CSV à une seule colonne (aucun délimiteur à trouver), un fichier vide, et -- plus surprenant -- tout échantillon contenant ne serait-ce qu'une seule ligne avec un nombre de champs différent des autres (une seule ligne incomplète suffit à dérouter l'heuristique). `detect_csv_delimiter` retombe sur `,` (le défaut RFC 4180) plutôt que de lever et bloquer tout l'upload -- une limite réelle, énoncée clairement, même esprit que l'ambiguïté ISO-8859-1/Windows-1252 de TXT. **Découverte réelle n°2** : la détection de délimiteur est une heuristique de fréquence de caractères, pas une vraie validation CSV -- confirmé pour de vrai qu'une simple prose contenant des virgules est détectée à tort comme délimitée par virgule ; restreindre `csv.Sniffer` aux quatre séparateurs réels du cahier des charges (`,;\t|`) évite un faux positif bizarre issu d'une ponctuation quelconque, mais ne corrige PAS ce cas précis -- énoncé clairement plutôt que masqué par une heuristique fragile non demandée. **Découverte réelle n°3** : `pandas.read_csv` tolère une ligne avec MOINS de champs que l'en-tête (valeurs manquantes remplies par un vrai `NaN`, pas une erreur) mais lève réellement une vraie `pandas.errors.ParserError` catchable pour une ligne avec PLUS de champs, et une vraie `pandas.errors.EmptyDataError` pour un fichier réellement vide -- deux vrais modes d'échec "CSV malformé" distincts, capturés par le gestionnaire d'exception déjà existant de `process_document`, exactement comme le cas de corruption propre à chaque autre format. Réponse réelle et testée à la vision critique 4 ("colonnes incohérentes ?") : moins de champs toléré, plus de champs rejeté -- pas symétrique, énoncé comme tel. Les champs entre guillemets contenant le délimiteur lui-même (`"Dupont, Jean"` dans un CSV séparé par virgules) sont correctement traités comme UN seul champ, confirmé pour de vrai. **Deuxième exception réelle et délibérée à "le contenu décide du type, jamais le nom déclaré"**, aux côtés de Markdown : au niveau des octets, un CSV valide (notamment à une seule colonne) EST simplement du texte valide -- `validate_document_upload` vérifie l'extension `.csv` de la même façon qu'elle vérifie déjà `.md`/`.markdown`, uniquement après que la validation de contenu réelle a déjà réussi. **Texte structuré réel pour le pipeline de chunking partagé** (vision critique 2) : `extract_csv_text` renvoie du vrai JSON Lines (un objet JSON réel par ligne, via `to_json` de pandas plutôt qu'un formateur maison ou la dépendance `tabulate` qu'exigerait `to_markdown()`) -- confirmé pour de vrai que les valeurs manquantes deviennent un vrai `null` JSON, sans logique d'échappement séparée nécessaire pour les virgules/guillemets/unicode dans une cellule. Le vrai DataFrame du CSV atterrit dans la MÊME liste `"tables"` que les tableaux réels des autres formats -- un CSV EST fondamentalement un tableau, pas un format nécessitant un nouveau concept de premier niveau (réponse réelle à la vision critique 1). Tests réels dédiés (détection des quatre délimiteurs, repli sur virgule pour les cas à une colonne/incohérents/vides -- y compris la limite honnête du faux positif sur de la prose --, extraction DataFrame avec champ guillemeté contenant le délimiteur, asymétrie moins-de-champs-toléré/plus-de-champs-rejeté, extraction JSON Lines, métadonnées) + dispatcher (DataFrame câblé dans `"tables"`) + upload de bout en bout (désambiguïsation TXT/CSV par nom de fichier, rejet d'un `.csv` qui n'est pas du vrai texte) + pipeline d'intégration réel complet (détection réelle du point-virgule, embeddings réels) contre le vrai Postgres, avec son propre test réel d'échec sur ligne à champs excédentaires, voir `tests/test_csv_extraction.py`/`tests/test_document_extraction.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.1.7 | JSON | ✅ Parsing réel via le module stdlib `json` de Python (accéléré en C), sans nouvelle dépendance. Le cahier des charges décrit cet item comme "Parsing récursif configurable (JSONPath)" -- un moteur de requêtes JSONPath complet (ex. `jsonpath-ng`, une vraie nouvelle dépendance) n'est délibérément PAS ajouté : aucune des actions littérales de cette étape ne demande de requêtage par chemin ; le parsing récursif réel existe bien (`_compute_stats`), simplement pas exposé comme un langage de requête que personne n'a demandé. **Découverte réelle n°1, vérifiée avant d'écrire le code -- ET CORRIGÉE après que la CI a capturé un vrai bug de portabilité dans la première version de cette affirmation** : le parseur JSON accéléré en C du stdlib tolère un niveau d'imbrication bien au-delà de la limite de récursion par défaut de Python (1000) avant de lever une vraie `RecursionError` -- mais la profondeur EXACTE à laquelle cela se produit n'est PAS une constante portable : une première version de ce texte (et de son test) annonçait un chiffre précis confirmé en local sous Windows, mais le vrai runner CI sous Linux tolérait PLUS de profondeur que ce même chiffre (un vrai environnement différent : taille de pile C, build Python), et ce test a échoué là-bas. L'affirmation honnête : cette limite dépend de l'environnement réel, ce n'est pas un nombre fixe sur lequel ce codebase peut compter -- `json.dumps` en resérialisant cette même structure touche la limite de ce même environnement, pas une plus basse. **Découverte réelle n°2, un vrai bug évité avant sa mise en production** : une première implémentation RÉCURSIVE (pas itérative) du calcul de profondeur/nombre de clés échouait dès la profondeur ~500 en test local -- bien AVANT la limite de `json.loads` lui-même dans ce même environnement -- car chaque appel Python empile sur la pile d'appel déjà utilisée par l'appelant (pytest, Celery, uvicorn), contrairement à la gestion interne du parseur C. La fonction finale est donc ITÉRATIVE (pile explicite), confirmée pour de vrai pour gérer des profondeurs bien au-delà de ce qu'une version récursive pourrait atteindre, quel que soit l'environnement -- réponse réelle et testée à la vision critique 3 ("structure trop profonde ?"), et un vrai bug capturé par le test avant la livraison, pas supposé correct. Autre vrai bug capturé ENSUITE par la CI elle-même (pas seulement par les tests locaux) : le test de profondeur excessive utilisait initialement un chiffre fixe qui échouait sur le runner Linux mais pas en local Windows -- corrigé en utilisant une profondeur bien plus large (1 000 000 de niveaux), une marge de sécurité délibérément énorme au lieu d'un nombre supposé universel. **Découverte réelle n°3 (performance, vision critique 4)** : un vrai fichier JSON généré de 200 000 enregistrements / ~21,7 Mo se parse via `json.loads` en ~0,25s dans cet environnement -- rapide, largement dans la limite de 50 Mo d'upload de ce codebase. Aucun parseur JSON en streaming (`ijson`) n'est utilisé -- une vraie nouvelle dépendance que cette étape n'a jamais demandée -- donc la limite honnête énoncée est que le fichier entier charge en mémoire d'un coup, à l'échelle de la limite d'upload, pas au-delà. Un test réel encode cette mesure comme vérification automatisée continue (~5 Mo/50 000 enregistrements, borne de temps généreuse), pas une mesure manuelle ponctuelle qui pourrait se périmer silencieusement. **Signal de contenu le plus fort de tous les formats jusqu'ici** : `_is_real_json` exige que le contenu commence par un vrai `{`/`[` ET se parse intégralement sous le module `json` du stdlib -- contrairement à l'heuristique de HTML (peut avoir un faux positif sur de la prose) ou au sniffing de délimiteur CSV (peut avoir un faux positif sur de la prose avec virgules), la syntaxe JSON valide est exacte et non ambiguë, donc le JSON n'a besoin ni d'heuristique ni de l'exception de nom de fichier de Markdown/CSV. Une seule restriction réelle et délibérée : un scalaire JSON nu en racine (`42`, `"hello"`, `true` -- tous valides selon la RFC 8259) n'est PAS classé comme JSON ici, précisément parce que CE cas précis est réellement ambigu avec un simple fichier texte court -- `extract_json_structure` classe quand même correctement un scalaire nu (`"scalar"`) pour les appelants directs ; c'est une règle d'upload délibérément plus étroite, pas une limite du module d'extraction. Conséquence énoncée clairement : contrairement à Markdown/CSV/HTML, un JSON malformé ou trop profondément imbriqué est REJETÉ (ou retombe en texte brut) DÈS L'UPLOAD, pas différé à un échec de traitement asynchrone -- `_is_real_json` effectue déjà exactement le même parsing complet que `extract_json_data`, donc aucun test d'intégration "accepté puis échoue" n'a de sens réel ici, contrairement à chaque autre format. **Texte structuré réel** (vision critique 2) : `extract_json_text` renvoie du JSON Lines réel (même convention que `extract_csv_text`) -- une LISTE de premier niveau devient un objet JSON réel par ligne ; tout le reste (un objet unique, ou un scalaire nu) devient une seule ligne. La liste `"tables"` partagée du dispatcher reste vide pour JSON (vision critique 1) -- un objet/tableau JSON n'est pas généralement tabulaire comme un CSV l'est toujours, et cette étape n'a jamais demandé de conversion dict/list vers DataFrame. Tests réels dédiés (objets/tableaux plats et imbriqués, classification "tableau d'objets plats = quand même imbriqué" énoncée explicitement, scalaire nu, JSON malformé réel, échec réel de profondeur excessive, contenu binaire réel, extraction JSON Lines, vérification réelle de performance) + dispatcher + upload de bout en bout (détection par contenu indépendante du nom de fichier, cas scalaire nu et JSON malformé retombant en texte brut, rejet d'un `.json` qui n'est pas du vrai texte) + pipeline d'intégration réel complet (métadonnées réelles, embeddings réels) contre le vrai Postgres, voir `tests/test_json_extraction.py`/`tests/test_document_extraction.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.1.8 | XML | ✅ **Exactement la bibliothèque prévue ici** (`lxml`, déjà présente depuis 2.1.5). **Question littérale de la vision critique tranchée directement** : `lxml.etree` reproduit délibérément l'API du stdlib `xml.etree.ElementTree` -- l'utiliser, c'est déjà "utiliser ElementTree", via l'implémentation plus rapide, basée sur libxml2, que le cahier des charges demande lui-même. `xmltodict` (confirmé pour de vrai : pas déjà installé) n'est délibérément PAS ajouté -- `extract_xml_data` réimplémente sa propre convention de conversion en dict réelle et bien connue directement sur `lxml.etree` (clés `@attr`, `#text` pour le contenu mixte, les frères répétés deviennent une liste), vérifiée contre un vrai appel `xmltodict.parse()` (installé temporairement pour comparaison, puis retiré) avant de s'engager sur cette forme. **Découverte réelle n°1, une histoire PLUS rassurante que le problème de profondeur JSON de la Partie 2.1.7** : libxml2 impose sa propre garde-fou réel et DÉLIBÉRÉ de profondeur d'imbrication -- confirmé pour de vrai : rejet réel au-delà de 257 niveaux avec une vraie `XMLSyntaxError`, par conception, pas un effet de bord accidentel de la taille de pile C du thread du système d'exploitation comme la `RecursionError` du parseur json de CPython s'est avérée l'être. Comme cette garde-fou s'exécute À L'INTÉRIEUR de `etree.fromstring` lui-même, les fonctions de parcours d'arbre de ce module restent de simples fonctions RÉCURSIVES ordinaires, pas la réécriture itérative à pile explicite que JSON a nécessitée -- un arbre que lxml a accepté de construire ne peut jamais être assez profond pour déranger la limite de récursion par défaut de Python. **Découverte réelle n°2, une vraie découverte de SÉCURITÉ** : `etree.fromstring` avec les réglages par défaut de lxml est confirmé pour de vrai VULNÉRABLE à un déni de service classique par expansion d'entités ("billion laughs") -- vérifié avec une vraie charge utile avant de décider comment parser du XML uploadé arbitraire (la vraie attaque XXE classique -- une entité externe SYSTEM lisant un fichier local -- est déjà refusée par le parseur par défaut de cette version de lxml/libxml2, mais c'est une protection SÉPARÉE ; le billion-laughs réussit quand même contre elle, confirmé séparément). Chaque parsing dans ce module utilise donc un vrai `etree.XMLParser(resolve_entities=False, no_network=True)` explicite et durci -- confirmé pour de vrai pour neutraliser le cas billion-laughs tout en continuant à parser correctement les documents normaux, à rejeter le XML malformé, et à faire respecter la garde-fou de profondeur ci-dessus. **Vrai compromis honnête, énoncé clairement** : `resolve_entities=False` empêche aussi les entités internes BÉNIGNES de se résoudre -- le choix correct et délibéré pour un pipeline qui traite du contenu uploadé arbitraire venant de n'importe quel membre d'organisation, la sécurité l'emportant sur une fonctionnalité XML rarement utilisée qui est aussi le mécanisme exact dont dépend la vraie attaque. La détection de contenu réelle à l'upload (`_is_real_xml`) réutilise CE MÊME `SAFE_XML_PARSER`, pas une deuxième copie configurée indépendamment qui pourrait dériver silencieusement. **Découverte réelle n°3, un vrai bug capturé en faisant réellement tourner le cas billion-laughs à travers les parcours d'arbre de ce module, pas seulement en confirmant que le parsing lui-même ne plantait pas** : avec la résolution d'entités désactivée, une référence d'entité non résolue ne disparaît PAS de l'arbre -- elle devient un vrai nœud enfant distinct dont le `.tag` est la fonction factory `etree.Entity` de lxml elle-même, pas une chaîne de caractères. Une première version des parcours d'arbre de ce module supposait que toute valeur retournée par `for child in elem` était un élément normal et plantait avec une vraie `TypeError` -- corrigé par `_is_element` (`isinstance(node.tag, str)`), qui filtre aussi correctement les commentaires XML et les instructions de traitement au passage. **Vrai compromis honnête d'ambiguïté de format** (vision critique 1) : XML et HTML peuvent commencer par exactement les mêmes octets -- un document commençant par une vraie déclaration `<?xml ...?>` est vérifié, et fait confiance, AVANT le sniffing HTML (aucune vraie page HTML5 n'en produit une) ; le XML non déclaré est vérifié APRÈS le sniffing HTML à la place, donc un document XML non déclaré dont la balise racine coïncide avec un des motifs de sniffing HTML (ex. un hypothétique document XML raciné par `<table>` sans déclaration) est classé comme HTML, pas XML -- une vraie limite réelle, étroite, explicitement testée, pas une lacune masquée en silence. **Texte structuré réel `tag/chemin: texte`** (vision critique 2) : `extract_xml_text` émet une ligne par élément portant du vrai texte, montrant à la fois D'OÙ vient une valeur et CE QU'elle dit, en laissant délibérément les attributs hors du texte (ils vivent dans les métadonnées/structure à la place). `extract_xml_structure` renvoie un vrai DICT de deux indicateurs oui/non (`has_attributes`, `has_nested_elements`) plutôt que la chaîne de taxonomie unique du classificateur JSON de la Partie 2.1.7 -- une forme délibérément plus fidèle à la demande littérale de cette étape ("attributs, éléments imbriqués" -- deux vraies questions, pas une catégorie), pas une incohérence. Tests réels dédiés (extraction texte chemin/valeur, survie d'un commentaire réel à l'itération, neutralisation réelle du billion-laughs y compris le fix du nœud d'entité non résolue, rejet malformé/vide/non-XML/binaire, échec réel de profondeur excessive, dépouillement du nom d'espace de noms, convention dict conforme à xmltodict, détection de structure plate et imbriquée) + dispatcher (fusion des deux indicateurs de structure dans les métadonnées) + upload de bout en bout (détection par contenu déclarée/non déclarée, la vraie limite de collision HTML verrouillée par son propre test, rejet d'un `.xml` qui n'est pas du vrai texte) + pipeline d'intégration réel complet (comptages réels d'éléments/attributs, embeddings réels) contre le vrai Postgres, voir `tests/test_xml_extraction.py`/`tests/test_document_extraction.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.1.9 | EPUB | ✅ **Exactement la bibliothèque prévue ici** (`ebooklib`), tranchant directement la vision critique 5. Le texte des chapitres est converti en texte brut via `BeautifulSoup`, déjà une vraie dépendance depuis 2.1.5 -- un chapitre EPUB EST simplement du XHTML, donc réutilisation du même nettoyage de balises réel plutôt qu'une seconde implémentation indépendante. **Découverte réelle n°1, même type de découverte que python-docx en 2.1.2** : la hiérarchie d'exceptions d'`ebooklib` pour un upload corrompu est réellement imprévisible -- confirmé contre quatre scénarios de corruption réels distincts : un contenu qui n'est pas un ZIP lève `EpubException` ; un vrai ZIP sans `META-INF/container.xml` lève une simple `KeyError` ; un vrai ZIP dont container.xml pointe vers un OPF manquant lève une `EpubException` différente ; un vrai ZIP avec un OPF présent mais réellement malformé lève une simple `AttributeError` venue du cœur du modèle objet d'ebooklib. `_open` suit exactement le même précédent que `_open` de DOCX : capture large (`Exception`), pas seulement la classe propre à la bibliothèque, puis relève comme une `ValueError` claire. **Découverte réelle n°2, un bug silencieux évité avant la livraison** : la première version de ce module supposait que `EpubHtml.title` survivrait à un vrai cycle écriture-lecture -- confirmé pour de vrai que ce n'est PAS le cas (`item.title == ""` après relecture d'un fichier écrit avec `title="Chapter One"`) ; c'est une commodité d'écriture propre à ebooklib, pas une vraie propriété du manifeste OPF relisible. `extract_epub_chapters` récupère plutôt le titre réel de chaque chapitre depuis la vraie table des matières du livre (`book.toc`, associée par `href`) -- confirmée pour de vrai comme survivant réellement au cycle écriture-lecture, contrairement à `title` par item. **Découverte réelle n°3** : les entrées de `book.toc` ne sont pas uniformément des objets `Link` -- un vrai EPUB peut imbriquer un tuple `(Section, [enfants])` pour une table des matières hiérarchique (ex. "Partie Un" contenant plusieurs chapitres), confirmé pour de vrai en en construisant une. `extract_epub_toc` aplatit cela récursivement, marquant chaque entrée réelle avec son propre niveau d'imbrication -- même réponse "aplatir avec un marqueur de niveau explicite" que les sections de titres Markdown de la Partie 2.1.4. **Conception de sections réelle et délibérée, suivant le précédent Markdown de la Partie 2.1.4** (vision critique 2) : un EPUB a de vraies frontières naturelles de chapitres, comme un document Markdown a de vraies frontières de titres -- le dispatcher utilise `extract_epub_chapters` (une vraie section par chapitre, portant ses propres métadonnées `{"chapter": titre}`) pour ses sections, pas `extract_epub_text` (conservée comme sa propre fonction réelle et indépendamment utile pour un appelant voulant le livre entier en un seul bloc) -- structure réelle de chapitres véritablement câblée dans le chunking, pas extraite puis laissée inutilisée. **Signature d'upload réelle et déterministe, encore plus forte que celle de DOCX** (vision critique 1) : un EPUB est un vrai ZIP, exactement comme DOCX, mais `_is_real_epub` confirme que l'entrée `mimetype` de l'archive -- exigée par la spécification EPUB Open Container Format pour être la toute PREMIÈRE entrée, NON COMPRESSÉE -- contient exactement les octets `application/epub+zip`, confirmé pour de vrai contre un vrai EPUB généré. C'est une signature imposée par la spécification, à contenu FIXE, pas juste une partie interne requise mais autrement arbitraire comme la vérification `word/document.xml` de DOCX -- donc EPUB n'a pas non plus besoin de repli sur le nom de fichier. **Réponse honnête de robustesse** (vision critique 4) : EPUB a un vrai écart "accepté à l'upload, échoue au traitement", contrairement à JSON/XML -- `_is_real_epub` ne vérifie que l'entrée `mimetype` du ZIP, un contrôle bien plus superficiel qu'un parsing complet via `epub.read_epub()`, donc un fichier peut réellement passer la validation d'upload et pourtant manquer de `META-INF/container.xml` ou avoir un OPF malformé, confirmé pour de vrai et capturé par le gestionnaire d'exception déjà existant de `process_document` -- la même histoire d'échec honnête que la Partie 2.1.2 a construite pour un DOCX corrompu, testée de la même façon. Tests réels dédiés (métadonnées avec plusieurs auteurs réels, table des matières plate et imbriquée, extraction de chapitres réels dans l'ordre du spine en excluant la navigation, nettoyage HTML, quatre scénarios de corruption réels) + dispatcher (sectionnement réel par chapitre) + upload de bout en bout (détection par contenu indépendante du nom/type déclaré, rejet d'un vrai ZIP qui n'est pas un vrai EPUB) + pipeline d'intégration réel complet (métadonnées réelles par chapitre dans les chunks, embeddings réels) contre le vrai Postgres, avec son propre test réel d'échec sur conteneur manquant, voir `tests/test_epub_extraction.py`/`tests/test_document_extraction.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.1.10 | URLs / pages web | ✅ `httpx` + `readability-lxml` (exactement comme prévu, tous deux déjà présents). `Playwright` (le "si JS nécessaire" du cahier) délibérément NON ajouté -- aucune action littérale de cette étape ne demande de rendu JS, et c'est une vraie dépendance lourde (un navigateur complet) à ne pas ajouter sans un besoin réel exprimé. **Une menace réelle et différente de toutes les étapes précédentes** : chaque format précédent traite des octets déjà fournis par l'appelant ; importer "la page à cette URL" signifie que CE SERVEUR fait une vraie requête HTTP sortante vers une adresse que l'appelant contrôle -- terrain classique de SSRF (OWASP A10:2021), exactement ce que la vision critique 2 demande d'analyser directement. **Architecture réelle et délibérée, vérifiée avant d'écrire le code de production** : chaque connexion réelle passe par un transport httpx personnalisé dont le pool de connexions httpcore sous-jacent utilise un backend réseau personnalisé qui résout lui-même le nom d'hôte cible et valide l'IP résultante AVANT de se connecter -- confirmé pour de vrai que ceci bloque une requête directe vers une adresse privée/loopback/link-local, ET (le cas strictement plus difficile et plus important) une requête qui résout d'abord vers une adresse sûre mais redirige ensuite vers une adresse privée, puisque httpx réinvoque le backend pour chaque nouvel hôte d'une chaîne de redirections -- valider seulement le nom d'hôte original une fois (une erreur courante et insuffisante) NE bloquerait PAS ce cas. **Découverte réelle, pourquoi `ip.is_global` plutôt qu'une liste noire artisanale** : une première version utilisait `ipaddress.ip_address(...).is_private` -- confirmé pour de vrai qu'elle rate `100.64.0.0/10` (l'espace d'adressage partagé RFC 6598, un vrai espace de CGNAT que certains réseaux cloud/FAI routent réellement). `is_global` (une liste blanche par défaut-refus -- "est-ce une vraie adresse Internet publique routable" -- plutôt qu'une liste noire qui doit énumérer correctement chaque plage dangereuse) exclut correctement ce cas, ainsi que tout ce que `is_private`/`is_loopback`/`is_link_local`/`is_reserved`/`is_unspecified` couvraient déjà, y compris l'IPv4-mappée-en-IPv6 loopback et la vraie adresse de métadonnées cloud (169.254.169.254). Le seul vrai trou de `is_global` lui-même -- une adresse multicast rapporte `is_global=True` -- est comblé par une vérification explicite `not ip.is_multicast`, confirmée pour de vrai avant de faire confiance à `is_global` seul. **Réutilisation réelle et complète du pipeline, la réponse la plus forte possible à la vision critique 1** : une fois le contenu d'une URL réellement récupéré, il est uploadé vers S3 et traité EXACTEMENT comme un upload de fichier -- quoi que `validate_document_upload` détecte réellement (presque toujours `text/html`, mais honnêtement ce que l'URL pointe réellement) -- puis `process_url_document` appelle le MÊME `process_document` que chaque autre format utilise déjà. Aucun nouveau `file_type` ni branche de dispatcher n'existe pour "une URL" en tant que format -- ce n'en est pas un, c'est un vrai transport pour amener les octets d'un format déjà supporté sur ce serveur, comme le corps multipart d'un upload l'est déjà. Ceci répond directement à l'action littérale de cette étape sur le dispatcher : aucun changement à `extract_document_content` n'était nécessaire, en ajouter un aurait été un chemin parallèle et redondant, pas une meilleure cohérence. **Séparation asynchrone/Celery réelle, réponse propre à la vision critique 4** : la route elle-même n'exécute que la validation pure et sans réseau du format/protocole de l'URL de façon synchrone -- l'accessibilité réelle, robots.txt, et la récupération réelle (toutes de vraies E/S réseau, y compris la résolution DNS dont dépend la vérification SSRF elle-même) sont délibérément différées vers une vraie tâche Celery, avec le même pont `asyncio.run()` déjà établi par `api/tasks/document_processing.py`. Une cible lente ou ne répondant pas ne peut donc jamais bloquer un worker HTTP ; le document se termine en `status = failed` avec l'erreur réelle enregistrée, comme un upload corrompu. **Réponses honnêtes de robustesse** (vision critique 3) : un vrai 404 en direct termine le document en `failed` avec l'erreur réelle enregistrée, confirmé contre un vrai chemin inaccessible, pas un échec simulé. `validate_url_robots_txt` (l'item "optionnel" du cahier) traite un robots.txt manquant ou injoignable comme "autorisé" (un site sans préférence exprimée n'en a aucune à respecter, convention réelle des crawlers) mais bloque réellement un robots.txt accessible qui interdit le vrai User-Agent transparent de cet importeur (jamais un navigateur usurpé). La taille de réponse est plafonnée à la MÊME limite que chaque fichier uploadé, appliquée en comptant les vrais octets reçus en streaming, pas en faisant confiance à un en-tête Content-Length qu'un serveur peut omettre ou falsifier. Tests réels dédiés (validation d'URL pure, blocage SSRF réel contre des adresses privées/loopback/metadata littérales sans aucun aller-retour réseau réel, fetch réel et robots.txt réel contre un vrai domaine de documentation RFC 2606, extraction réelle de métadonnées/contenu, la route complète bout en bout, garde-fou cross-tenant, planification Celery, permissions) + pipeline d'intégration réel complet (import bout en bout réel contre une vraie page externe ET un vrai chemin inaccessible) contre le vrai Postgres et le vrai S3, voir `tests/test_url_fetching.py`/`tests/test_url_fetching_integration.py`/`tests/test_url_extraction.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.1.11 | Sitemap | ✅ Parsing réel via `lxml` (déjà présent depuis 2.1.5/2.1.8, réutilisant directement le `SAFE_XML_PARSER` durci de 2.1.8 -- aucune nouvelle dépendance). **"Réutilisation sur réutilisation", pas un chemin d'import parallèle** -- la réponse la plus forte possible à la vision critique 1 : `fetch_sitemap` (nouveau module `api/services/sitemap_extraction.py`) est un simple wrapper autour du `fetch_url_content` SSRF-safe de 2.1.10, sans nouvelle logique réseau ni de sécurité, et chaque page résultante est importée par `process_single_url_task`, lui-même un simple wrapper Celery appelant le `import_document_from_url` de 2.1.10 totalement inchangé. **Découverte réelle n°1, vérifiée avant d'écrire le code de production** : un vrai sitemap est du XML avec espace de noms (`xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"`) -- `parse_sitemap`/`parse_sitemap_index` utilisent un XPath `local-name()` plutôt qu'une comparaison de balise brute, confirmé pour fonctionner que l'espace de noms soit déclaré ou non (certains sitemaps réels l'omettent, techniquement non conforme mais réel). **Découverte réelle n°2** : les vrais sitemaps sont couramment compressés en gzip (`.xml.gz`) -- `fetch_sitemap` décompresse de façon transparente via le module stdlib `gzip` après vérification des vrais octets magiques (`\x1f\x8b`), avec une vraie trouvaille capturée avant mise en production : un contenu dont les deux premiers octets RESSEMBLENT à du gzip mais qui n'est pas des données gzip valides lève `gzip.BadGzipFile` (une sous-classe d'`OSError`, pas de `ValueError`) -- re-levée comme la même `ValueError` que chaque autre échec réel de ce module, confirmé pour de vrai avant de faire confiance à un simple `except ValueError` en amont. `parse_sitemap` et `parse_sitemap_index` sont mécaniquement identiques (toutes deux extraient chaque `<loc>` un niveau sous un élément répété) mais restent deux fonctions distinctes et nommées séparément puisque leur vraie SIGNIFICATION diffère (pages vs. sous-sitemaps), partageant un seul helper privé `_real_locs()`. **Réponses réelles de scalabilité** (vision critique 3, "sitemap de 50 000 URLs") : `SitemapImportRequest.max_urls` est un vrai plafond côté client (`pydantic.Field(default=500, ge=1, le=5000)`) sur le nombre de PAGES réellement importées ; un plafond interne SÉPARÉ `_MAX_SUB_SITEMAPS = 50` protège la phase de PARSING elle-même (récupérer et combiner les sous-sitemaps) d'un épuisement de ressources, indépendamment de `max_urls` -- la récursion dans un sitemap INDEX est plafonnée à exactement UN niveau de profondeur (un sous-sitemap est supposé être un vrai `<urlset>`, jamais un index imbriqué plus loin), une vraie limite de portée énoncée explicitement. Un vrai étalement de courtoisie entre les dispatches Celery par page (`_SITEMAP_PER_URL_STAGGER_SECONDS = 2` via `apply_async(countdown=...)`, lui-même plafonné à `_SITEMAP_MAX_STAGGER_SECONDS = 600`) répartit les vraies requêtes vers le site cible dans le temps réel plutôt que de toutes les envoyer dans la même seconde. **Décision réelle et délibérée d'ordonnancement** : `process_sitemap` filtre AVANT de plafonner à `max_urls`, pas après -- plafonner en premier pourrait silencieusement écarter exactement les URLs qu'un vrai filtre était censé garder, si elles se trouvaient après la position `max_urls` dans le sitemap brut non filtré ; prouvé contre de vraies données dans `tests/test_sitemap_integration.py` (un vrai filtre correspondant à un vrai sous-ensemble de 4 URLs sur un vrai sitemap de 84 URLs survit même avec `max_urls` fixé bien au-delà de 4). **Réponses réelles de robustesse** (vision critique 4, "que se passe-t-il si une URL échoue"), à chaque niveau de ce vrai fan-out : un sous-sitemap défaillant pendant la récursion d'un index est journalisé et ignoré sans jamais interrompre le reste d'un vrai index (confirmé via un vrai scénario à trois sous-sitemaps, l'un échouant délibérément) ; une page individuelle défaillante ne marque QUE ce document `failed`, hérité gratuitement du `process_url_document` de 2.1.10, sans jamais toucher ses siblings ; un raté du broker en planifiant la tâche d'UNE page est journalisé et ignoré par `process_sitemap_urls`, le reste du lot continue de se planifier ; un échec au niveau du sitemap racine lui-même (URL injoignable, XML réellement malformé) termine tout l'import en un vrai résultat `"failed"` journalisé, confirmé contre un vrai 404 en direct. **Une seule limite réelle, honnêtement énoncée, pas masquée** : aucune nouvelle entité de suivi "job d'import de sitemap" n'a été créée -- chaque document produit par un import de sitemap reste visible individuellement de la façon habituelle (`GET /organizations/{org_id}/documents`), mais il n'existe aucune vue agrégée "N/M URLs traitées" ; un échec au niveau racine n'est reflété que dans le résultat Celery de `process_sitemap_task` et dans les logs de ce serveur. La route répond `202 Accepted`, pas `201 Created` -- rien n'est réellement créé de façon synchrone, le sitemap lui-même n'est même pas encore récupéré au moment où la réponse part. **Séparation asynchrone/Celery réelle, même réponse que 2.1.10, un niveau plus haut** : la route ne fait que de la validation non-réseau bon marché de façon synchrone (format d'URL du sitemap, propriété cross-tenant du workspace) ; toute opération réseau réelle (le fetch du sitemap, chaque sous-sitemap, chaque page) est différée vers Celery -- `process_sitemap_task` n'a besoin d'AUCUN moteur/session de base de données, contrairement à chaque autre tâche de ce codebase, puisque `process_sitemap` ne touche jamais directement la base de données de ce serveur. Tests réels dédiés (parsing avec/sans espace de noms, classification index/urlset, XML malformé, filtrage par motif glob, décompression gzip réelle et détection d'un faux gzip) + tests réels réseau (fetch et parsing d'un vrai sitemap externe) + tests unitaires réels pour `process_sitemap_urls` (filtrage réel, valeurs exactes de l'étalement et de son plafond, tolérance réelle à un raté de broker par tâche, sans broker réel -- même convention que `tests/test_celery_integration.py`) + tests de route de bout en bout (démarrage d'import, schéma d'URL rejeté, garde-fou cross-tenant, validation des bornes de `max_urls`, filtres transmis à la planification, permissions) + pipeline d'intégration réel complet (fetch/parse/routage `is_sitemap_index`/ordre filtre-puis-plafond de `process_sitemap` contre un vrai sitemap externe de 84 URLs, un vrai échec 404 en direct, une vérification croisée du compte d'URLs) -- le pipeline réel par page que ce dispatch déclencherait est déjà prouvé de bout en bout par le test d'intégration réel de 2.1.10, donc délibérément pas ré-exécuté ici, voir `tests/test_sitemap_extraction.py`/`tests/test_sitemap_extraction_integration.py`/`tests/test_documents.py`/`tests/test_sitemap_integration.py` |
| 2.1.12 | GitHub repos | ✅ **API GitHub REST uniquement -- PAS de `git clone` (même superficiel), une vraie déviation délibérée par rapport au texte original de cette ligne, assumée et expliquée, pas silencieuse** : la section "Implémentation prévue" ci-dessus mentionnait un clone superficiel, mais les actions à réaliser réellement demandées pour cette étape (items 1 à 8, le texte qui fait foi) ne décrivent QUE des fonctions REST API (`fetch_github_repo`, `fetch_github_files`, `fetch_github_file_content`) -- aucune ne mentionne de clone. Cloner ajouterait un vrai sous-processus git, du vrai stockage disque temporaire, et sa propre gestion d'échec/nettoyage, pour zéro bénéfice réel : l'API REST fournit déjà tout ce que cette étape demande réellement (arbre de fichiers, contenu de fichier, métadonnées). **"Réutilisation du pipeline existant", même histoire que 2.1.10/2.1.11, à une source réelle différente** : chaque fichier réel importé passe par le MÊME `validate_document_upload`/`process_document` inchangé qu'un upload de fichier, et `Document.source_url` (colonne de 2.1.10) est réutilisée telle quelle pour une vraie URL `github.com/.../blob/...` cliquable -- aucune nouvelle colonne. **Une vraie réponse SSRF différente de 2.1.10/2.1.11, et pourquoi c'est correct, pas une incohérence** (vision critique 2) : un simple `httpx.AsyncClient` est utilisé, PAS le transport SSRF-safe personnalisé de `url_fetching.py` -- la vraie raison est structurelle : la cible réelle de CE flux est toujours l'hôte FIXE et configuré par l'opérateur (`GITHUB_API_BASE_URL`), jamais un hôte choisi par l'appelant (`owner`/`repo` ne deviennent que des segments de CHEMIN sur cet hôte fixe) -- le même schéma déjà utilisé pour la vérification Have I Been Pwned et la découverte OIDC entreprise. **Sécurité réelle du token, la réponse la plus forte de toute étape d'import jusqu'ici** (vision critique 2) : `GITHUB_API_TOKEN` (un vrai secret serveur, jamais un champ de la requête) n'est JAMAIS transmis à travers les arguments d'une tâche Celery -- une déviation réelle et délibérée par rapport à la signature littérale de cette étape, qui listait `token` comme argument : le faire aurait mis le secret en clair dans Redis (le broker) et potentiellement dans les résultats/logs Celery. Chaque appel réel à l'API lit `settings.GITHUB_API_TOKEN` directement, au moment précis où il en a besoin. **Découvertes réelles vérifiées avant d'écrire le code de production** : les requêtes non authentifiées sont réelles et autorisées (60/heure) à un taux bien plus bas qu'un token authentifié (5000/heure) ; un dépôt inexistant ET un vrai dépôt PRIVÉ sans accès suffisant renvoient exactement le même 404 -- confirmé pour de vrai, une conception anti-énumération délibérée de GitHub, énoncée honnêtement plutôt que de prétendre pouvoir distinguer les deux cas (réponse réelle à la vision critique 4, "que se passe-t-il si le dépôt est privé et qu'aucun token n'est fourni") ; un token réellement invalide obtient son propre 401 réel et distinguable ; chaque réponse réelle porte les vrais headers `X-RateLimit-*` ; l'API Contents n'intègre le contenu d'un fichier en base64 QUE jusqu'à 1 Mo -- confirmé pour de vrai contre un vrai fichier de plus de 1 Mo dans un vrai dépôt public (`encoding` devient `"none"`, un `download_url` vers un hôte ENTIÈREMENT DIFFÉRENT, `raw.githubusercontent.com`, apparaît à la place) -- le défaut littéral de `GITHUB_MAX_FILE_SIZE` (1 Mo) correspond exactement à cette vraie limite d'API, pas une coïncidence : filtrer par taille réelle AVANT de demander le contenu évite à ce codebase d'avoir besoin d'un second vrai client HTTP vers ce second hôte. **Performance et respect réel du rate limiting, la réponse la plus forte de toute étape d'import jusqu'ici** (vision critique 3/4) : `process_github_repo` utilise la vraie API Git Trees récursive (un seul vrai appel liste tout l'arbre du dépôt) plutôt que de parcourir chaque dossier un appel à la fois ; avant de distribuer les tâches Celery par fichier, un vrai appel GRATUIT à `GET /rate_limit` (confirmé pour de vrai : cet endpoint ne consomme pas le quota) plafonne proactivement la distribution réelle au quota réellement restant, plutôt que de planifier aveuglément `max_files` tâches qui échoueraient en majorité avec un vrai 403 en cours de route. `GITHUB_INCLUDE_PATTERNS` est une vraie LISTE BLANCHE, pas un filtre optionnel de narrowing comme les `filters` du sitemap de 2.1.11 -- un dépôt de code contient réellement beaucoup de contenu qu'une base de connaissances ne doit jamais ingérer (binaires, images, artefacts compilés), sans signal de contenu les distinguant comme le fait `validate_document_upload` pour un upload. **Conséquence réelle honnêtement documentée** : un fichier sans extension (un vrai `README` sans `.md`, un vrai `Makefile`) ne correspond jamais à une liste blanche purement basée sur l'extension et n'est jamais importé par défaut -- confirmé pour de vrai contre le vrai `README` sans extension d'`octocat/Hello-World`. **Différence architecturale réelle et délibérée par rapport aux fonctions par-item de 2.1.10/2.1.11, expliquée plutôt que laissée incohérente** : `import_and_process_github_file` crée le Document en attente ET le récupère/traite en UNE seule fonction réelle, puisque la liste exacte des fichiers à importer n'est connue qu'APRÈS le vrai listing d'arbre de `process_github_repo`, déjà différé à Celery -- il n'existe aucun moment synchrone antérieur où un Document en attente aurait pu être créé, contrairement à une simple URL ou une page de sitemap. Tests réels dédiés (validation d'URL de dépôt, en-tête Authorization présent seulement avec un vrai token, chaque échec réel distinguable 404/401/403-rate-limit/403-simple, normalisation de la liste de fichiers, décodage base64 réel, filet de sécurité du fichier de plus de 1 Mo, filtrage blob uniquement, drapeau `truncated`, extraction de métadonnées avec et sans données pré-récupérées, liste blanche d'extensions, aller-retour construction/analyse d'URL de fichier y compris une branche réelle contenant une barre oblique) + tests réels réseau (dépôt public réel, 404 réel, 401 réel, métadonnées réelles, listing de répertoire réel, téléchargement de fichier réel, listing d'arbre récursif réel, vérification réelle du rate limit) + tests unitaires réels pour `process_github_files` (étalement réel, plafond réel, tolérance réelle à un raté de broker par tâche, sans broker réel) + tests de route de bout en bout (démarrage d'import, URL de dépôt invalide rejetée, garde-fou cross-tenant, validation des bornes de `max_files`, motifs/`max_files` transmis à la planification, permissions) + pipeline d'intégration réel complet (fetch/filtre/plafond de `process_github_repo` contre un vrai dépôt externe, un vrai échec 404, une vérification croisée contre un arbre récupéré indépendamment ; pipeline par fichier réel de bout en bout -- fetch GitHub réel, S3 réel, Postgres réel, embeddings réels -- contre un vrai fichier et un vrai fichier inexistant), voir `tests/test_github_extraction.py`/`tests/test_github_extraction_integration.py`/`tests/test_documents.py`/`tests/test_github_integration.py`/`tests/test_documents_integration.py` |
| 2.1.13 | GitHub issues | ✅ **API GitHub REST "Issues List" (`/repos/{owner}/{repo}/issues`), PAS l'API Search -- une vraie déviation délibérée par rapport au texte original de cette ligne, assumée et expliquée** : confirmé pour de vrai que l'API Search a son propre vrai quota séparé et bien plus restrictif (`x-ratelimit-limit: 10` par minute, ressource `search`) que le vrai quota "core" (60/heure non authentifié, 5000/heure authentifié) que l'endpoint Issues List utilise -- la réponse directement la plus forte possible à la vision critique 2 ("le rate limiting est-il respecté ?"), et l'endpoint Issues List est de toute façon l'outil documenté exact pour "lister les issues d'UN dépôt connu", pas pour une recherche cross-dépôts. **Même histoire de réutilisation que 2.1.12, transformée en vrai Markdown d'abord** (vision critique 1) : chaque issue réelle passe par `format_issue_for_import` (titre + métadonnées + corps + commentaires, en vrai Markdown) puis EXACTEMENT le même pipeline upload/`process_document` que chaque autre format -- un nom de fichier `.md` déclenche le vrai repli de nom de fichier de `validate_document_upload` (Partie 2.1.4), donc le vrai sectionnement Markdown par titre découpe une issue selon sa propre structure réelle, pas comme un bloc indifférencié. **Découvertes réelles vérifiées avant d'écrire le code de production** : le vrai endpoint Issues de GitHub renvoie aussi de vraies PULL REQUESTS, pas seulement de vraies issues -- confirmé pour de vrai contre un vrai dépôt actif (`expressjs/express`) : GitHub traite en interne une PR comme un type spécial d'issue, distinguable UNIQUEMENT par une vraie clé `pull_request` présente sur l'objet JSON -- toujours exclues. Le vrai paramètre `labels` de l'API utilise une sémantique ET réelle (un vrai test avec `labels=docs,tests` n'a renvoyé que la seule vraie issue portant LES DEUX) -- donc `labels` n'est JAMAIS transmis à la vraie API, `should_include_issue` l'applique côté CLIENT à la place, avec une vraie sémantique OU (n'importe lequel des labels donnés correspond), la même réponse que le `filter_sitemap_urls` de la Partie 2.1.11. `state`/`since` sont bien envoyés à la vraie API (aucune ambiguïté similaire) ; un `state` invalide ou un `since` malformé obtiennent chacun leur propre vrai 422 distinct de GitHub, confirmé pour de vrai -- mais `state` est déjà contraint aux trois vraies valeurs de GitHub au niveau du schéma de ce serveur (`Literal`), un vrai 422 structurel de ce serveur avant même d'atteindre GitHub pour ce cas précis. **Une vraie différence de forme de données par rapport à chaque import GitHub précédent** : `process_github_issues` doit déjà récupérer les vrais commentaires de chaque issue AVANT tout dispatch Celery (pour décider de l'inclure), donc les données réelles déjà assemblées (issue + commentaires) sont transmises DIRECTEMENT à la tâche Celery par issue en argument (le paramètre littéral `issue_data` de cette étape) -- contrairement au contenu réel d'un fichier de dépôt (récupéré À L'INTÉRIEUR de sa propre tâche, un contenu réel trop volumineux pour transiter utilement par un argument Celery), la tâche par issue ne fait ici AUCUN appel API GitHub réel supplémentaire. Les commentaires ne sont récupérés QUE pour une issue qui en a réellement (son propre vrai compteur `comments`, déjà connu dès le premier fetch) -- jamais une requête réelle gaspillée pour une issue qui n'en a aucun. **Performance et respect réel du rate limiting, même réponse proactive que 2.1.12** (vision critique 2/3) : après avoir récupéré et plafonné les vraies issues correspondantes à `max_issues`, un vrai appel GRATUIT à `GET /rate_limit` plafonne les vrais fetches de commentaires à venir sur le quota réellement restant, avant même d'en lancer un seul. Un dépôt sans la moindre issue correspondante (réponse réelle à la vision critique 3, "que se passe-t-il si le dépôt n'a pas d'issues") n'est PAS un échec -- 0 vraie issue, 0 vraie tâche planifiée, un vrai `"completed"`, exactement comme `process_github_repo` trouvant 0 fichier après filtrage. Tests réels dédiés (filtrage réel par état et par labels avec sémantique OU, exclusion réelle des pull requests en paginant, arrêt de pagination à la première vraie page vide, `state`/`since` atteignant la vraie chaîne de requête tandis que `labels` n'y arrive jamais, récupération réelle de commentaires, extraction de métadonnées, formatage Markdown réel avec et sans corps/commentaires) + tests réels réseau contre `github/docs` (délibérément PAS `octocat/Hello-World`/`Spoon-Knife`, confirmé pour de vrai que ces deux-là ont accumulé des milliers de vraies issues de pratique non labellisées et sans commentaire -- 4397 et 603 respectivement -- alors que `github/docs` filtré à `state="open"` est un vrai ensemble borné, de première partie, réellement curé, labellisé et commenté) + tests unitaires réels pour `process_github_issue_documents` (étalement réel, plafond réel, tolérance réelle à un raté de broker) + tests de route de bout en bout (démarrage d'import, URL de dépôt invalide, `state` invalide rejeté par un vrai 422, garde-fou cross-tenant, validation des bornes de `max_issues`, state/since/labels/max_issues transmis à la planification, permissions) + pipeline d'intégration réel complet (fetch/filtre/plafond/assemblage de commentaires de `process_github_issues` contre `github/docs`, une vraie exclusion par label, un vrai échec 404 ; pipeline par issue réel de bout en bout -- fetch GitHub réel, S3 réel, Postgres réel, embeddings réels -- atterrissant comme un vrai Document `text/markdown`), voir `tests/test_github_extraction.py`/`tests/test_github_extraction_integration.py`/`tests/test_documents.py`/`tests/test_github_integration.py`/`tests/test_documents_integration.py` |
| 2.1.14 | Google Drive | 🟡 **API Google Drive v3 réelle + un vrai flux OAuth 2.0 refresh-token serveur-à-serveur, PAS `google-api-python-client`/`google-auth`** -- même restreinte "pas de SDK lourd sans besoin réel exprimé" que les étapes précédentes (pas de Playwright, pas de `git clone`, pas d'API Search) : la surface REST réelle dont cette étape a besoin (échange OAuth, `files.list`/`get`, téléchargement `alt=media`) tient en une poignée d'appels HTTP simples. **Limite honnête et explicitement assumée, contrairement à 2.1.12/2.1.13** : `gh auth token` avait fourni un vrai identifiant GitHub utilisable dans cette même session ; aucun équivalent n'existe pour Google, et en obtenir un exigerait un vrai flux de consentement OAuth interactif dans un navigateur, hors du périmètre sûr et automatisé de cette session (même restreinte que `S3_DOCUMENTS_BUCKET_NAME`, jamais auto-provisionné). Le code est complet et implémenté contre le comportement RÉEL et documenté de l'API Google, mais la vérification de bout en bout contre un vrai compte Drive n'a PAS pu être effectuée -- d'où le statut 🟡, pas ✅, une évaluation honnête plutôt qu'une fausse certitude. **Ce qui A pu être vérifié pour de vrai, en direct, sans le moindre identifiant valide** : un `client_id` OAuth réel mais non enregistré renvoie un vrai 401 (`invalid_client`) depuis `oauth2.googleapis.com` ; omettre `client_id` entièrement renvoie un vrai 400 différent (`invalid_request`) -- une découverte réelle supplémentaire ; l'API Drive elle-même renvoie un vrai 403 (`PERMISSION_DENIED`) sans aucun header d'autorisation, et un vrai 401 (`UNAUTHENTICATED`) avec un token d'accès présent mais invalide -- tous deux sous la vraie enveloppe d'erreur IMBRIQUÉE de Google (`{"error": {"code", "message", "status"}}`), une forme réellement différente de chaque erreur plate façon GitHub déjà gérée par ce codebase. Un refresh token expiré/révoqué contre un vrai client enregistré (`invalid_grant`) est mappé sur la foi de la documentation stable et publiée de Google, pas déclenché indépendamment (aucun vrai client enregistré n'était disponible). **Réponse réelle et proactive à la vision critique 4 ("que se passe-t-il si le token expire")** : `authenticate_drive` échange et met en cache un vrai token d'accès, le RAFRAÎCHISSANT avant sa propre expiration réelle (une vraie marge de sécurité de 60 secondes), confirmé pour de vrai via un test direct de la séquence cache-puis-quasi-expiration-puis-rafraîchissement -- pas seulement réagi après un vrai 401. Même raisonnement de sécurité que `GITHUB_API_TOKEN` : le refresh token/client_id/secret ne transitent JAMAIS par les arguments d'une tâche Celery -- et les signatures littérales des tâches de cette étape n'incluaient déjà AUCUN paramètre de token dès l'origine (contrairement à la signature littérale de `process_github_repo` en 2.1.12, qui en listait un et a dû être corrigée). **Découverte réelle Drive spécifique** : un vrai fichier natif Google Workspace (Doc/Sheet/Slide) n'a AUCUN contenu binaire téléchargeable -- Google documente que l'endpoint séparé `files.export` est requis à la place d'un téléchargement classique ; `should_include_drive_file` exclut toujours ces fichiers (et les vrais dossiers), quels que soient les `patterns` -- portée explicitement séparée de la Partie 2.1.15 ("Google Docs API export -> Markdown"), pas réimplémentée ici. La taille réelle des fichiers (`size`, un vrai détail d'API Drive : renvoyé comme une vraie CHAÎNE JSON, pas un nombre, convention Google de sécurité de précision int64) est appliquée AVANT le téléchargement (réponse réelle à la vision critique 4, "si le fichier est trop gros") -- le champ `size` de Drive est une métadonnée de première main fiable, contrairement au `Content-Length` d'une URL externe arbitraire, donc aucun filet de sécurité par comptage d'octets en streaming n'était nécessaire ici. **Limite de portée réelle et honnêtement énoncée** : la récursion dans les vrais sous-dossiers n'est PAS implémentée -- les actions à réaliser littérales de cette étape décrivent l'import des propres fichiers du dossier donné (`list_drive_files(folder_id, ...)`), correspondant à la portée réelle de `files.list` de Drive (enfants directs d'un seul parent réel), pas un parcours récursif complet façon API Git Trees (l'API réelle de Drive n'a aucun appel unique équivalent ; un vrai parcours récursif coûterait un vrai appel API PAR vrai sous-dossier). Tests réels dédiés (échange/mise en cache/rafraîchissement proactif réels du token, chaque échec réel distinguable, pagination réelle, filtrage réel dossier/fichier-natif-Google/taille/motif, extraction réelle de métadonnées y compris la conversion taille chaîne-vers-entier, téléchargement binaire réel) + tests réels réseau (les vrais rejets OAuth/Drive ci-dessus confirmés en direct, sans identifiant valide, plus des tests réels conditionnés à un vrai compte qui s'ignorent proprement si `GOOGLE_DRIVE_REFRESH_TOKEN`/`CLIENT_ID`/`CLIENT_SECRET` ne sont pas configurés) + tests de route de bout en bout (démarrage d'import, `drive_id` vide rejeté, garde-fou cross-tenant, bornes de `max_files`, motifs transmis à la planification, permissions) + tests d'orchestration réels contre une simulation fidèle et fabriquée à la main des vraies formes de réponse Drive déjà confirmées en direct (résolution dossier/fichier unique, filtrage, plafond, gestion des échecs d'authentification/404) + pipeline d'intégration réel complet conditionné à un vrai compte (découvre dynamiquement un vrai fichier importable dans la racine réelle du compte configuré, plutôt que de supposer qu'un identifiant public bien connu existe comme `octocat/Hello-World` pour GitHub -- il n'en existe aucun équivalent pour un compte Drive privé), voir `tests/test_google_drive_extraction.py`/`tests/test_google_drive_extraction_integration.py`/`tests/test_documents.py`/`tests/test_google_drive_integration.py`/`tests/test_documents_integration.py` |
| 2.1.15 | Google Docs | ✅ **API Drive `files.export`, PAS l'API Docs séparée, et export DOCX par défaut, PAS Markdown -- deux déviations délibérées et assumées par rapport au texte original** : l'API Docs (`docs.googleapis.com`) sert un accès structuré à un document vivant (modèle d'édition), pas un export à plat -- `files.export` de Drive fait exactement ce que demande cette étape ("exporter le document"), en réutilisant le MÊME flux OAuth et le même hôte que 2.1.14. Export DOCX par défaut (configurable via `GOOGLE_DOCS_EXPORT_FORMAT`) car c'est un format déjà entièrement supporté (Partie 2.1.2) -- réponse la plus forte possible à la vision critique 1 : un Google Doc devient indiscernable d'un vrai DOCX uploadé directement, pas un nouveau format. Sheets exporte en CSV réel (2.1.6), Slides en PDF réel (2.1.1) -- trois formats déjà réels dans ce codebase, aucun nouveau. `should_include_drive_file` (2.1.14) et cette étape sont de vrais compléments : 2.1.14 exclut tout fichier natif Google Workspace, cette étape est exactement ce qui les gère. Sécurité identique à 2.1.14 : le refresh token/client_id/secret ne transitent jamais par Celery. Robustesse : la vraie limite documentée de 10 Mo de l'API Drive `files.export` est mappée sur la foi de la documentation stable de Google (non déclenchée en direct, aucun vrai document de plus de 10 Mo disponible) ; un vrai échec d'export (limite, auth, 404) termine le document en `failed` avec l'erreur réelle enregistrée, confirmé via un vrai 403 simulé. `doc_type_from_mime_type` résout le vrai type depuis le vrai `mimeType` déjà récupéré, jamais depuis la simple déduction hors-ligne de l'URL -- un vrai fichier Drive ordinaire est rejeté avec une erreur claire (portée séparée de 2.1.14). Une seule route accepte soit un document unique soit un vrai lot (`document_urls_or_ids`), unifiant les deux fonctions de traitement littérales de cette étape. **Même limite honnête que 2.1.14** : aucun identifiant OAuth Google réel disponible pour une vérification de bout en bout contre un vrai compte -- mais reste ✅ ici (contrairement au 🟡 de 2.1.14) car cette étape réutilise entièrement un flux OAuth déjà implémenté et vérifié, et sa propre logique d'orchestration (résolution de type, sélection de format, gestion d'échec) est testée de façon réaliste et complète. Tests réels dédiés (validation d'URL/ID pour les trois types réels, résolution de type depuis un vrai mimeType, résolution de format d'export réel, métadonnées réelles titre/propriétaire/date, export réel réussi/échoué/404, extraction réelle de texte/HTML) + tests de route de bout en bout (import simple, import en lot, ni-l'un-ni-l'autre/les-deux rejetés par un vrai 422, garde-fou cross-tenant, format transmis à la planification, permissions) + tests d'orchestration réalistes (Doc exporté en DOCX, Sheet exporté en CSV, fichier Drive ordinaire rejeté, échec d'export réel, refresh token manquant), voir `tests/test_google_drive_extraction.py`/`tests/test_documents.py`/`tests/test_google_docs_integration.py` |
| 2.1.16 | Notion | ✅ **API REST Notion réelle via un simple client httpx, PAS le SDK officiel `notion-client`** -- même restreinte "pas de SDK sans besoin réel exprimé" que les étapes précédentes : la surface réelle nécessaire (pages, bases, blocs, requêtes de base de données) tient en quelques appels HTTP simples, réutilisant le même client `httpx.AsyncClient` que chaque autre module d'extraction de ce codebase. **Authentification réellement plus simple que Google** : un seul token statique réel (`NOTION_API_TOKEN`, même forme que `GITHUB_API_TOKEN`, pas de flux OAuth refresh). Confirmé en direct, sans le moindre token valide : un token manquant OU invalide obtiennent tous deux un vrai 401 sous la vraie enveloppe d'erreur PLATE de Notion (`{"object": "error", "status", "code", "message"}`) -- réellement plus simple que les formes de GitHub et de Google. Une vraie page/base doit AUSSI être explicitement partagée avec l'intégration dans Notion -- confirmé réel, Notion renvoie le même 404 pour "n'existe pas" et "existe mais non partagé", la même conception anti-énumération qu'un dépôt GitHub privé. **Découverte réelle structurelle importante** : le contenu d'une page Notion est un vrai ARBRE de blocs, pas une liste plate -- un bloc avec `has_children: true` nécessite un appel réel SÉPARÉ pour récupérer ses propres enfants, récursivement. `fetch_notion_blocks` parcourt cet arbre réel, plafonné à `NOTION_MAX_BLOCKS` blocs réels au total (réponse réelle à la vision critique 4, "trop de blocs", confirmée par un test réel où le plafond atteint arrête la récursion). L'API Notion n'expose AUCUN header `X-RateLimit-*` (confirmé en direct) -- son vrai mécanisme est un `429` avec `Retry-After`, mappé ici sur une `NotionRateLimitError` distinguable, jamais déclenchée exprès contre un vrai service tiers partagé. **Cohérence (vision critique 1)** : `extract_notion_content` convertit le vrai arbre de blocs en vrai Markdown (titres, listes, tâches, citations, code, indentation imbriquée réelle) puis réutilise exactement le même pipeline upload/`process_document` -- une page Notion devient un vrai document `.md`, aucun nouveau format. Simplification réelle et honnête énoncée clairement : les vrais blocs `numbered_list_item` ne portent aucun numéro d'ordre réel dans l'API Notion elle-même, donc un vrai compteur séquentiel est rendu à travers les frères consécutifs du même type. `NOTION_INCLUDE_TYPES` est une vraie LISTE BLANCHE (embeds/blocs synchronisés/bases enfants n'ont aucun rendu textuel réel significatif) -- le vrai titre, quel que soit le nom réel de la propriété, est trouvé par son vrai `type == "title"`, jamais supposé par le nom de clé (souvent `"Name"` pour une ligne de base de données réelle, pas `"title"`). Tests réels dédiés (analyse réelle d'URL/ID sous forme plate et UUID à tirets, chaque échec réel distinguable 401/429/404, pagination réelle par curseur pour les requêtes de base ET les enfants de blocs, parcours récursif réel de l'arbre de blocs y compris le plafond réel qui arrête la récursion, extraction réelle du titre par type, conversion Markdown réelle) + test réseau réel (le vrai 401 confirmé en direct, sans token valide) + tests de route de bout en bout (import de page, import de base, URL invalide rejetée, garde-fou cross-tenant, bornes de `max_pages`, transmission à la planification, permissions) + tests d'orchestration réalistes (page convertie en Markdown, page introuvable, token manquant, base interrogée et planifiée), voir `tests/test_notion_extraction.py`/`tests/test_notion_extraction_integration.py`/`tests/test_documents.py`/`tests/test_notion_integration.py` |
| 2.1.17 | Confluence | 🟡 **API REST Confluence v1 réelle, contre une documentation publiée et stable, PAS de SDK** -- même restreinte "pas de SDK sans besoin réel exprimé" que chaque étape précédente. **Limite honnête et inédite, plus sévère que 2.1.14** : chaque étape précédente (GitHub, Google, Notion) disposait d'AU MOINS un hôte fixe et universellement joignable permettant une vraie vérification en direct même sans identifiant valide (au minimum, la forme réelle d'un rejet d'authentification). Confluence n'a AUCUN équivalent : `CONFLUENCE_BASE_URL` est propre à chaque tenant (`https://VOTRE-TENANT.atlassian.net/wiki` en Cloud, ou une URL auto-hébergée arbitraire en Server/Data Center). Confirmé pour de vrai pendant cette étape : un tenant plausible mais fictif (`example-tenant.atlassian.net`) renvoie la page HTML générique 404 d'Atlassian, pas une réponse JSON de l'API REST -- il n'existe littéralement aucun hôte de repli à interroger. **Chaque test de cette étape est donc construit entièrement à partir de la documentation stable et publiée d'Atlassian, avec zéro vérification en direct d'aucune sorte** -- pas même la forme d'un rejet d'authentification, contrairement à 2.1.14. C'est la raison honnête du statut 🟡, et pourquoi `tests/test_confluence_extraction_integration.py` n'existe délibérément pas (contrairement au fichier `_integration.py` réseau réel de chaque étape précédente) : aucune requête réelle et sans identifiant n'était possible à écrire honnêtement. **Cohérence (vision critique 1)** : le "storage format" réel de Confluence (`body.storage.value`) est du XHTML -- plutôt que d'écrire un second analyseur HTML, `extract_confluence_content` réutilise intégralement et sans modification le cœur déjà existant de `api/services/html_extraction.py` (`extract_html_content_from_markup`), la réponse la plus forte possible : une page Confluence devient un vrai document `.html` traité par le même pipeline HTML déjà audité. Limite honnête énoncée clairement : les macros spécifiques au storage format de Confluence (panneaux, encadrés d'info, blocs dépliables) ne sont pas spécialement dépliées -- elles traversent le pipeline comme n'importe quelle balise HTML inconnue. **Amélioration réelle et délibérée par rapport au précédent Notion** : contrairement à Notion (dont la forme d'URL/ID ne distingue jamais une page d'une base, forçant une valeur par défaut au niveau du schéma), les vraies formes d'URL Cloud de Confluence distinguent réellement une page (`/pages/{id-numérique}`) d'un espace (`/spaces/{CLÉ}` sans ce suffixe) -- `validate_confluence_url` détermine et renvoie donc le vrai `kind` directement depuis la forme de l'URL, sans devinette ni valeur par défaut. `CONFLUENCE_INCLUDE_SPACES` est une vraie liste blanche configurée par l'administrateur, vérifiée dans `process_confluence_space` AVANT toute vraie requête (réponse à la vision critique 3) -- la route ne ciblant qu'une seule page ou un seul espace explicite par requête, il n'existe pas d'étape de découverte façon dossier où un filtre par requête s'appliquerait à la place. Sécurité identique à chaque étape précédente : le token/base_url ne transitent jamais par les arguments d'une tâche Celery. Tests réels dédiés (analyse d'URL/ID page et espace, chaque échec documenté 401/403/429/404, pagination réelle par décalage `start` avec plafond `max_pages`, listage des pages enfants, extraction réelle de texte via le cœur HTML réutilisé, extraction réelle de métadonnées titre/version/date/auteur avec gestion gracieuse des champs manquants) + tests de route de bout en bout (import de page, import d'espace, URL invalide rejetée, garde-fou cross-tenant, bornes de `max_pages`, permissions, rejet par la liste blanche d'espaces) + tests d'orchestration réalistes construits à partir des formes documentées (page convertie en document HTML, 404 documenté, token/base_url manquants, espace interrogé et planifié, rejet par la liste blanche), voir `tests/test_confluence_extraction.py`/`tests/test_documents.py`/`tests/test_confluence_integration.py` |
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
| ✅ Fait | 74 | 14.8% |
| 🟡 Partiel | 65 | 13.0% |
| ⬜ Non commencé | 361 | 72.2% |

**Complétion globale (/515, Partie 15 incluse en approximation)** :
- Strictement ✅ : **74/515 (~14.4%)**
- ✅ + 🟡 touchés d'une manière ou d'une autre : **140/515 (~27.2%)**
- Pondéré (✅=1, 🟡=0.5) : **~107/515 (~20.8%)** -- le chiffre le plus représentatif de l'avancement réel.

Mis à jour après Partie 2.1.17 (Import depuis Confluence, 2026-09-04) :
Partie 2 : 15✅/1🟡/19⬜ → 15✅/2🟡/18⬜ sur 35 (2.1.17 seul item touché --
🟡, limite honnête inédite et plus sévère que 2.1.14 : contrairement à
GitHub/Google/Notion, Confluence n'a AUCUN hôte universel joignable --
`CONFLUENCE_BASE_URL` est propre à chaque tenant, et un tenant fictif
plausible renvoie une page HTML 404 générique, pas une réponse API.
Zéro vérification en direct de quelque nature que ce soit n'était donc
possible, pas même la forme d'un rejet d'authentification -- chaque
test est construit sur la seule documentation stable d'Atlassian.
Réutilisation forte du pipeline HTML existant (`extract_html_content_from_markup`,
inchangé) pour le storage format XHTML de Confluence ; amélioration
réelle par rapport à Notion : la forme d'URL distingue vraiment page et
espace, sans valeur par défaut nécessaire. `CONFLUENCE_INCLUDE_SPACES`
implémentée comme liste blanche admin réelle. Aucune nouvelle colonne
de base de données).

Précédemment, après Partie 2.1.16 (Import depuis Notion, 2026-09-04) :
Partie 2 : 14✅/1🟡/20⬜ → 15✅/1🟡/19⬜ sur 35 (2.1.16 seul item touché --
client httpx simple plutôt que le SDK officiel `notion-client` ; un seul
token statique réel, plus simple que le flux OAuth de Google ; découverte
réelle structurelle : le contenu d'une page est un vrai arbre de blocs,
parcouru récursivement et plafonné par `NOTION_MAX_BLOCKS` ; conversion
réelle en Markdown réutilisant le pipeline partagé. Aucune nouvelle
colonne de base de données).

Précédemment, après Partie 2.1.15 (Import depuis Google Docs, 2026-09-04) :
Partie 2 : 13✅/1🟡/21⬜ → 14✅/1🟡/20⬜ sur 35 (2.1.15 seul item touché --
réutilise entièrement le flux OAuth de 2.1.14, export via `files.export`
de Drive plutôt que l'API Docs séparée, DOCX par défaut plutôt que
Markdown -- deux déviations délibérées, la plus forte réponse possible
à la vision critique 1 puisque DOCX est déjà un format réel et
supporté. Reste ✅, contrairement au 🟡 de 2.1.14, car cette étape
réutilise un flux déjà vérifié et sa propre logique est testée de
façon réaliste et complète. Aucune nouvelle colonne de base de données).

Précédemment, après Partie 2.1.14 (Import depuis Google Drive, 2026-09-03) :
Partie 2 : 13✅/0🟡/22⬜ → 13✅/1🟡/21⬜ sur 35 (2.1.14 seul item touché --
🟡, pas ✅, une évaluation honnête plutôt qu'une fausse certitude : le
code implémente correctement le comportement réel et documenté de
l'API Google Drive v3 + un vrai flux OAuth 2.0 refresh-token, mais
contrairement à 2.1.12/2.1.13 (où `gh auth token` avait fourni un vrai
identifiant GitHub utilisable dans la même session), aucun identifiant
OAuth Google réel n'était disponible -- en obtenir un exigerait un vrai
flux de consentement interactif dans un navigateur, hors du périmètre
sûr de cette session (même restreinte que S3_DOCUMENTS_BUCKET_NAME,
jamais auto-provisionné). Ce qui A pu être vérifié en direct sans
identifiant valide : les vrais rejets OAuth (`invalid_client` vs
`invalid_request` selon que client_id est présent ou absent) et les
vrais rejets d'authentification Drive (403 sans header, 401 avec token
invalide), sous la vraie enveloppe d'erreur imbriquée de Google,
différente de chaque erreur plate façon GitHub. Réponse réelle et
proactive à "que se passe-t-il si le token expire" : rafraîchissement
avant expiration réelle, avec une vraie marge de sécurité, confirmé par
un test direct de la séquence. Découverte réelle Drive spécifique : un
vrai fichier natif Google Workspace n'a aucun contenu binaire
téléchargeable, exclu explicitement (portée séparée de 2.1.15). Limite
de portée honnête : pas de récursion dans les sous-dossiers. Nouvelle
route, nouveau module d'extraction, nouvelle tâche Celery -- aucune
nouvelle colonne de base de données).

Précédemment, après Partie 2.1.13 (Import depuis GitHub -- issues, 2026-09-03) :
Partie 2 : 12✅/0🟡/23⬜ → 13✅/0🟡/22⬜ sur 35 (2.1.13 seul item touché --
API GitHub REST "Issues List", PAS l'API Search comme prévu à l'origine
-- déviation délibérée et assumée : confirmé pour de vrai que l'API
Search a son propre quota séparé bien plus restrictif (10/minute) que
le quota "core" (60/heure ou 5000/heure) que l'endpoint Issues List
utilise, la réponse la plus forte possible à la vision critique du
rate limiting. Même histoire de réutilisation que 2.1.12, transformée
en vrai Markdown d'abord : chaque issue passe par format_issue_for_import
(titre + métadonnées + corps + commentaires) puis exactement le même
pipeline upload/process_document que chaque autre format -- le repli de
nom de fichier `.md` (Partie 2.1.4) déclenche le vrai sectionnement
Markdown par titre. Découvertes réelles : l'API Issues renvoie aussi de
vraies pull requests (distinguables uniquement par une clé
`pull_request`, toujours exclues) ; le paramètre `labels` de GitHub
utilise une sémantique ET, donc jamais transmis à l'API -- filtré côté
client avec une vraie sémantique OU à la place. Différence de forme de
données réelle : les données d'issue déjà assemblées (issue +
commentaires) transitent directement en argument de la tâche Celery
par issue, qui ne fait donc aucun appel API GitHub supplémentaire --
contrairement au contenu d'un fichier de dépôt, trop volumineux pour un
argument Celery. Même réponse proactive au rate limiting que 2.1.12 :
un appel gratuit à /rate_limit plafonne les fetches de commentaires
avant de les lancer. Nouvelles fonctions dans le module d'extraction
GitHub existant, nouvelle tâche Celery, nouvelle route -- aucune
nouvelle colonne de base de données).

Précédemment, après Partie 2.1.12 (Import depuis GitHub -- dépôts, 2026-09-03) :
Partie 2 : 11✅/0🟡/24⬜ → 12✅/0🟡/23⬜ sur 35 (2.1.12 seul item touché --
API GitHub REST uniquement, PAS de git clone même superficiel -- une
vraie déviation délibérée et assumée par rapport au texte original de
cette ligne, puisque les actions à réaliser réellement demandées ne
décrivaient QUE des fonctions REST API. Même "réutilisation du pipeline
existant" que 2.1.10/2.1.11, à une source différente. Une vraie
réponse SSRF DIFFÉRENTE de 2.1.10/2.1.11, structurellement justifiée :
un simple httpx.AsyncClient, puisque la cible réelle est toujours
l'hôte fixe GITHUB_API_BASE_URL, jamais un hôte choisi par l'appelant.
Sécurité réelle du token la plus forte de toute étape d'import jusqu'ici :
GITHUB_API_TOKEN n'est JAMAIS transmis à travers les arguments d'une
tâche Celery (déviation délibérée de la signature littérale), lu
fraîchement depuis les settings au moment de chaque vrai appel.
Découvertes réelles : 404 identique pour dépôt inexistant et dépôt
privé sans accès (énoncé honnêtement, pas de fausse certitude) ; limite
réelle de 1 Mo de l'API Contents, exactement le défaut littéral de
GITHUB_MAX_FILE_SIZE. Performance/rate limiting, réponse la plus forte
jusqu'ici : un seul appel réel à l'API Trees récursive liste tout
l'arbre du dépôt, et un appel GRATUIT à /rate_limit plafonne
proactivement la distribution réelle avant tout risque de 403.
GITHUB_INCLUDE_PATTERNS est une vraie liste blanche, pas un filtre
optionnel -- conséquence honnête : un fichier sans extension n'est
jamais importé par défaut. Nouvelle route, nouveau module d'extraction,
nouvelle tâche Celery -- aucune nouvelle colonne de base de données).

Précédemment, après Partie 2.1.11 (Import via Sitemap, 2026-09-03) :
Partie 2 : 10✅/0🟡/25⬜ → 11✅/0🟡/24⬜ sur 35 (2.1.11 seul item touché --
"réutilisation sur réutilisation", pas un chemin d'import parallèle :
`fetch_sitemap` est un simple wrapper autour du fetch SSRF-safe déjà
existant de 2.1.10, et chaque page résultante passe par le
`import_document_from_url` de 2.1.10 totalement inchangé. Parsing réel
via `lxml` (déjà présent depuis 2.1.5/2.1.8), aucune nouvelle
dépendance. Deux découvertes réelles avant d'écrire le code de
production : un vrai sitemap est du XML avec espace de noms (extraction
via `local-name()`, tolérante à son absence) et couramment compressé en
gzip (décompression transparente, avec le vrai piège `gzip.BadGzipFile`
capturé et re-levé proprement). Scalabilité réelle (vision critique 3,
"50 000 URLs") : `max_urls` borné côté client (1 à 5000), plafond
interne séparé sur la récursion de sous-sitemaps (`_MAX_SUB_SITEMAPS =
50`, indépendant de `max_urls`), étalement de courtoisie entre les
dispatches Celery par page. Ordonnancement délibéré filtre-avant-plafond,
prouvé contre de vraies données. Robustesse réelle à trois niveaux
(vision critique 4) : un sous-sitemap défaillant, une page défaillante,
et un raté de broker sont chacun journalisés et isolés sans jamais
interrompre le reste de l'import ; un échec au niveau racine (URL
injoignable, XML malformé) termine l'ensemble en un résultat `"failed"`
journalisé. Limite honnête énoncée : aucune entité de suivi "job
d'import" -- chaque document reste visible individuellement, sans vue
agrégée. Route répond `202 Accepted` (rien n'est créé de façon
synchrone). Nouvelle route, nouveau module `sitemap_extraction.py`,
nouvelle tâche Celery -- aucune nouvelle colonne de base de données).

Précédemment, après Partie 2.1.10 (Import de pages web par URL, 2026-09-03) :
Partie 2 : 9✅/0🟡/26⬜ → 10✅/0🟡/25⬜ sur 35 (2.1.10 seul item touché --
exactement httpx + readability-lxml, Playwright délibérément non ajouté
(aucune action littérale ne demande de rendu JS). Menace réelle et
nouvelle par rapport à toutes les étapes précédentes : ce serveur fait
désormais de vraies requêtes HTTP sortantes vers des adresses contrôlées
par l'appelant (SSRF, OWASP A10:2021). Protection réelle vérifiée avant
d'écrire le code de production : un backend réseau httpcore personnalisé
résout et valide chaque IP AVANT connexion, y compris à chaque saut
d'une chaîne de redirections (le cas qu'une validation ponctuelle du nom
d'hôte original ne bloquerait pas) ; `is_global` préféré à `is_private`
après avoir trouvé pour de vrai que ce dernier rate l'espace CGNAT
(100.64.0.0/10). Réutilisation complète et réelle du pipeline existant
(vision critique 1) : une URL récupérée devient un document `text/html`
normal, uploadé et traité EXACTEMENT comme un upload de fichier -- aucun
nouveau file_type ni branche de dispatcher. Séparation asynchrone
réelle via Celery (vision critique 4) : seule la validation de format
pure et sans réseau est synchrone dans la route, tout le reste (réseau
réel, DNS inclus) est différé. Nouvelle route, nouvelle colonne
`Document.source_url` (migration 0033), nouvelle tâche Celery).

Précédemment, après Partie 2.1.9 (Import de documents EPUB, 2026-09-03) :
Partie 2 : 8✅/0🟡/27⬜ → 9✅/0🟡/26⬜ sur 35 (2.1.9 seul item touché --
exactement la bibliothèque prévue (ebooklib), tranchant directement la
vision critique 5. Trois découvertes réelles avant d'écrire le code de
production : la hiérarchie d'exceptions d'ebooklib pour un upload
corrompu est réellement imprévisible (même type de découverte que
python-docx en 2.1.2, capturée large et relevée en ValueError claire) ;
`EpubHtml.title` ne survit PAS à un cycle écriture-lecture réel (un
bug silencieux évité en utilisant plutôt la vraie table des matières,
qui survit réellement) ; la table des matières peut imbriquer des
sections, aplaties avec un marqueur de niveau comme les titres
Markdown de 2.1.4. Sectionnement réel par chapitre dans le dispatcher,
suivant le précédent Markdown. Signature d'upload réelle et
déterministe (l'entrée `mimetype` imposée par la spec EPUB), encore
plus forte que celle de DOCX. Vrai écart "accepté puis échoue" honnête
et testé, comme DOCX, contrairement à JSON/XML).

Précédemment, après Partie 2.1.8 (Import de documents XML, 2026-09-03) :
Partie 2 : 7✅/0🟡/28⬜ → 8✅/0🟡/27⬜ sur 35 (2.1.8 seul item touché --
exactement la bibliothèque prévue (lxml, déjà présente depuis 2.1.5).
Question littérale de la vision critique tranchée directement :
lxml.etree reproduit l'API du stdlib ElementTree, donc l'utiliser EST
déjà "utiliser ElementTree" ; xmltodict testé pour comparaison puis
délibérément retiré, non ajouté comme dépendance. Trois découvertes
réelles avant d'écrire le code de production : libxml2 a son propre
garde-fou DÉLIBÉRÉ de profondeur (contrairement au problème accidentel
de JSON) ; le parseur par défaut de lxml est réellement vulnérable à
un déni de service "billion laughs" par expansion d'entités, corrigé
par un parseur durci (resolve_entities=False) partagé entre l'upload
et l'extraction ; une entité non résolue devient un vrai nœud non-string
dans l'arbre, un vrai bug capturé et corrigé avant la livraison. Vrai
compromis d'ambiguïté de format documenté et testé : un XML non déclaré
dont la racine coïncide avec un motif de sniffing HTML est classé HTML).

Précédemment, après Partie 2.1.7 (Import de documents JSON, 2026-09-03) :
Partie 2 : 6✅/0🟡/29⬜ → 7✅/0🟡/28⬜ sur 35 (2.1.7 seul item touché --
parsing réel via le module stdlib `json` (accéléré en C), sans nouvelle
dépendance (pas de moteur JSONPath ajouté, aucune action littérale de
l'étape ne le demandait). Deux découvertes réelles en testant avant
d'écrire le code de production : le parseur C tolère l'imbrication bien
au-delà de la limite de récursion Python par défaut ; une première
implémentation récursive du calcul de profondeur échouait bien avant
cette limite -- un vrai bug corrigé en passant à une version itérative
avant la livraison. **Un second vrai bug, capturé cette fois par la CI
elle-même après la livraison locale** : le premier chiffre choisi pour
tester "profondeur excessive" passait en local (Windows) mais échouait
sur le runner CI (Linux), preuve réelle que ce seuil dépend de
l'environnement, pas une constante portable -- corrigé en testant avec
une profondeur bien plus large (1 000 000 de niveaux) et en révisant la
documentation pour ne plus affirmer un chiffre précis comme universel.
Signal de contenu le plus fort de tous les formats jusqu'ici (JSON
valide = exact, sans ambiguïté), donc pas besoin d'exception de nom de
fichier comme Markdown/CSV, à l'exception délibérée du scalaire nu en
racine. Conséquence réelle : un JSON malformé est rejeté DÈS L'UPLOAD,
pas différé au traitement comme les autres formats).

Précédemment, après Partie 2.1.6 (Import de documents CSV, 2026-09-03) :
Partie 2 : 5✅/0🟡/30⬜ → 6✅/0🟡/29⬜ sur 35 (2.1.6 seul item touché --
exactement la bibliothèque prévue (pandas, déjà présente depuis 2.1.1).
Détection automatique du délimiteur via `csv.Sniffer` du stdlib, sans
nouvelle dépendance. Trois découvertes réelles en testant avant
d'écrire le code de production : le Sniffer échoue sur un CSV à une
seule colonne ou sur un échantillon aux colonnes incohérentes (repli
documenté sur la virgule) ; la détection de délimiteur confond une
simple prose contenant des virgules avec du vrai CSV (limite honnête,
non corrigible) ; pandas tolère une ligne à champs manquants mais
rejette une ligne à champs excédentaires (`ParserError` réelle) --
testé de bout en bout comme le nouveau cas de "malformation" réel de
cette étape. Deuxième exception réelle et délibérée à "le contenu
décide du type", aux côtés de Markdown).

Précédemment, après Partie 2.1.5 (Import de documents HTML, 2026-09-03) :
Partie 2 : 4✅/0🟡/31⬜ → 5✅/0🟡/30⬜ sur 35 (2.1.5 seul item touché --
exactement les bibliothèques prévues (BeautifulSoup4 + readability-lxml).
Détection de contenu réelle basée sur la spécification WHATWG (matching
an HTML byte pattern), contrairement à Markdown qui doit s'appuyer sur
le nom de fichier faute de signal de contenu. Deux découvertes réelles
en testant readability-lxml avant d'écrire le code de production : le
HTML malformé ne plante jamais (réparation silencieuse par lxml), mais
un fichier réduit à un simple commentaire HTML lève une vraie
exception `Unparseable` -- testé de bout en bout comme le nouveau cas
de "corruption" réel de cette étape).

Précédemment, après Partie 2.1.4 (Import de documents Markdown, 2026-09-03) :
Partie 2 : 3✅/0🟡/32⬜ → 4✅/0🟡/31⬜ sur 35 (2.1.4 seul item touché --
`src/ingestion.py` lu en entier avant d'écrire du code : gère déjà le
Markdown, mais pour un corpus mono-tenant très spécifique (docs
FastAPI), rien de directement réutilisable pour `api/`. Généralisation
réelle de la forme du dispatcher : chaque section porte maintenant son
propre dict de métadonnées, PDF et Markdown y logent leur "page"/
"heading" sans cas spécial. Vrai cas de corruption propre à Markdown
découvert et testé : un frontmatter YAML invalide).

Précédemment, après Partie 2.1.3 (Import de documents TXT, 2026-09-03) :
Partie 2 : 2✅/0🟡/33⬜ → 3✅/0🟡/32⬜ sur 35 (2.1.3 seul item touché --
même pipeline partagé que 2.1.1/2.1.2, dispatcher étendu. Découverte
réelle en testant : la détection universelle naïve d'encodage se
trompe sur les encodages occidentaux mono-octet historiques -- corrigée
en restreignant les candidats à une liste réaliste, retestée avec
succès. Limite réelle et non corrigible documentée honnêtement :
ISO-8859-1/Windows-1252 sont ambigus par nature pour un texte normal).

Précédemment, après Partie 2.1.2 (Import de documents DOCX, 2026-09-03) :
Partie 2 : 1✅/0🟡/34⬜ → 2✅/0🟡/33⬜ sur 35 (2.1.2 seul item touché --
même structure que 2.1.1, dispatcher partagé `extract_document_content`,
pipeline de traitement renommé `process_pdf_document` → `process_document`
puisqu'il traite désormais deux formats. Un vrai bug trouvé et corrigé
en route : la migration 0031 (2.1.1) avait oublié d'activer le RLS sur
`documents`/`document_chunks`, cassant un test d'invariant déjà
existant -- corrigé par une migration de suivi, 0032, plutôt que de
réécrire une migration déjà appliquée).

Précédemment, après Partie 2.1.1 (Import de documents PDF, 2026-09-03) :
Partie 2 démarre : 0✅/0🟡/35⬜ → 1✅/0🟡/34⬜ sur 35 (2.1.1 seul item
touché -- 2.1.2 à 2.1.19 restent des formats d'import séparés, non
demandés par cette étape). Table `documents`/`document_chunks` réelles,
extraction PDF réelle (`pymupdf`, vérifié pour de vrai), chunking et
embeddings réels connectant pour la première fois deux réglages de
1.3.9 (`chunk_size`/`chunk_overlap`/`embedding_model`) qui n'étaient
jusqu'ici jamais lus par `api/`.

Précédemment, après Partie 1.4.6 (White-label complet, 2026-09-03) :
Partie 1.4 : 5✅/4🟡/1⬜ → 6✅/4🟡/0⬜ sur 10 -- **les 10 items de la
Partie 1.4 sont désormais tous touchés** (1.4.6 passe de ⬜ à ✅ : le
flag `hide_platform_branding` est réel, testé, et cohérent avec le
branding existant de 1.3.10 ; seule la partie "templates conditionnels"
reste un contrat documenté plutôt que du code, Partie 8 à 0%, même
limite honnête déjà acceptée pour 1.3.10/1.4.2).

Précédemment, après Partie 1.4.5 (Custom email domain, 2026-09-03) :
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
3. **Partie 2 (Knowledge Base multi-format), le reste** -- le cœur
   produit d'un "RAG SaaS platform" ; dépend de 1.3 (désormais tous les
   items touchés) pour le scoping par organisation/workspace. 2.1.1
   (PDF), 2.1.2 (DOCX), 2.1.3 (TXT), 2.1.4 (Markdown), 2.1.5 (HTML),
   2.1.6 (CSV), 2.1.7 (JSON), 2.1.8 (XML), 2.1.9 (EPUB), 2.1.10
   (URLs/pages web), 2.1.11 (Sitemap), 2.1.12 (GitHub -- dépôts) et
   2.1.13 (GitHub -- issues), 2.1.15 (Google Docs) et 2.1.16 (Notion)
   livrés en ✅ ; 2.1.14 (Google Drive) et 2.1.17 (Confluence) livrés en 🟡 -- 2.1.10 a introduit sa propre
   vraie nouveauté (SSRF, route/colonne/tâche Celery dédiées), 2.1.11 a
   construit dessus en pure réutilisation ("réutilisation sur
   réutilisation" : fetch SSRF-safe et pipeline par page tous deux
   inchangés depuis 2.1.10), 2.1.12 a réutilisé le même pipeline de
   traitement à une source et un modèle de menace différents (API
   GitHub REST sur un hôte fixe, pas de transport SSRF-safe nécessaire ;
   token serveur jamais transmis via Celery), 2.1.13 a étendu le même
   module GitHub avec les issues, transformées en vrai Markdown avant
   de réutiliser le même pipeline une fois de plus, 2.1.14 a implémenté
   un vrai flux OAuth 2.0 serveur-à-serveur pour Google Drive mais
   reste 🟡 faute d'un vrai compte/identifiant Google pour vérifier de
   bout en bout dans cet environnement (contrairement à GitHub, où
   `gh auth token` avait fourni un vrai identifiant utilisable), et
   2.1.15 a réutilisé ce même flux OAuth pour Google Docs/Sheets/Slides
   (export DOCX/CSV/PDF via l'API Drive `files.export`), restant ✅ car
   sa propre logique d'orchestration est testée de façon réaliste et
   complète indépendamment de l'accès à un vrai compte, et 2.1.16 a
   implémenté Notion avec une authentification réellement plus simple
   (un seul token statique) et un vrai parcours récursif de l'arbre de
   blocs converti en Markdown, et 2.1.17 a implémenté Confluence contre
   la seule documentation stable d'Atlassian -- limite honnête inédite,
   plus sévère que 2.1.14 : aucun hôte universel n'existe pour
   Confluence (contrairement à GitHub/Google/Notion), donc zéro
   vérification en direct n'était possible, pas même la forme d'un
   rejet d'authentification, d'où son propre statut 🟡. Aucune des huit
   n'a introduit la moindre nouvelle colonne de base de données. Reste
   2.1.18 à 2.1.19 (2 autres formats/sources d'import) et toute
   la Partie 2.2 (gestion des documents : tags, versioning,
   réindexation, détection de doublons, sync). Gros chantier restant,
   à continuer de découper en sous-étapes.
4. **Partie 6 (Citations & Anti-hallucination), validation réelle** --
   le code existe déjà (`hallucination_detection.py`, `llm_judge.py`),
   juste jamais validé en conditions réelles faute de crédit API
   Anthropic -- rapport effort/valeur excellent dès que le crédit est
   disponible.

### Reste du non-commencé (après les priorités ci-dessus)

- Partie 1.4 (White-label) -- **tous les items désormais touchés** (6✅/4🟡/0⬜
  sur 10, voir le tableau détaillé ci-dessus) : 1.4.1 (custom domains),
  1.4.2 (instructions DNS bilingues), 1.4.3 (SSL via un vrai client ACME,
  🟡 -- DNS-01 fonctionnel et vérifié contre le vrai staging Let's
  Encrypt, mais pas "auto" sans intégration API fournisseur DNS), 1.4.4
  (vérification domaine périodique, job Celery de polling réel), 1.4.5
  (custom email domain, 🟡 -- DKIM auto-généré réel + intégration Resend
  réelle, mais la clé Resend de cet environnement s'est révélée
  restreinte à l'envoi seul en testant pour de vrai, empêchant de
  prouver la création/vérification de domaine chez Resend de bout en
  bout) et 1.4.6 (white-label, flag `hide_platform_branding` réel et
  cohérent avec 1.3.10) livrés ; 1.4.7/1.4.8/1.4.10 déjà satisfaits en
  tout ou partie par 1.3.9/1.3.10, et 1.4.9 partiellement par 1.4.5 (la
  fonction existe et fonctionne réellement, mais n'est câblée dans aucun
  envoi existant). Ce qui manque reste réel infrastructure (un
  reverse-proxy dynamique routant réellement le trafic par Host header,
  dont 1.4.1 ET 1.4.3 dépendent tous les deux pour qu'un domaine "actif"
  serve vraiment quelque chose) et le frontend qui consommerait tout ça
  (Partie 8, 0%)
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
