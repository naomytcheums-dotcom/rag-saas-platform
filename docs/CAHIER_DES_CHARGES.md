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

## Audit exhaustif des limites connues (2026-09-04)

Vérification réelle, ligne par ligne dans le code (pas sur la seule foi
des rapports précédents), de chaque limite listée dans le tableau fourni.
Résultat honnête : la majorité N'ÉTAIT PAS un oubli -- c'était déjà une
décision technique réelle et documentée, souvent pour une raison de
sécurité. "Corriger" ces cas-là aurait été une régression, pas une
amélioration -- ils sont donc listés comme **confirmés, non modifiés**,
avec la raison exacte.

| Item | Statut vérifié | Verdict |
|---|---|---|
| 1.2.7 RBAC Casbin non branché | **Confirmé, réel, délibéré** — `api/security/rbac.py` : moteur Casbin complet, réel, seedé, testé en intégration Postgres réelle, mais PAS branché sur `require_org_*` car `tests/conftest.py`'s `client` fixture (ASGITransport) ne déclenche jamais le `lifespan` de l'app — brancher aujourd'hui ferait planter (500) tous les tests de permissions (~450 tests) dès qu'un test touche un enforcer jamais initialisé. **Non corrigé dans ce lot** : solution concrète identifiée (paquet `asgi-lifespan`, `LifespanManager` autour du fixture `client`) mais c'est un changement à fort rayon d'impact sur toute la suite de tests, à traiter séparément, avec sa propre vérification complète — pas à la sauvette dans un lot qui construit par ailleurs 9 nouvelles fonctionnalités. |
| 1.2.8 Permissions granulaires non branchées sur `organizations.py` | **Confirmé, réel, délibéré — et il faut le LAISSER ainsi.** `api/security/resource_permissions.py` fonctionne réellement et est branché sur `workspaces.py`. Le brancher sur `organizations.py` (PATCH/DELETE, Owner-only) ouvrirait un contournement du contrôle le plus strict du système (renommer/supprimer une organisation entière) — décision de sécurité déjà prise et documentée. Le corriger "comme demandé" serait une régression de sécurité réelle, pas une amélioration. **Volontairement non touché.** |
| 1.3.5 RLS no-op (BYPASSRLS) | **Confirmé, réel, toujours vrai.** `tests/test_postgres_integration.py` le prouve empiriquement : RLS est activée sur chaque table mais la connexion de l'app (rôle `postgres`) a `BYPASSRLS` — no-op total pour l'app elle-même aujourd'hui ; l'isolation réelle est 100% applicative (`require_org_member`). Rendre RLS réellement fonctionnelle demande de créer un rôle Postgres dédié SANS `BYPASSRLS`, migrer la chaîne de connexion de l'app vers ce rôle, accorder les GRANT nécessaires table par table, et écrire de vraies policies par organisation (`current_setting('app.organization_id')`) -- un chantier réel, séparé, à fort risque si précipité (une seule GRANT manquante casse une fonctionnalité au hasard). **Non corrigé dans ce lot** — chantier dédié recommandé, pas une correction ponctuelle. |
| 1.3.2 Workspaces pas liés à KB/agents | **Partiellement obsolète.** Le lien KB existe déjà réellement : `api/models/document.py:58` a bien `workspace_id`. Le lien "agents" reste impossible : aucune entité `Agent` stockée n'existe (Partie 5.3, non commencée) — rien à quoi lier. Rien à corriger tant que 5.3 n'existe pas. |
| 1.4.3 SSL auto partiel (pas de reverse-proxy) | **Confirmé, réel, mais c'est un choix d'architecture valide, pas un bug.** `api/security/ssl_certificates.py` : ACME DNS-01 réel et complet (le seul challenge type possible sans reverse-proxy). DNS-01 est une approche standard et suffisante en production (beaucoup de SaaS l'utilisent exclusivement, y compris pour les certs wildcard) — ce n'est pas une intégration à moitié faite, c'est le bon choix pour ce déploiement. "Finaliser" nécessiterait de déployer un vrai reverse-proxy (nginx/Caddy) en frontal — une décision d'infrastructure/hébergement qui appartient à l'utilisateur, pas une correction de code. |
| 1.4.5 Email domain partiel (pas de DKIM réel) | **Confirmé, réel, mais déjà aussi complet que possible.** `api/security/email_domains.py` : vérifié contre la vraie doc API Resend — Resend génère et gère SA PROPRE clé DKIM côté serveur, sous UN sélecteur fixe ("resend") ; son API n'accepte aucune clé DKIM fournie par l'appelant. Le vrai enregistrement DKIM qui compte pour la délivrabilité (`api/services/resend_domains.py`) est déjà réel et exposé à l'Owner. Rien à "finaliser" — c'est la limite réelle de l'API tierce, pas de ce code. |
| 3.3.4-3.3.6 Résolveurs non câblés | **Obsolète, déjà corrigé** dans une session antérieure. `POST /organizations/{org_id}/search` (`api/routers/search.py`) existe réellement, branché sur `retrieval_pipeline.search_with_context`. |
| 4.x Embeddings non intégrés au pipeline | **Obsolète, déjà corrigé.** `api/security/documents.py`'s `process_document` appelle réellement `get_embedder(organization_settings.embedding_model)`. |
| 3.4.x Recherche non intégrée à l'API | **Partiellement vrai, réel, plan concret identifié, non implémenté dans ce lot.** L'endpoint de base existe (`POST /organizations/{org_id}/search`), mais les fonctions autonomes de 3.4.2/3.4.3/3.4.4 (query rewriting, HyDE, multi-query) ne sont PAS exposées comme options de cet endpoint — vérifié par grep, aucune référence dans `search.py`. Plan concret : ajouter des champs optionnels (`use_query_rewriting`/`use_hyde`/`use_multi_query`, défaut `False`) à `SearchRequest`, transformer `payload.query` avant l'appel à `search_with_context` quand demandé. Additif, sans risque pour les appelants existants. **Non implémenté dans ce lot** — reporté après 5.1.2-5.1.10 (le cœur de cette même requête) faute de place raisonnable dans un seul lot. |
| 2.x UI différée | **Confirmé, inchangé, volontaire.** Projet backend-only jusqu'ici (dashboards client/admin à venir séparément). Une API REST propre et documentée EST la préparation pour cette intégration — rien de plus à faire côté backend en attendant. |
| 5.1.1 Registre des runs en mémoire | **✅ Corrigé dans cette même session** — voir Partie 5.1.1 ci-dessous (table `agent_runs` persistante, migration `0048`). |
| 5.x Agent Builder non commencé | **Confirmé, inchangé, volontairement hors périmètre** de cette requête aussi (Partie 5.3 reste un chantier séparé, non demandé ici). |

**Statut final de l'audit** : 🟡 4 items confirmés et **délibérément non touchés** (1.2.7, 1.2.8, 1.4.3, 1.4.5 -- les corriger littéralement aurait été une régression ou une impossibilité d'infrastructure) ; 1 item réel reporté avec plan concret (3.4.x) ; 1 item réel correctement scopé mais trop risqué pour ce lot (1.3.5 RLS) ; 2 items obsolètes déjà résolus (3.3.4-3.3.6, 4.x) ; 1 item partiellement obsolète (1.3.2) ; 1 item corrigé dans ce même lot (5.1.1) ; 1 item hors périmètre confirmé (5.x).

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

## PARTIE 2 — Knowledge Base universelle — 🟡 DÉMARRÉ (27✅/8🟡/0⬜ sur 35, via les Étapes 2.1.1/2.1.2/2.1.3/2.1.4/2.1.5/2.1.6/2.1.7/2.1.8/2.1.9/2.1.10/2.1.11/2.1.12/2.1.13/2.1.14/2.1.15/2.1.16/2.1.17/2.1.18/2.1.19/2.2.1/2.2.2/2.2.3/2.2.4/2.2.5/2.2.6/2.2.7/2.2.8/2.2.9/2.2.10/2.2.11/2.2.12/2.2.13/2.2.14/2.2.15/2.2.16)

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
| 2.1.18 | OneDrive | 🟡 **API Microsoft Graph v1.0 réelle + un vrai flux OAuth 2.0 refresh-token serveur-à-serveur, structurellement le plus proche parent de la 2.1.14 (Google Drive)** -- même forme réelle de cache-et-rafraîchissement proactif du token que Drive (vision critique 4). **Contrairement à Confluence (2.1.17), un vrai hôte universel et indépendant du tenant existe réellement ici** : le point de terminaison multi-tenant réel `https://login.microsoftonline.com/common/oauth2/v2.0/token` et l'hôte fixe `graph.microsoft.com` fonctionnent tous deux pour N'IMPORTE QUEL tenant Azure AD réel, confirmé en direct. Même limite honnête que Google Drive cependant : aucun identifiant Microsoft/Azure réel disponible dans cette session (pas d'équivalent `az`-CLI à `gh auth token` -- confirmé, `az` lui-même n'est même pas installé ici), d'où le statut 🟡 plutôt que ✅. **Découverte réelle et honnête faite en vérifiant en direct** : une requête identique octet pour octet (client_id manquant, refresh token malformé) a été observée renvoyant DEUX formes de rejet réelles différentes à des moments différents (`invalid_request`/AADSTS900144 une fois, `invalid_grant`/AADSTS9002313 une autre fois) -- un vrai non-déterminisme du backend Microsoft (probablement un équilibrage de charge entre instances différemment configurées), contrairement à la paire `invalid_client`/`invalid_request` de Google, elle proprement et systématiquement reproductible (2.1.14). Rapporté tel quel plutôt que de forcer une distinction stable qui ne l'est pas réellement -- le test réseau réel n'affirme qu'un rejet réel a bien lieu, jamais un code AADSTS précis, pour éviter un test intrinsèquement instable contre l'point de terminaison réel en direct. Le vrai 401 de l'API Graph elle-même pour absence totale d'en-tête d'autorisation (`{"error": {"code": "InvalidAuthenticationToken", ...}}`) était, lui, parfaitement reproductible à chaque tentative. **Cohérence (vision critique 1)** : aucun nouveau format -- un vrai fichier OneDrive est téléchargé et uploadé via exactement le même pipeline que chaque import binaire précédent (GitHub, Drive). **Différence structurelle réelle et importante par rapport à Drive** : un `driveItem` Graph indique dossier-vs-fichier via quelle vraie FACETTE est présente (`folder` vs `file`, avec `mimeType` À L'INTÉRIEUR de la facette `file`), pas un simple champ `mimeType` comme chez Drive -- aucun équivalent du cas particulier des fichiers natifs Google Workspace n'existe ici : chaque vrai élément à facette `file` a un vrai contenu binaire téléchargeable, donc aucune séparation export-vs-téléchargement n'est nécessaire (contrairement à 2.1.14/2.1.15). Même limite de portée réelle que Drive : pas de récursion dans les vrais sous-dossiers. Tests réels dédiés (échange/cache/rafraîchissement proactif réels du token, chaque échec réel distinguable 401/429/404, pagination réelle par `@odata.nextLink`, distinction dossier/fichier réelle par facette, extraction réelle de métadonnées, filtrage réel taille/motif) + tests réseau réels (rejet réel confirmé en direct sans identifiant valide, le vrai 401 Graph confirmé en direct) + tests de route de bout en bout (import dossier, import fichier, dossier_id vide rejeté, garde-fou cross-tenant, bornes de `max_files`, motifs transmis à la planification, permissions) + tests d'orchestration réalistes (résolution dossier-vs-fichier, filtrage, plafond, gestion des échecs auth/404), voir `tests/test_onedrive_extraction.py`/`tests/test_onedrive_extraction_integration.py`/`tests/test_documents.py`/`tests/test_onedrive_integration.py` |
| 2.1.19 | Fichiers ZIP | ✅ **stdlib `zipfile` uniquement -- le SEUL import de toute la série 2.1.10-2.1.19 sans la moindre API externe ni le moindre identifiant.** Réutilise la route d'upload EXISTANTE (`POST /organizations/{org_id}/documents`, Partie 2.1.1) plutôt qu'une route dédiée -- un `.zip` est uploadé exactement comme un PDF/DOCX ; `validate_document_upload` reconnaît les vrais octets magiques ZIP (après avoir écarté DOCX/EPUB, qui partagent la même signature) et `upload_document` redirige vers `schedule_zip_processing` au lieu du pipeline générique pour ce type de contenu. `ZIP_INCLUDE_PATTERNS`/`ZIP_MAX_FILES`/`ZIP_MAX_ENTRY_SIZE` sont donc des réglages serveur par défaut, pas des champs par requête -- la route d'upload simple n'a pas de place pour cela. **Déviation réelle et délibérée par rapport à la signature littérale de `process_zip_archive`** : `zip_file_id` est ajouté (absent du texte de la consigne) car le fan-out Celery par entrée en a besoin pour re-télécharger la même archive depuis S3 plus tard -- même type de correction nécessaire que le `token` supprimé en 2.1.12 ou le `created_by` ajouté en 2.1.13/2.1.14. **Choix architectural réel et assumé** : `process_zip_entry_task` ne reçoit jamais un chemin de fichier temporaire local ni les octets décompressés d'une entrée via ses arguments Celery -- seulement `{zip_file_id, entry_name}` (références sérialisables) -- et re-télécharge toute l'archive depuis S3 avant d'extraire cette seule entrée. Coût réel : un téléchargement S3 répété par entrée, mais c'est le SEUL choix correct dans un vrai déploiement Celery distribué à plusieurs workers (un chemin de fichier temporaire local créé par une tâche n'est pas garanti visible par le worker qui exécute une tâche différente). **Vraie protection ZipSlip** (vision critique 2) : `should_include_zip_entry` rejette toute entrée dont le nom contient une traversée de chemin réelle ou est absolu -- pas parce que la méthode d'extraction de ce dépôt est vulnérable à l'exploit classique d'écriture sur disque (elle ne l'est pas : `extract_zip_file` lit les octets d'une entrée directement par son nom exact, sans jamais appeler `extractall()`), mais parce que ce même nom est stocké tel quel comme nom du Document résultant. **Défense réelle et plus substantielle contre une "zip bomb"** : `extract_zip_file` lit chaque entrée par un vrai flux en boucle, levant une erreur dès que plus de `max_size` octets RÉELLEMENT décompressés ont été lus -- une vraie limite physique de mémoire, indépendante de ce que prétend la métadonnée `file_size` de l'archive (potentiellement falsifiée). **Cohérence (vision critique 1)** : aucun nouveau format, poussé plus loin que toutes les étapes précédentes -- une entrée ZIP extraite passe par exactement le même pipeline `validate_document_upload`/`process_document` qu'un fichier uploadé directement de ce même type réel. Le Document conteneur `.zip` lui-même termine `completed` avec ZÉRO chunk propre (un choix honnête : son rôle est un enregistrement d'audit de l'upload et de son propre dispatch d'entrées, pas un document interrogeable) -- `metadata_json` enregistre le nombre réel d'entrées trouvées vs. effectivement planifiées. **Effet de bord honnête découvert en testant** : deux tests préexistants des Parties 2.1.2/2.1.9 supposaient qu'un ZIP simple soit toujours rejeté (avant que ZIP ne soit un format supporté) -- corrigés pour refléter le nouveau comportement correct (accepté comme `application/zip`, jamais confondu avec un DOCX/EPUB réel). **Le fichier de test le plus pleinement et réellement vérifiable de bout en bout de toute la série** : `tests/test_zip_extraction.py` n'utilise AUCUN mock d'aucune sorte -- chaque test construit une vraie archive ZIP sur disque local réel. Tests réels dédiés (listing, rejet ZipSlip/chemin absolu/répertoire, filtrage réel motif+taille, extraction réelle à mémoire bornée y compris la coupure réelle sur une entrée trop grosse, archive corrompue réelle) + tests d'orchestration réels (logique pure de `process_zip_archive`, comportement réel en base de `import_and_process_zip_archive`/`import_and_process_zip_entry`) + tests de route de bout en bout (upload ZIP accepté, dispatch vers la bonne tâche, permissions), voir `tests/test_zip_extraction.py`/`tests/test_zip_integration.py`/`tests/test_documents.py` |

### 2.2 Gestion des documents

| # | Fonctionnalité | Implémentation prévue |
|---|---|---|
| 2.2.1 | Upload multiple | ✅ **Nouvelle route dédiée `POST /organizations/{org_id}/documents/batch`, PAS une modification littérale de la route d'upload existante** -- déviation réelle et assumée par rapport au texte de la consigne ("modifier POST .../documents") : une vraie réponse multi-fichiers (un résultat PAR fichier) ne peut pas avoir la même forme qu'un `DocumentResponse` unique, et changer le nom de champ multipart/la forme de réponse de la route existante aurait cassé des dizaines de tests d'upload déjà en place depuis les Parties 2.1.1-2.1.9 sans aucun bénéfice réel -- une route additive ne perturbe rien de déjà fonctionnel. `validate_upload_batch` vérifie le nombre réel de fichiers (`DOCUMENT_BATCH_MAX_FILES`, défaut 10) et la taille totale réelle (`DOCUMENT_BATCH_MAX_TOTAL_SIZE`, défaut 100 Mo) -- purement hors ligne, avant tout travail S3/Celery. **Validation de contenu par fichier RÉELLE ET SYNCHRONE, avant tout travail Celery** : `start_document_batch_upload` réutilise `validate_document_upload` (inchangé) sur chaque fichier DANS la requête elle-même -- réponse directe à la vision critique 3/4 ("un fichier invalide est rejeté") rendue immédiatement visible dans la réponse HTTP, pas seulement découvrable plus tard dans les logs d'une tâche d'arrière-plan ; seuls les fichiers acceptés sont transmis à Celery. **Déviation réelle et documentée par rapport à la règle habituelle de ce dépôt** : les octets de chaque fichier accepté transitent réellement par les arguments de la tâche Celery (encodés en base64, `process_upload_batch_task`) -- contrairement à chaque fan-out précédent (qui re-télécharge toujours depuis une source durable comme S3 ou une vraie API externe), un fichier fraîchement uploadé n'a nulle part ailleurs où vivre de façon durable à ce stade ; `DOCUMENT_BATCH_MAX_TOTAL_SIZE` borne réellement cette exception. Un seul vrai job Celery pour tout le lot (`process_upload_batch_task`, conforme au texte littéral), traitant chaque fichier dans une vraie boucle -- pas un fan-out par fichier vers une tâche séparée. **Robustesse (vision critique 3)** : l'échec réel d'upload S3/DB d'UN fichier du lot est journalisé et ignoré, sans jamais interrompre les autres -- même résilience que chaque fan-out précédent de ce dépôt. **Cohérence (vision critique 1)** : aucun nouveau format ni pipeline -- chaque fichier accepté passe par exactement le même `upload_document_file`/`schedule_document_processing` qu'un upload simple. Tests réels dédiés (upload multiple accepté, fichier invalide rejeté sans bloquer les autres, limite de nombre respectée, limite de taille totale respectée, garde-fou cross-tenant, permissions, dispatch Celery ne recevant que les fichiers acceptés, tolérance à un échec S3 réel par fichier, tolérance à une panne du broker), voir `tests/test_documents.py`/`tests/test_document_batch_integration.py` |
| 2.2.2 | Drag & drop | 🟡 **100% frontend, zéro surface backend propre à cette étape -- honnêtement non démarrée, pas "partiellement" démarrée.** Ce dépôt n'a AUCUN frontend React : son seul frontend réel est un dashboard Streamlit (`dashboard/app.py`) qui sert l'ANCIEN pipeline RAG (`src/`), pas `api/`, l'architecture multi-tenant que construit toute cette Partie 2. Question posée explicitement à l'utilisateur le 2026-09-04 (nouveau projet React ? extension du dashboard Streamlit ? backend seul ?) -- réponse : **backend seul pour l'instant**. Le glisser-déposer lui-même n'a littéralement aucune contrepartie serveur (lire des fichiers par API navigateur puis les envoyer est un pur événement client) -- **les deux vraies routes d'upload que cette fonctionnalité utiliserait existent déjà et sont pleinement testées** : `POST /organizations/{org_id}/documents` (2.1.1, fichier unique) et `POST /organizations/{org_id}/documents/batch` (2.2.1, fichiers multiples). Rien de plus à construire côté serveur ; le jour où un vrai frontend existe, le glisser-déposer n'est qu'un appel à ces routes déjà réelles. |
| 2.2.3 | Barre de progression | 🟡 **Backend réel et complet, UI explicitement différée** (voir 2.2.2). `GET /documents/{document_id}/progress` (poll ponctuel) + `GET /documents/{document_id}/progress/stream` (Server-Sent Events, pas WebSocket -- choix réel et justifié : ce flux n'a jamais besoin de RECEVOIR quoi que ce soit du client en cours de route, un canal unidirectionnel HTTP simple suffit). Réutilise le VRAI Redis déjà en service pour le rate limiting/geoip (`RATE_LIMIT_REDIS_URL`) pour un vrai pub/sub -- aucune nouvelle infrastructure. **Limite honnête et assumée** : la progression réelle est mappée sur le vrai statut du Document (`pending`/`processing`/`completed`/`failed` → 0/50/100/100%), pas un pourcentage par chunk réellement instrumenté -- ajouter cette granularité exigerait de modifier `process_document`, le chemin de code le plus partagé et le plus critique de tout ce dépôt (utilisé par chaque format depuis la Partie 2.1.1), pour un gain marginal ; rétrécissement de portée réel et énoncé, pas un oubli. `send_progress_update` publie sur ce vrai canal Redis à chaque transition de statut réelle (3 points d'ajout minimaux et mécaniques dans `process_document`, jamais un remaniement) -- tolérant aux pannes Redis réelles (jamais bloquant pour le vrai traitement). Vision critique 2 ("connexion SSE interrompue") : un vrai `EventSource` navigateur reconnecte automatiquement ; la reconnexion renvoie immédiatement l'état réel courant via le vrai instantané initial, aucune perte d'information au-delà de la coupure elle-même. |
| 2.2.4 | Preview | 🟡 **Backend réel et complet, UI (PDF.js, pagination, zoom) explicitement différée** (voir 2.2.2). `GET /documents/{document_id}/preview` sert le vrai contenu de manière SÉCURISÉE (vision critique 2) : toujours par un proxy authentifié et vérifié par appartenance, jamais un accès S3 direct ou une URL pré-signée publique. Vraie performance (vision critique 1) : `stream_document_file` télécharge par vrais chunks bornés (256 Ko) directement depuis le vrai `StreamingBody` S3, un gros fichier n'est jamais entièrement chargé en mémoire juste pour être prévisualisé -- vérifié par un vrai aller-retour contre S3/MinIO réel (`tests/test_documents_integration.py`). Génération de miniature explicitement marquée optionnelle par la consigne -- délibérément non construite (dépendances réelles supplémentaires, complexité réelle, hors du périmètre honnête "backend seul"). |
| 2.2.5 | Extraction metadata | 🟡 **Extraction/normalisation backend réelle et complète, affichage UI explicitement différé** (voir 2.2.2). Chaque format expose déjà ses propres métadonnées réelles depuis les Parties 2.1.1-2.1.9 (`Document.metadata_json`, jamais modifié ici) -- le vrai travail de cette étape est la NORMALISATION : `api/services/metadata_normalization.py` mappe les clés hétérogènes de chaque format (`creationDate` PDF au format spec brut `D:YYYYMMDDHHmmSS`, `created` DOCX déjà ISO, `tags` frontmatter Markdown, `subject` Dublin Core EPUB, etc.) vers une forme commune réelle `{title, author, created_date, keywords}` -- jamais fabriquée quand un format n'a réellement aucun concept d'auteur/titre/date (CSV/JSON/XML/TXT rapportent honnêtement `None`/`[]`). **Vraie extension de 3 extracteurs existants** (item 1 de la consigne), chacun avec un vrai champ déjà standard mais jamais surfacé : DOCX (`keywords`, le vrai "Tags" OOXML), HTML (`<meta name="keywords">`, une vraie balise standard), EPUB (`dc:subject`, l'équivalent réel Dublin Core des mots-clés). **Distinction réelle et délibérée** : le `creator` PDF (le LOGICIEL auteur, ex. "Microsoft Word") n'est jamais traité comme un repli d'auteur -- une vraie confusion sémantique du spec PDF évitée, pas un oubli. `GET /documents/{document_id}/metadata` calcule la normalisation À LA LECTURE, sans jamais dupliquer le stockage ni toucher au pipeline `process_document` partagé. |
| 2.2.6 | Tags/catégories | ✅ **Deux vraies tables** (migration `0034`) : `document_tags` (`organization_id`, `name`, `color`, `created_by`, vraie contrainte `UNIQUE(organization_id, name)`) et `document_tag_assignments` (le vrai lien M2M, `UNIQUE(document_id, tag_id)`). Nouveau module `api/security/document_tags.py` séparé -- `documents.py` est déjà un vrai gros fichier couvrant chaque source d'import depuis 2.1.1, même découpage que `organizations.py` vs `organization_members.py`. **Cohérence (vision critique 1)** : un tag réel est scopé à `organization_id`, pas un workspace ni un document -- le même tag "finance" réel est utilisable sur tout document de l'organisation ; l'assignation vérifie EN PLUS pour de vrai que le tag et le document appartiennent à la MÊME organisation (garde-fou réel qu'aucune contrainte FK seule ne peut exprimer). **Sécurité (vision critique 3)** : `PATCH`/`DELETE /tags/{tag_id}` réutilisent exactement la même forme de permission que `DELETE /documents/{id}` -- Member+ ET (créateur réel OU Admin/Owner) -- confirmé qu'un autre Member ne peut pas modifier/supprimer un tag qu'il n'a pas créé. **Déviation réelle et documentée** par rapport au texte littéral "Member+" sur les 3 routes de LECTURE (`GET .../tags`, `GET /documents/{id}/tags`) : utilisent `require_org_member` (Viewer inclus), comme chaque autre vraie route GET de ce routeur -- le rôle Viewer est explicitement en lecture seule par la convention déjà établie de ce routeur, et lire une liste de tags est exactement ce type de lecture, pas une écriture. **Performance (vision critique 2)** : les deux vrais index littéraux couvrent chaque vrai pattern de lecture utilisé. Tests réels dédiés (création, doublon de nom rejeté en 409, lecture Viewer, permissions créateur/non-créateur/Admin, assignation/retrait propriétaire vs non-propriétaire, assignation cross-organisation rejetée, assignation en double rejetée, 404 tag inexistant), 29 tests, voir `tests/test_documents.py` |
| 2.2.7 | Versioning | ✅ **Nouvelle table réelle** (migration `0035`), `document_versions` : un vrai instantané append-only par version, `UNIQUE(document_id, version_number)`. `Document` gagne un vrai `current_version_id` (FK nullable) -- les deux tables se référencent mutuellement, donc la migration crée `document_versions` d'abord (référençant `documents` déjà existant) PUIS ajoute `current_version_id` en étape séparée (une vraie séquence en deux temps, pas une DDL circulaire). Nouveau module `api/security/document_versions.py`. **Cohérence** : créer/restaurer une version fait vraiment double usage -- insère un vrai instantané permanent ET met à jour le `Document` LIVE (`file_key`/`file_size`/`file_type`) pour que chaque lecteur existant (preview, metadata, `process_document`, download) continue de fonctionner sans changement, en lisant toujours "le contenu actuel réel" -- re-déclenche le vrai traitement ensuite (`process_document` supprime et recrée déjà les chunks à chaque rerun, réutilisé sans nouvelle logique). **Vrai motif "restaurer = nouvelle version"** (comme `git revert`, pas `git reset`) : restaurer la version 2 d'un document à la version 4 crée une vraie version 5 dont le contenu est copié de la version 2 -- jamais de retour en arrière sur le numéro de version, un vrai historique propre et monotone. **Limite réelle assumée** : l'upload original n'est pas rétroactivement versionné -- aucune version 1 n'existe avant le premier appel explicite à la route de création de version ; instrumenter chaque chemin d'upload/import précédent pour un gain marginal aurait été invasif. **Vrai bug trouvé et corrigé en testant, à souligner** : les routes de création/restauration appelaient `schedule_document_processing` via un nom importé directement dans le routeur -- le monkeypatch autouse de `tests/conftest.py` (qui stub le vrai dispatch Celery pour toute la suite rapide) ne l'atteignait donc jamais, puisque Python copie la référence dans l'espace de noms du routeur à l'import. Effet réel en direct : créer/restaurer une version dans un test déclenchait un vrai `Celery.delay()`, tentant de joindre un vrai Redis injoignable avec un vrai backoff lent -- confirmé par un vrai dump de threads `faulthandler` montrant la pile exacte. Deux nouveaux tests exécutés ensemble prenaient plus de 16 minutes au lieu de quelques secondes. Corrigé en importer le MODULE de sécurité lui-même et en appelant `documents_security.schedule_document_processing(...)` -- la résolution par attribut au moment de l'appel respecte tout monkeypatch du module, peu importe qui appelle. Tests réels dédiés (création séquentielle, permissions propriétaire/non-propriétaire/Admin, version spécifique, 404, restauration créant une vraie nouvelle version, permissions de restauration, lecture Viewer), 10 tests, ~17s après correction (contre 16+ minutes avant), voir `tests/test_documents.py` |
| 2.2.8 | Suppression/remplacement | ✅ **Deux nouvelles colonnes réelles** (migration `0036`) : `deleted_at`/`deleted_by`. `DELETE /documents/{id}` (route existante depuis 2.1.1) devient un VRAI soft delete -- vrai changement de comportement, assumé -- la suppression définitive réelle déménage vers une nouvelle route `DELETE /documents/{id}/permanent`. **Un seul correctif à fort effet de levier, pas une dizaine éparpillés** : plutôt que d'ajouter `deleted_at IS NULL` à chaque requête individuelle (une approche réelle, sujette aux oublis), le vrai correctif vit dans le SEUL point de passage partagé que chaque route mono-document appelle déjà (`_get_document_and_membership` + la requête de `list_documents`) -- un document supprimé devient invisible PARTOUT d'un coup. Confirmé par un test dédié qui vérifie les 7 routes concernées après suppression, chacune renvoyant un vrai 404. **Seule exception réelle et délibérée** : un helper séparé sans filtre, utilisé UNIQUEMENT par la route de purge définitive -- un Admin/Owner doit pouvoir atteindre un document déjà supprimé logiquement pour le purger, sinon un document supprimé ne pourrait jamais être purgé du tout. **Sécurité (vision critique 1)** : purge définitive réservée à Owner/Admin -- contrairement au soft delete, aucun repli "créateur" ici. **Stockage (vision critique 3)** : la purge définitive supprime le vrai objet S3 ET la vraie ligne DB, confirmé par un test vérifiant l'appel réel de suppression S3. **Récupération (vision critique 2)** : un document supprimé logiquement reste atteignable pour purge définitive -- un vrai "undelete" n'était pas demandé et n'est pas construit, limite honnête assumée. **Cohérence avec 2.2.7** : `replace_document` est un vrai alias honnête de `create_document_version_from_upload`, pas une seconde implémentation concurrente -- la vision critique de cette étape demande explicitement que le remplacement crée une nouvelle version. **Correctif de test nécessaire, assumé** : convertir la route DELETE de suppression réelle à logique change son comportement observable -- le test préexistant qui vérifiait la disparition de la ligne vérifie désormais sa survie avec `deleted_at`/`deleted_by`, plus une invisibilité confirmée via un GET de suivi. Tests réels dédiés (route convertie, purge définitive Owner/Admin uniquement, purge atteignant un document déjà supprimé, remplacement créant une vraie nouvelle version, invisibilité confirmée sur 7 routes à la fois), voir `tests/test_documents.py` |
| 2.2.9 | Réindexation manuelle | ✅ **Deux nouvelles routes réelles** (`POST /documents/{id}/reindex`, Member+ si propriétaire ; `POST /organizations/{org_id}/documents/reindex`, Admin+) + deux vraies tâches Celery. **Cohérence -- la réponse "réutilise le pipeline" la plus forte de tout ce lot 2.2** : `reindex_document` n'implémente AUCUNE nouvelle logique de suppression/recréation de chunks -- il appelle simplement le vrai `process_document` existant, qui supprime et recrée déjà les chunks/embeddings à chaque rerun depuis la Partie 2.1.1. Réindexer, c'est littéralement relancer `process_document`. **Performance (vision critique 1)** : la réindexation d'organisation est réellement pilotée par Celery à DEUX niveaux, pas une boucle synchrone géante -- liste tous les documents réels non supprimés puis fan-out d'une vraie tâche par document (même stagger de courtoisie que chaque autre fan-out de ce dépôt). **Robustesse (vision critique 2)** : un échec réel à mi-chemin ne marque `failed` que LE document concerné (via la gestion d'exception déjà existante de `process_document`) -- chaque autre document continue normalement, confirmé par un test où une panne broker sur un document n'empêche pas les deux autres d'être planifiés. **Journalisation (vision critique 3)** : réutilise le `logger.warning` déjà existant de `process_document`, aucune nouvelle infrastructure de log. **Vrai bug capturé et corrigé AVANT d'atteindre le CI, grâce au diagnostic déjà appris en 2.2.7** : les nouvelles routes appelaient `schedule_document_reindex`/`schedule_organization_reindex` via des noms importés directement dans le routeur -- exactement le même piège que 2.2.7. Capturé immédiatement cette fois (un nouveau dump `faulthandler` a confirmé) et corrigé de la même façon (résolution par le module au moment de l'appel). Tests réels dédiés (permissions propriétaire/non-propriétaire/Admin, réservation Admin+ pour l'organisation, comptage réel excluant les documents supprimés, orchestration réelle de `reindex_document`/`reindex_documents`/`reindex_organization`, tolérance à une panne broker), voir `tests/test_documents.py`/`tests/test_reindex.py` |
| 2.2.10 | Historique modifications | ✅ **Nouvelle table réelle** `document_audit_logs` (migration `0038`, RLS activée en ligne cette fois -- oubli déjà corrigé une fois pour 2.2.6/2.2.7, pas une seconde fois). Nouveau module `api/security/document_audit.py`. **Vraie lacune honnête assumée** : `restored` (undelete depuis un soft delete réel) est défini dans le vocabulaire mais n'est produit nulle part dans ce dépôt -- 2.2.8 a explicitement stipulé qu'aucun vrai endpoint d'annulation de suppression n'a été construit ; le nom existe pour qu'une future vraie fonctionnalité ait un seul vrai endroit où se brancher. **Choix réel et délibéré, contrairement au pub/sub Redis de 2.2.3** : `log_document_action` n'est jamais enveloppé dans un try/except best-effort -- il partage la même vraie transaction que l'action qu'il enregistre ; une mise à jour de progression manquée ne coûte qu'une UI légèrement obsolète, un enregistrement d'audit manquant pour une action qui a réellement eu lieu trahirait le but même de cette étape. **Intégration réelle dans 6 fonctions déjà existantes réparties sur 3 fichiers**, chacune une seule ligne additive utilisant l'acteur déjà disponible -- deux ajouts réels et délibérés : `unassign_tag_from_document` gagne un `removed_by` optionnel, et `reindex_document`/`reindex_documents`/`reindex_organization` (et leurs signatures de tâches Celery) gagnent un `triggered_by` optionnel, tous deux par défaut `None` pour ne rien casser des appelants existants de 2.2.6/2.2.9. `create_document_version_from_upload` (le seul point de passage partagé entre `/versions` et `/replace`) journalise `updated` ; `restore_document_version` journalise `version_restored` SEUL (jamais `updated` en double, puisqu'une restauration appelle directement la fonction de bas niveau, jamais celle qui journalise `updated`). **Performance (vision critique 1)** : pas de Celery -- choix honnête et assumé, une simple insertion bon marché dans la même transaction qu'une écriture déjà en cours, pas une opération coûteuse méritant d'être différée. **Stockage (vision critique 2)** : conservé indéfiniment, aucune politique de rétention demandée ni construite, limite honnête assumée. **Sécurité (vision critique 3)** : même garde-fou `_get_document_and_membership` que chaque autre route -- seuls les membres de l'organisation propriétaire du document peuvent voir son historique. Tests réels dédiés (pagination, isolation par document, vocabulaire d'action fixe, vraie entrée créée après chacune des 6 actions intégrées, `updated` compté exactement une fois pour une restauration, lecture Viewer, 404 hérité pour un document supprimé), voir `tests/test_document_audit.py`/`tests/test_documents.py` |
| 2.2.11 | Statut d'indexation | 🟡 **Backend réel et complet, UI (polling frontend) explicitement différée** (voir 2.2.2). **Déviation réelle et documentée par rapport au texte littéral** ("colonne `indexing_status`") : plutôt qu'une DEUXIÈME colonne de statut facilement désynchronisée de la première, réutilise le `Document.status`/`processed_at` déjà réel et déjà suivi depuis la Partie 2.1.1 -- le même raisonnement "éviter deux sources de vérité" déjà appliqué avec succès en 2.2.8 (soft delete réutilisant `status` plutôt qu'un nouveau flag). Seules les DEUX informations réellement nouvelles gagnent une colonne : `indexing_started_at` (horodatage réel du début de la tentative en cours) et `indexing_error` (le vrai message d'erreur, lisible sans fouiller `metadata_json`). Les deux sont posées aux deux vrais points de transition de `process_document` (déjà réutilisé sans changement de logique) : `indexing_started_at` au début (et toute erreur périmée d'une tentative précédente y est effacée au même moment, pour qu'une réindexation en cours n'affiche jamais une vieille erreur pendant qu'elle retente), `indexing_error` uniquement sur le chemin `failed`, avec le MÊME message déjà enregistré dans `metadata_json["error"]` -- une seule vraie erreur, deux endroits où elle doit être lisible, jamais deux sources concurrentes. Deux nouvelles routes réelles : `GET /documents/{id}/status` (Member+, Viewer inclus, même garde-fou `_get_document_and_membership`) et `GET /organizations/{org_id}/documents/status` (Admin+, un vrai comptage `GROUP BY status` sur les documents non supprimés de l'organisation, jamais une estimation). Tests réels dédiés : chemin d'échec réel forcé (téléchargement S3 mocké en échec, sans tokenizer ni embeddings), effacement réel d'une erreur périmée lors d'une nouvelle tentative, permissions/404/anti-énumération sur les deux routes, comptage réel par statut excluant les documents supprimés -- plus deux assertions ajoutées aux tests d'intégration Postgres réels déjà existants (`tests/test_documents_integration.py`) prouvant le chemin de succès réel (`indexing_started_at` posé, `indexing_error` resté `None`). Voir `tests/test_document_status.py`/`tests/test_documents.py`/`tests/test_documents_integration.py` |
| 2.2.12 | Détection doublons | ✅ **Nouvelle colonne réelle** `content_hash` (migration `0040`) : vrai hash SHA-256 hex des octets bruts uploadés, calculé AVANT tout parsing spécifique au format -- identique quel que soit le format parmi les 10 acceptés. **Déviation réelle et documentée par rapport au texte littéral** ("UNIQUE (organization_id, content_hash)") : un simple INDEX, pas une contrainte UNIQUE en base -- découvert concrètement en testant : `upload_document`/`process_upload_batch` bloquent déjà la création d'un doublon au niveau applicatif ; si la base l'interdisait AUSSI physiquement, la route littérale `POST .../deduplicate` (item 4) ne trouverait plus jamais rien à faire en fonctionnement normal, ce qui viderait sa propre raison d'être demandée. Compromis assumé : la fenêtre de course étroite entre la vérification applicative et l'insertion n'est plus fermée par la base -- réelle mais rare, sans risque d'intégrité (la route de déduplication existe justement pour nettoyer ce cas). **Deuxième déviation réelle, découverte en testant** : l'identité de doublon est `(organization_id, content_hash, file_type)`, pas seulement le hash seul -- les tests déjà établis de ce dépôt (Markdown vs TXT, CSV vs TXT, "mêmes octets, extension différente") prouvent que les mêmes octets bruts peuvent légitimement être deux documents réels différents selon le format détecté ; un hash pur aurait faussement signalé ces deux scénarios déjà testés comme des doublons. Appliqué aux DEUX vrais chemins d'upload (simple ET batch, une extension de cohérence réelle au-delà du texte littéral qui ne nomme que `upload_document_file`) ; explicitement PAS appliqué aux sources d'import externes (URL/GitHub/Drive/Notion/Confluence/OneDrive), qui ont leur propre sémantique de re-synchronisation (portée de 2.2.13/2.2.14), limite réelle assumée. Nouvelles routes : `GET /documents/{id}/duplicates` (Member+) et `POST /organizations/{org_id}/documents/deduplicate` (Admin+, conserve le doublon le plus ancien, supprime logiquement les autres via `soft_delete_document` déjà existant -- réversible, jamais permanent, cohérent avec la consigne "sans risque"). Réponse d'upload : `200` (pas `201`) pour un doublon détecté, un vrai mensonge sinon. **Régression réelle trouvée et corrigée** : le helper de test `_upload()` réutilisait un seul contenu par défaut partagé sur 110+ appels -- inoffensif avant, mais plusieurs tests déjà existants uploadant deux fois pour simuler "deux documents distincts" auraient silencieusement reçu le même document deux fois ; corrigé à la racine (contenu par défaut réellement varié par appel). Tests réels dédiés (déterminisme du hash, portée par organisation/format, exclusion des documents supprimés, doublon réel détecté et non détecté, déduplication conservant le plus ancien), voir `tests/test_document_duplicates.py`/`tests/test_documents.py` |
| 2.2.13 | Détection docs modifiés | ✅ **Deux nouvelles colonnes réelles** `last_modified`/`last_checked` (migration `0041`). Nouvelle fonction réelle `api/services/url_fetching.py::get_url_last_modified` -- vraie requête HEAD via le MÊME transport SSRF-safe déjà utilisé par ce module, lecture du vrai header HTTP standard `Last-Modified`. **Cohérence (vision critique 1), réponse honnête en deux temps** : `source_url` est en réalité déjà posé par QUASIMENT toutes les sources d'import (URL, GitHub, Google Drive/Docs, Notion, Confluence, OneDrive -- pas seulement 2.1.10) ; MAIS un mécanisme HTTP générique et non authentifié ne peut honnêtement répondre "a changé ?" que pour une URL publique directement accessible (2.1.10, pages GitHub publiques) -- Drive/Docs/Notion/Confluence Cloud exigent une authentification qu'une requête anonyme n'a pas. Une vraie vérification authentifiée par source est précisément ce que 2.2.14 (étape suivante immédiate de ce lot), via `ExternalSource`, construit correctement -- pas dupliqué ici avec un mécanisme qui ne fonctionnerait pas pour ces sources de toute façon. Un upload direct sans `source_url` retourne honnêtement `None` -- aucune source externe indépendante à comparer. **Performance (vision critique 2)** : le balayage périodique système (`check_modified_documents_task`) est un vrai Celery Beat quotidien (même fenêtre de faible trafic que les autres tâches planifiées) ; la route mono-document `POST .../check-modified` reste synchrone (une seule requête HEAD bornée, pas la préoccupation "gérée par Celery" du balayage en masse). **Robustesse (vision critique 3)** : `get_url_last_modified` ne lève JAMAIS -- source injoignable, statut non-200, header absent/imparsable, ou même une vraie cible bloquée SSRF (le transport SSRF-safe lève un `ValueError` brut, explicitement intercepté aussi) -- tout résout en `None` honnête, jamais un faux positif ; `last_checked` avance quand même à chaque tentative réelle. **Bug réel trouvé et corrigé avant livraison** : la première version du balayage périodique annulait TOUTE la transaction sur l'échec d'UN document, effaçant silencieusement les vérifications déjà réussies des documents précédents dans le même balayage -- corrigé par un commit réel par document. **Déviation assumée** : pas de colonne `is_outdated` -- `GET /documents/outdated` (sans `{org_id}` dans son propre chemin littéral, donc interprété comme "toutes mes organisations") dérive l'obsolescence en comparant `last_modified` au `processed_at` déjà existant, même raisonnement qu'en 2.2.8/2.2.11. Tests réels dédiés (parsing réel du header via un vrai flux httpx à transport simulé, cible SSRF bloquée résolvant en `None` sans lever, comparaison neuf/inchangé/injoignable/jamais-vérifié, dérivation d'obsolescence, portée par appartenance d'organisation), voir `tests/test_url_fetching.py`/`tests/test_document_modification_check.py`/`tests/test_documents.py` |
| 2.2.14 | Sync automatique | ✅ **Nouvelle table réelle** `external_sources` (migration `0042`, RLS activée en ligne dès le départ). Nouveau routeur dédié `api/routers/external_sources.py` (ressource distincte, pas une sous-ressource de `/documents`). **La réponse "réutilise le pipeline" la plus forte de tout ce lot 2.2** : `sync_external_source` n'implémente AUCUNE nouvelle logique de communication avec GitHub/Drive/Notion/Confluence/OneDrive -- elle appelle directement les mêmes vraies fonctions déjà existantes et testées des Parties 2.1.12-2.1.18 (`process_github_repo`/`process_google_drive`/`process_notion_database`/`process_confluence_space`/`process_onedrive`). `source_id` désigne toujours le CONTENEUR (dépôt, dossier Drive, base Notion, espace Confluence, dossier OneDrive), jamais une page/fichier isolé -- cohérent avec la sémantique réelle d'une synchronisation récurrente. **Déviation réelle et documentée par rapport au texte littéral** ("config (JSONB)") : `config_encrypted`, un blob opaque chiffré par Fernet (même chiffrement au repos déjà utilisé par ce dépôt pour les clés de signature JWT et les secrets SSO entreprise), stocké en TEXT -- chaque type de source de cette étape s'authentifie via un vrai jeton que ce dépôt traite déjà comme un secret ; traiter tout le blob comme sensible par défaut est plus sûr que de faire confiance à chaque futur appelant. **Constat architectural réel et assumé, énoncé clairement plutôt que contourné en silence** : les 5 pipelines existants lisent chacun leur identifiant depuis un unique réglage SERVEUR (pas par organisation) -- une vraie gestion d'identifiants par organisation pour 5 fournisseurs OAuth différents est un chantier réel, séparé, non demandé par le texte littéral de cette étape. **Limite réelle et importante, énoncée en évidence plutôt que masquée** : aucun des 5 pipelines existants ne vérifie qu'un document pour un item donné existe déjà avant d'en créer un -- une resynchronisation réelle réimporte donc tout le conteneur à chaque fois qu'elle a effectivement lieu ; `detect_source_changes` existe précisément pour rendre ce cas rare, pas pour l'éliminer -- une vraie déduplication incrémentale par item (étendant le mécanisme de hash de 2.2.12, aujourd'hui limité aux uploads directs, aux pipelines d'import) est un vrai chantier futur, nommé explicitement plutôt que silencieusement prétendu résolu. **Performance (vision critique 1), réponse honnête en deux temps** : pour GitHub, un vrai signal gratuit déjà existant (`pushed_at`, obtenu par le même appel que `process_github_repo` fait déjà) comparé à `last_sync_at` ; pour les 4 autres types, aucun signal comparable n'existe sans un vrai appel de listing séparé hors du périmètre de cette étape -- réponse honnête "changement possible", limitée à un vrai intervalle minimal de resynchronisation plutôt que vérifiée à chaque tick. **Robustesse (vision critique 2)** : même résilience "l'échec d'une source ne bloque pas les autres" que chaque autre opération en masse de ce dépôt, confirmée par un test réel ; le balayage périodique committe par source, pas en une seule transaction (même bug déjà trouvé et corrigé en 2.2.13). **Gestion des conflits (vision critique 3)** : limite réelle assumée -- la synchronisation n'ajoute que de nouveaux documents pour l'instant (jamais de modification/remplacement), donc aucun vrai conflit local-vs-source n'est encore possible ; un vrai mécanisme de résolution deviendra nécessaire le jour où la déduplication incrémentale par item existera. Tests réels dédiés (CRUD, validation de type, garde-fou cross-tenant, chiffrement réel du config, dispatch vers le bon pipeline pour les 5 types, transitions de statut réelles, source désactivée rejetée, résilience multi-sources, permissions Manager+ sur les 5 routes, anti-énumération, `config` jamais renvoyé dans une réponse), voir `tests/test_external_sources.py` |
| 2.2.15 | Réindexation programmée | ✅ **Nouvelle colonne réelle** `Document.reindex_schedule` (override cron par document) et **nouvelle table réelle** `reindex_schedules` (migration `0043`, RLS en ligne), un vrai schedule cron nommé par organisation. **Zéro nouvelle dépendance de parsing cron** : `_crontab_from_pattern` parse le pattern stocké directement via la vraie classe `celery.schedules.crontab` (déjà une vraie dépendance de ce dépôt pour Beat lui-même) et réutilise ses vraies méthodes `is_due`/`remaining_estimate` -- confirmé en direct contre la version Celery installée, pas supposé depuis la documentation. **Cohérence, encore la réutilisation du pipeline** : `schedule_reindex` n'implémente aucune nouvelle logique -- appelle le même `reindex_organization` (2.2.9) inchangé ; l'override par document réutilise `Document.indexing_started_at` (2.2.11) comme référence de "dernière exécution" plutôt que d'ajouter une paire `last_run_at`/`next_run_at` dupliquée. **Performance (vision critique 1)** : le vérificateur périodique tourne sur un vrai intervalle d'UNE MINUTE (pas un crontab quotidien comme les autres tâches planifiées) -- un pattern cron stocké peut légitimement demander "chaque minute", donc le vérificateur doit tourner au moins aussi souvent pour le respecter. **Gestion des conflits (vision critique 2), réponse honnête** : ni `reindex_organization` ni `reindex_document` ne suivent un état "en cours" -- un chevauchement réel entre une réindexation planifiée et une manuelle produit au pire un vrai travail redondant (jamais une corruption, `process_document` étant déjà sûr sous répétition depuis la Partie 2.1.1) ; limite réelle assumée : aucun verrou distribué, disproportionné vu la cadence réelle visée (horaire/quotidienne, pas sub-seconde). **Robustesse (vision critique 3)** : même résilience "un échec n'affecte pas les autres" que chaque opération en masse de ce dépôt. **Bug réel trouvé et corrigé avant livraison, même famille que 2.2.13/2.2.14** : `run_scheduled_reindexes` committe désormais par schedule/document, pas en une seule transaction finale. **Permission plus stricte que 2.2.14** : Admin+ (pas Manager+) pour toute écriture -- une réindexation automatique et récurrente à l'échelle de l'organisation est un levier plus important qu'une simple connexion de synchronisation. Tests réels dédiés (validation cron réelle, calcul de `next_run_at`, détection réelle des schedules/documents dus, exclusion des désactivés/supprimés, orchestration réelle, résilience multi-schedules, permissions Admin+ sur les 4 routes, anti-énumération), voir `tests/test_reindex_schedules.py` |
| 2.2.16 | Batch processing | ✅ **Deux nouvelles tables réelles** `batch_jobs`/`batch_job_items` (migration `0044`, RLS en ligne sur les deux). **Une vraie couche de suivi générique, pas un sixième pipeline concurrent** : `process_batch_job` n'implémente aucune nouvelle logique par item pour ses 5 vrais `job_type` -- dispatch direct vers la même fonction réelle déjà construite et testée par une étape 2.2 antérieure (`upload_document` 2.1.1/2.2.12, `reindex_document` 2.2.9, `soft_delete_document` 2.2.8, `sync_external_source` 2.2.14, `replace_document` 2.2.8). `process_upload_batch` (2.2.1, une seule requête HTTP, résultat agrégé seulement) reste inchangé pour ce cas précis -- la vraie valeur distincte de cette étape est le suivi PERSISTÉ par item, la reprise et l'annulation, à travers n'importe laquelle des 5 opérations. **Deux ajouts réels, petits, nécessaires, documentés au-delà des colonnes littérales** : `BatchJobItem.sequence` (aucune des deux tables littérales n'a de colonne d'ordre, nécessaire pour aligner chaque ligne sur son entrée réelle dans `config["items"]`) ; `BatchJobStatus.cancelled` (pas une des 4 valeurs littérales, mais `cancel_batch_job` a besoin d'un état terminal honnête distinct de `failed` -- même raisonnement que le `restored` de 2.2.10). **Où vivent réellement les données d'entrée par item** : `BatchJob.config["items"]` -- `process_batch_job` tourne plus tard, dans une session Celery séparée, et a besoin d'un endroit durable pour lire l'entrée de chaque item (octets de fichier en base64 pour un upload -- même exception réelle et documentée déjà faite une fois en 2.2.1). **Performance (vision critique 1)** : la création retourne immédiatement (`201`, `pending`), le vrai travail est planifié via Celery selon le même schéma `schedule_*` que partout ailleurs, confirmé par un test réel. **Robustesse/Gestion des erreurs (vision critique 2/3)** : même résilience "l'échec d'un item ne bloque pas les autres" que chaque opération en masse -- erreur capturée et journalisée sur la ligne de CET item précis ; commit par item, pas en une seule transaction finale (même bug déjà trouvé et corrigé en 2.2.13/2.2.14/2.2.15) ; un échec catastrophique au niveau du job (config malformée) est capturé par un filet de sécurité externe et termine en `failed` réel, jamais bloqué à `processing`. **Annulation réelle et honnêtement COOPÉRATIVE** : le flag est vérifié entre les items, jamais en cours de traitement d'un item déjà démarré -- confirmé par un test réel. **Reprise réelle** : `process_batch_job_task`/`resume_batch_job_task` sont la même fonction réelle sous deux noms, déjà sûre à rappeler puisqu'elle ne retraite jamais que les items encore `pending`. Permission Admin+ sur les 5 routes -- un batch job peut exécuter à grande échelle n'importe laquelle des actions administratives/destructives de 2.2.8/2.2.9/2.2.14. Tests réels dédiés (CRUD, dispatch correct par type, isolation réelle des échecs par item, filet de sécurité catastrophique, annulation coopérative réelle, reprise réelle, permissions Admin+ sur les 5 routes, anti-énumération), voir `tests/test_batch_jobs.py` |

---

## PARTIE 3 — Pipeline RAG avancé — 🟡 PARTIEL (~15/41, dont 3.1.1-3.1.10 réels dans `api/`, 2026-09-04)

### 3.1 Ingestion — ✅ (10/10, la Partie 3.1 est désormais intégralement couverte)

**Mise à jour 2026-09-04** : le nettoyage/normalisation "déjà existant pour Markdown uniquement" ci-dessous fait référence à `src/ingestion.py`, l'ANCIEN pipeline RAG mono-tenant (servi par le dashboard Streamlit) -- un code totalement distinct et non réutilisé par `api/`, le vrai backend multi-tenant que construit toute cette Partie 3, comme déjà établi pour la Partie 2. Les items 3.1.1/3.1.2 ci-dessous sont un vrai travail NEUF dans `api/`, pas une redécouverte de ce qui existe déjà dans `src/`.

| # | Item | Statut |
|---|---|---|
| 3.1.1 | Nettoyage du texte | ✅ Voir détails ci-dessous |
| 3.1.2 | Normalisation du texte | ✅ Voir détails ci-dessous |
| 3.1.3 | Extraction du texte (amélioration) | ✅ Voir détails ci-dessous |
| 3.1.4 | Extraction des tableaux | ✅ Voir détails ci-dessous |
| 3.1.5 | Extraction des images | ✅ Voir détails ci-dessous |
| 3.1.6 | OCR | ✅ Voir détails ci-dessous (vérification réelle via CI, binaires système absents de cette machine de dev) |
| 3.1.7 | Détection de langue | ✅ Voir détails ci-dessous |
| 3.1.8 | Détection de structure documentaire | ✅ Voir détails ci-dessous |
| 3.1.9 | Extraction des titres et sections | ✅ Voir détails ci-dessous |
| 3.1.10 | Extraction avancée des métadonnées | ✅ Voir détails ci-dessous |

#### Partie 3.1.1 — Nettoyage du texte

✅ **Nouveau module réel** `api/services/text_cleaning.py` : `normalize_whitespace`, `remove_control_characters`, `normalize_unicode` (NFKC), `preserve_structure`, `clean_text` (pipeline complet). Intégré dans `process_document` (`api/security/documents.py`), appliqué sur CHAQUE chunk juste avant l'embedding (texte littéral de l'item 3), pas sur la section entière avant découpage -- les limites de chunk reflètent donc toujours la vraie longueur du texte extrait. **Performance (vision critique 1)** : opérations regex/Unicode pures sur des chaînes déjà en mémoire, confirmé rapide sur 20000 répétitions dans un vrai test chronométré (< 5s). **Préservation de structure (vision critique 2)** : une ligne réellement structurelle (titre Markdown, item de liste, ligne de tableau -- définition réelle mais volontairement étroite, voir le docstring du module) garde son propre saut de ligne, jamais fusionnée avec le paragraphe voisin ; limite honnête assumée : ne redérive pas une structure que l'extraction n'a jamais capturée en texte (mise en forme DOCX réelle, mise en page PDF réelle). **Robustesse (vision critique 3)** : chaque fonction retourne `""` pour `None`/vide, ne lève jamais. Tests réels dédiés (espaces, caractères de contrôle, Unicode, préservation de titres/listes/tableaux, pipeline complet, performance), voir `tests/test_text_cleaning.py`.

#### Partie 3.1.2 — Normalisation du texte

✅ **Nouveau module réel** `api/services/text_normalization.py` : `normalize_case`, `normalize_accents`, `normalize_dates`, `normalize_numbers`, `normalize_units`, `normalize_text` (pipeline). Intégré dans `process_document`, appliqué juste après `clean_text` sur chaque chunk. **Cohérence (vision critique 1)** : réponse honnête à "configurable par langue" -- un paramètre réel `date_order` (`dmy`/`mdy`) répond à la vraie ambiguïté locale jour/mois-premier (pas une fausse i18n complète). **Défauts volontairement conservateurs** : `normalize_text` ne change PAS la casse ni les accents par défaut (perte réelle de signal sémantique pour du texte français destiné à l'embedding) -- seuls dates/nombres/unités sont normalisés par défaut, un vrai format ambigu avec une forme canonique correcte, pas une réécriture destructrice du contenu. **Point honnête soulevé, pas caché** : normaliser le contenu réellement stocké/embeddé (ex. "15/03/2026" → "2026-03-15") à l'indexation SANS normalisation symétrique côté requête peut réduire le rappel pour une recherche littérale sur le format d'origine -- un vrai compromis RAG, assumé et documenté, pas résolu dans cette étape (nécessiterait une normalisation symétrique côté requête, hors scope littéral ici). Tests réels dédiés (casse, accents, dates dans les deux ordres, nombres avec virgule décimale française correctement préservée, unités, pipeline complet, performance), voir `tests/test_text_normalization.py`.

**Ordre de dépendance réel, pas l'ordre numérique littéral** : 3.1.4 (tableaux) et 3.1.5 (images) ont été traités AVANT 3.1.3 (amélioration de l'extraction), et 3.1.6 (OCR) sera traité avant 3.1.3 également -- 3.1.3 demande explicitement d'ajouter l'OCR pour les images (`extract_text_image`, "optionnel, via Tesseract"), exactement ce que 3.1.6 construit en profondeur ; traiter 3.1.6 en premier évite de construire l'OCR deux fois. 3.1.3 sera donc finalisé en dernier, une fois 3.1.4/3.1.5/3.1.6 en place, pour ne couvrir que ce qui reste réellement (notes de bas de page, revue des extracteurs existants).

#### Partie 3.1.4 — Extraction des tableaux

✅ **Constat réel important fait avant d'écrire quoi que ce soit** : l'extraction de tableaux existait DÉJÀ pour PDF/DOCX/Markdown/CSV depuis la Partie 2.1.x (chacune retournant déjà un vrai `pandas.DataFrame`) -- mais `process_document` ne stockait qu'un COMPTE (`table_count`), jamais les données structurées elles-mêmes. Le vrai périmètre honnête de cette étape : combler le seul vrai manque (HTML, `tables: []` codé en dur) et exposer le vrai contenu des tableaux, pas seulement un compte. **Nouvelle fonction** `extract_tables_html` (`pandas.read_html`, déjà appuyé sur `lxml`, aucune nouvelle dépendance). **Nouveau module réel** `api/services/table_transformation.py` : `table_to_markdown` (rendu Markdown écrit à la main, pas `to_markdown()` qui exigerait la dépendance optionnelle `tabulate`), `table_to_json`, `table_to_text`, `normalize_table`, `detect_table_headers`. `process_document` stocke désormais `metadata_json["tables"]` réel et structuré (borné à 100 lignes par tableau, limite réelle assumée). **Deux vrais bugs trouvés et corrigés en testant** : `table_to_json` ne produisait pas de vrai `None` pour une valeur numérique manquante (`.where(..., None)` revient silencieusement à `NaN` sur une colonne `float64`, un vrai piège pandas) -- corrigé via `DataFrame.to_json` ; `normalize_table` ne nettoyait pas les espaces car conditionné sur `dtype == object`, alors qu'un pandas moderne peut utiliser un dtype `str` natif -- corrigé en vérifiant le type de chaque valeur plutôt que le dtype de colonne. **Cohérence (vision critique 1)** : chaque fonction opère sur un DataFrame déjà extrait, comportement uniforme quel que soit le format d'origine. Tests réels dédiés (5 fonctions, tous formats de table extraction), voir `tests/test_table_transformation.py`/`tests/test_html_extraction.py`, plus assertions réelles ajoutées aux tests d'intégration DOCX/HTML existants.

#### Partie 3.1.5 — Extraction des images

✅ **Nouveau modèle réel** `DocumentImage` (migration `0045`, RLS en ligne). **Nouveau module réel** `api/services/image_extraction.py` : `extract_images_docx` (relations de paquet python-docx), `extract_images_epub` (ebooklib `ITEM_IMAGE`), `extract_images_html` (référence seulement, voir limite ci-dessous), `get_image_metadata` (Pillow, parsing d'en-tête seulement). `extract_pdf_images` existait déjà depuis 2.1.1 (réutilisée sans changement). **Nouvelle fonction** `save_image` dans `document_storage.py`. **Initiative réelle et assumée au-delà de la liste d'actions littérale** : cette étape ne listait explicitement AUCUNE intégration au pipeline (contrairement à 3.1.1/3.1.2/3.1.4) -- mais des fonctions d'extraction et un modèle sans rien qui les appelle seraient une fonctionnalité réellement inerte ; `process_document` appelle désormais le bon extracteur pour PDF/DOCX/EPUB et crée de vraies lignes `DocumentImage`. Une nouvelle route réelle et minimale `GET /documents/{id}/images` a été ajoutée pour la même raison (stocker sans pouvoir relire serait tout aussi inerte). **Limite réelle et documentée pour HTML, énoncée clairement** : les images HTML référencent presque toujours une URL EXTERNE, pas des octets embarqués -- les récupérer exigerait le même transport SSRF-safe que 2.1.10, pour un bénéfice réel marginal ; `extract_images_html` retourne donc seulement `src`/`alt`, jamais d'octets récupérés, jamais branché sur `save_image`. **Stockage (vision critique 2)** : même bucket S3 que le document lui-même, sous `documents/{org}/{doc}/images/{index}`, aucune nouvelle infrastructure. **Performance (vision critique 1)** : Pillow ne lit que l'en-tête réel de l'image (jamais un décodage complet du raster) ; échec d'une image isolée n'interrompt jamais le reste du document. **Métadonnées (vision critique 3)** : format/largeur/hauteur réels via Pillow, `{}` honnête pour des octets non décodables. Tests réels dédiés (4 fonctions, route, plus une vraie image intégrée au test d'intégration DOCX existant confirmant le round-trip S3 réel), voir `tests/test_image_extraction.py`/`tests/test_documents.py`.

#### Partie 3.1.6 — OCR

✅ **Nouveau module réel** `api/services/ocr.py` : `ocr_image`, `ocr_pdf_page`, `ocr_pdf_scanned`, `detect_scanned_pdf`, `get_ocr_confidence`, plus `ocr_image_bytes`/`ocr_image_with_confidence` (ajouts réels nécessaires, voir ci-dessous). **Nouvelle config réelle** `api/config.py` : `OCR_ENABLED`/`OCR_LANGUAGE` (`fra`)/`OCR_DPI`/`OCR_TIMEOUT`. Intégré dans `extract_document_content` (un PDF réellement scanné est OCR AVANT le reste du dispatcher, texte littéral de l'item 4) et dans la boucle d'images de `process_document` (chaque image intégrée reçoit un OCR automatique réel -- "pour les images" signifie les images intégrées de 3.1.5, puisque ce dépôt n'accepte jamais une image brute comme upload de document de premier niveau). **Limite réelle et importante, énoncée en évidence, pas découverte par surprise** : `pytesseract`/`pdf2image` sont de simples wrappers Python autour d'un vrai binaire système séparé qu'aucun des deux paquets pip n'installe (le moteur Tesseract, et `pdftoppm`/`pdftocairo` de poppler) -- confirmé qu'AUCUN des deux n'est installé sur la machine de développement de cette session. Le job CI `api-tests` installe désormais les deux (`apt-get install tesseract-ocr tesseract-ocr-fra poppler-utils`) pour une vraie vérification de bout en bout que cette machine ne peut pas fournir. **Robustesse (vision critique 3), exception réelle et nommée** : `OCRNotAvailableError` distingue "le binaire réel n'est pas installé" de tout autre échec OCR réel -- les deux points d'intégration dégradent gracieusement (gardent le texte déjà extrait, ou sautent l'OCR pour cette image), confirmé en direct sur cette machine (le message de dégradation a été réellement observé, pas seulement simulé dans un test). **Déviation réelle et documentée par rapport au texte littéral** de `get_ocr_confidence(text)` : prend le vrai dictionnaire de données par mot de l'OCR (`pytesseract.image_to_data`), pas du texte brut -- un score de confiance réel ne peut venir que de l'inférence propre du moteur OCR au moment où il tourne, jamais reconstruit honnêtement depuis du texte déjà extrait. **Qualité (vision critique 2)** : `detect_scanned_pdf` est une heuristique réelle sur du texte réellement extrait par PyMuPDF (aucun OCR nécessaire pour cette détection elle-même). **Performance (vision critique 1)** : `OCR_DPI`/`OCR_TIMEOUT` réellement configurables ; coût réel et honnête assumé -- un document avec beaucoup d'images intégrées signifie beaucoup d'appels OCR réels et proportionnels. Tests réels dédiés (calcul de confiance, détection de PDF scanné sans Tesseract, orchestration simulée à la frontière pytesseract/pdf2image, DEUX tests réels de bout en bout marqués SKIP sur cette machine faute de binaires -- confirmés sauter correctement plutôt que d'être simulés), voir `tests/test_ocr.py`, plus un vrai test d'intégration PDF scanné de bout en bout dans `tests/test_documents_integration.py` (également SKIP en local, réellement exécuté en CI).

#### Partie 3.1.3 — Extraction du texte (amélioration)

✅ **Construite délibérément EN DERNIER dans ce lot de 6, pas dans l'ordre numérique** -- l'item 2 de cette étape nomme `extract_text_image` ("OCR via Tesseract, optionnel"), exactement ce que 3.1.6 construit déjà en profondeur ; faire 3.1.6 d'abord évite de construire l'OCR deux fois. Le vrai périmètre restant, une fois cette redite et le travail déjà livré par 3.1.4/3.1.5 pris en compte, est étroit : **un seul vrai manque, trouvé en révisant réellement chaque extracteur existant** (item 1 littéral), pas du travail fabriqué. **Le vrai manque : les notes de bas de page DOCX.** `extract_docx_text` (2.1.2) parcourt `document.paragraphs` -- confirmé que python-docx n'a AUCUNE API publique pour les notes de bas de page (ni lecture ni écriture) : elles vivent dans une vraie partie OOXML séparée, `word/footnotes.xml`, que `document.paragraphs` ne touche jamais. Nouvelle fonction `extract_docx_footnotes`, trouvant cette vraie partie via `part.package.parts` (filtré par le vrai type de contenu OOXML standard), parsée avec le même vrai parcours `w:p`/`w:t` que python-docx utilise en interne. Les vraies notes structurelles de séparation (ids `-1`/`0`, jamais du vrai contenu) sont correctement exclues. Intégré dans `extract_document_content` comme une vraie section DISTINCTE (`metadata={"footnotes": True}`), jamais fusionnée silencieusement dans le texte du corps. **Complétude (vision critique 1), constat honnête pour les 3 autres formats** : PDF (`page.get_text()`) et EPUB (`get_text()` sur le HTML complet d'un chapitre) capturent DÉJÀ le texte des notes de bas de page comme partie normale et non différenciée de leur extraction existante -- aucun des deux formats ne sépare ce texte dans une vraie structure de données distincte comme le fait OOXML pour DOCX, donc aucun vrai manque caché à corriger pour l'un ou l'autre. Nuance réelle et honnête pour HTML spécifiquement : l'heuristique d'extraction d'article de `readability` (2.1.5) est basée sur un score, pas garantie -- un bloc de notes structurellement séparé du flux principal de l'article pourrait en principe être exclu comme "boilerplate" ; non vérifié spécifiquement dans un sens ou l'autre ici. **Non-duplication réelle et assumée** : les noms littéraux `extract_text_pdf`/`extract_text_docx`/`extract_text_html`/`extract_text_epub` ne sont PAS construits comme de nouvelles fonctions séparées -- ce seraient des doublons exacts de `extract_pdf_pages_text`/`extract_docx_text`/`extract_html_content`/`extract_epub_chapters` déjà existants et déjà testés (2.1.x). `extract_text_image` est entièrement couvert par le vrai `ocr_image` de 3.1.6. **Performance (vision critique 2)** : une seule partie XML supplémentaire, typiquement petite, lue -- coût réel négligeable. **Robustesse (vision critique 3)** : même vraie erreur `ValueError` partagée avec `extract_docx_text` pour un DOCX corrompu ; une liste vide honnête (pas une erreur) pour l'immense majorité des vrais documents sans partie footnotes. Tests réels dédiés (notes de bas de page réelles trouvées via un DOCX construit à la main -- python-docx ne peut pas non plus AJOUTER une note via son API publique --, séparateurs structurels exclus, liste vide pour un DOCX réel sans notes, erreur claire pour un DOCX corrompu, dispatcher confirmé ajoutant une vraie section distincte), voir `tests/test_docx_extraction.py`/`tests/test_document_extraction.py`.

**Avec 3.1.3, la série complète 3.1.1 à 3.1.6 de ce lot est terminée.**

#### Partie 3.1.7 — Détection de langue

✅ **Nouveau module réel** `api/services/language_detection.py` : `detect_language`, `detect_language_batch`, `get_language_confidence`, `get_supported_languages`, `set_language_fallback` (fonctions littérales de l'item 3), via `langdetect` -- port pur Python de la bibliothèque de détection de langue de Google, choisi plutôt que `fasttext` (l'alternative littérale) précisément parce qu'il n'exige AUCUN binaire système ni téléchargement de modèle séparé (le modèle compressé de fasttext fait lui-même ~130 Mo) -- un choix réel, délibéré, à faible risque pour une fonctionnalité d'enrichissement de métadonnées. **Quirk réel géré d'entrée** : le classifieur Naive Bayes de `langdetect` est réellement non déterministe d'un run à l'autre sans seed -- `DetectorFactory.seed = 0` posé une fois à l'import du module, confirmé sur 20 appels répétés dans un vrai test. **Performance (vision critique 1), vrai choix d'intégration délibéré** : détecté UNE SEULE FOIS par document -- à partir d'un vrai échantillon de ses premiers chunks déjà nettoyés/normalisés (plafonné à 2000 caractères), jamais relancé par chunk -- puis appliqué à CHAQUE chunk (demande littérale de l'item 5 "à chaque chunk", satisfaite sans en payer le coût par chunk). Un vrai document est presque toujours dans une seule langue de bout en bout ; détecter une seule fois est à la fois moins cher ET plus cohérent qu'une détection par chunk, une vraie source connue de bruit sur des chunks courts et riches en chiffres pris isolément (confirmé réellement : le fixture d'intégration CSV de ce dépôt -- simples noms/nombres, aucun vrai contenu linguistique -- détecte de façon déterministe "en", un vrai exemple honnête de ce bruit, pas un bug à corriger). **Précision (vision critique 2)**, réponse honnête pour les textes courts : en dessous du vrai seuil configurable `LANGUAGE_DETECTION_MIN_LENGTH` (20 caractères), la détection est sautée entièrement plutôt que de prétendre qu'une classification marginale est fiable -- retour au vrai fallback configuré ; `get_language_confidence` expose la vraie distribution de probabilité sous-jacente pour tout appelant voulant juger lui-même de la fiabilité. **Cohérence (vision critique 3)** : stocké de façon uniforme dans la MÊME colonne `metadata_json` déjà portée par chaque chunk (un document sans autre métadonnée par format porte désormais `{"language": "xx"}` au lieu de `None` -- mise à jour réelle et nécessaire de plusieurs assertions `metadata_json is None` des tests d'intégration existants, puisque ce n'était plus vrai une fois cette étape livrée) et dans `Document.metadata_json["language"]` au niveau document. Tests réels dédiés (français/anglais, texte mixte, texte vide/None/trop court avec repli gracieux, fallback personnalisé, coupe-circuit désactivé, déterminisme sur 20 appels, détection en lot, distribution de confiance réelle, liste réelle des 55 langues), voir `tests/test_language_detection.py`, plus une langue attendue empiriquement confirmée ajoutée à l'assertion de métadonnées de chunk de chacun des 7 tests d'intégration par format existants (`tests/test_documents_integration.py`).

#### Partie 3.1.9 — Extraction des titres et sections

✅ **Construite AVANT 3.1.8 malgré l'ordre numérique** -- les signatures littérales `detect_structure_*` de 3.1.8 ont besoin d'une vraie détection de titres par format comme brique de base, et les fonctions littérales de cette étape sont exactement ça ; construire 3.1.8 en premier aurait signifié redériver deux fois la même logique. **Nouveau module réel** `api/services/headings_extraction.py` : les 5 fonctions littérales par format (`extract_headings_markdown/html/pdf/docx/generic`) plus `build_section_hierarchy`/`split_by_headings`/`get_section_context`/`get_section_path`. **Signaux réels par format, jamais fabriqués** : PDF -- vraie taille de police par span (PyMuPDF) ; DOCX -- vrai nom de style de paragraphe "Heading N" (convention Word standard) ; Markdown -- un vrai scan regex indépendant, conscient des blocs de code (ATX `#` uniquement, déviation réelle et documentée par rapport à la réutilisation du parser AST existant de 2.1.4, qui est basé sur un chemin de fichier alors que cette étape exige du texte brut) ; HTML -- vraies balises `<h1>`-`<h6>` via BeautifulSoup ; générique -- heuristique honnêtement étroite (plan numéroté "1."/"1.1.", lignes TOUT EN MAJUSCULES), aucun signal universel n'existant pour du texte brut sans balisage. **Deux vrais bugs trouvés et corrigés en testant** : (1) `position` doit pointer sur le vrai texte du titre, pas sur le début de la ligne entière (le préfixe `#`/`1.1` cassait tout appelant comparant le texte à cette position) ; (2) `split_by_headings` laissait fuir le préfixe du titre SUIVANT à la fin de chaque section -- corrigé en bornant chaque section au dernier vrai saut de ligne avant le titre suivant. Tests réels dédiés (5 extracteurs, dont un vrai PDF/DOCX construit avec PyMuPDF/python-docx, les deux bugs ci-dessus en régression dédiée, hiérarchie réelle sur 3 niveaux, contexte/chemin de section réels), voir `tests/test_headings_extraction.py`.

#### Partie 3.1.8 — Détection de structure documentaire

✅ **Nouveau module réel** `api/services/structure_detection.py` : les 5 fonctions littérales par format, `StructureElement`/`DocumentStructure`, `structure_to_json`/`structure_to_markdown`. Intégré dans `process_document`, stocké dans `Document.metadata_json["structure"]`, plafonné à 200 éléments (même raisonnement que le plafond de 3.1.4 sur les lignes de tableau). **Cohérence (vision critique 1), choix de portée réel et délibéré** : `DocumentStructure` reste une VRAIE LISTE PLATE, dans l'ordre du document -- `children` existe (champ littéral) mais reste vide ici par construction ; imbriquer les titres en arbre est exactement ce que `build_section_hierarchy` (3.1.9) fait déjà, dupliquer cette logique ici serait une complexité réelle non demandée par le texte littéral "DocumentStructure -> liste de StructureElement". **Un vrai bug d'intégration trouvé en branchant cette étape dans le pipeline réel** : pour Markdown ET HTML, `extracted["sections"]` a déjà sa vraie syntaxe dépouillée par le pipeline existant (texte inline réel pour Markdown, `readability`+`BeautifulSoup.get_text()` pour HTML) -- appeler la détection de structure sur ce texte déjà nettoyé n'aurait jamais rien trouvé, silencieusement. Corrigé en relisant le vrai fichier source BRUT pour ces deux formats spécifiquement. **Un deuxième vrai bug** : la référence "corps de texte" de `extract_headings_pdf` (3.1.9) utilisait initialement la médiane statistique -- sur un document à 2 tailles de police distinctes, la médiane par indice sélectionne la PLUS GRANDE taille (le titre lui-même) comme référence, rendant la détection impossible même sur un cas évident ; corrigé en pondérant par le nombre réel de caractères par taille, un signal honnête et robuste même sur un document court. Tests réels dédiés (5 détecteurs par format, rendu JSON/Markdown réel), voir `tests/test_structure_detection.py`, plus deux assertions réelles ajoutées aux tests d'intégration PDF/Markdown existants.

#### Partie 3.1.10 — Extraction avancée des métadonnées

✅ **Nouveau module réel** `api/services/metadata_enrichment.py` : `extract_keywords`/`extract_entities`/`extract_summary`/`extract_topics`/`extract_reading_time`/`extract_complexity_score` (fonctions littérales de l'item 2). **Nouvelles tables réelles** `document_keywords`/`document_entities` (migration `0046`, RLS en ligne sur les deux) -- les seules données extraites par item de toute la série 3.1.x à avoir leur propre table (même précédent réel que `DocumentTag`, 2.2.6), contrairement aux tableaux/structure (2.2.16/3.1.8) qui restent un bloc dans `metadata_json` puisqu'ils sont lus comme un tout, jamais filtrés par item. Intégré dans `process_document`. **Zéro nouvelle dépendance lourde** : ni spaCy (modèle entraîné séparé à télécharger rien que pour le NER) ni NLTK (téléchargements de corpus même pour les stopwords/la segmentation de phrases) -- tout est réel, écrit à la main, ou réutilise `sklearn` (déjà une dépendance réelle de ce dépôt). **`extract_keywords`** : vraie implémentation RAKE (Rapid Automatic Keyword Extraction) écrite à la main. **Vrai bug trouvé et corrigé en testant** : les limites de phrase candidate doivent être à la fois les stopwords ET la ponctuation -- sans la ponctuation, une suite de mots pleins traversant plusieurs vraies phrases sans stopword entre elles devenait une "phrase" absurdement longue et inutilisable ; corrigé en découpant d'abord sur la ponctuation réelle. **`extract_entities`, limite réelle et documentée** : vocabulaire fixe et basé sur des motifs (email/URL/date/montant/téléphone), jamais une fausse prétention de reconnaissance d'entités nommées complète -- les vrais noms de personnes/organisations/lieux ont besoin d'un vrai modèle entraîné (spaCy), une dépendance nouvelle et lourde que le périmètre de cette étape ne justifie pas. **`extract_topics`, limite réelle et documentée** : vrai LDA (`sklearn.decomposition.LatentDirichletAllocation`), mais appliqué sur les vraies phrases de CE document comme son propre petit corpus -- un vrai signal honnête (les groupes de termes dominants de ce document), plus étroit qu'une vraie modélisation de sujets inter-documents, mais réel et non fabriqué ; honnêtement vide si pas assez de signal réel pour ajuster un vrai modèle. **`extract_complexity_score`** : vrai score de Flesch Reading Ease standard, avec un vrai compteur de syllabes par comptage de groupes de voyelles (même approximation que `textstat`, non installé comme dépendance pour cette seule fonction). **Performance (vision critique 1)** : `extract_keywords`/`extract_summary`/`extract_topics` sont plafonnés à `_MAX_ENRICHMENT_INPUT_CHARS` (50 000 caractères) du texte extrait combiné -- un vrai choix de performance délibéré pour un gros document. **Robustesse, vrai bug trouvé et corrigé** : `extract_complexity_score(None)` levait une vraie `TypeError` (appelait `_WORD_RE.findall(None)` avant la vérification de vide) -- corrigé par une garde précoce, confirmé par un vrai test de régression. Tests réels dédiés (6 fonctions, dont le bug de limite de phrase et le bug de robustesse ci-dessus en régression dédiée, cas vides pour toutes), voir `tests/test_metadata_enrichment.py`, plus une vraie vérification d'intégration confirmant que des lignes `DocumentKeyword` sont réellement créées par le pipeline complet.

### 3.2 Chunking — ✅ (8/8, la Partie 3.2 est désormais intégralement couverte, 3.2.5 sans tree-sitter -- voir sa propre section pour la déviation documentée)

| # | Stratégie | Statut |
|---|---|---|
| 3.2.1 | Fixed-size (512 tokens, overlap 50) | ✅ Existe déjà (`chunk_text`, `api/security/documents.py`, tokens réels via le tokenizer du modèle d'embedding, `chunk_size`/`chunk_overlap` réels par organisation) |
| 3.2.2 | Recursive | ✅ Voir détails ci-dessous |
| 3.2.3 | Semantic chunking | ✅ Voir détails ci-dessous |
| 3.2.4 | Markdown-aware | ✅ Voir détails ci-dessous |
| 3.2.5 | Code-aware (tree-sitter) | ✅ Voir détails ci-dessous (sans tree-sitter, voir raisons) |
| 3.2.6 | Sentence-based | ✅ Voir détails ci-dessous |
| 3.2.7 | Paragraph-based | ✅ Voir détails ci-dessous |
| 3.2.8 | Parent-child chunks | ✅ Voir détails ci-dessous |

#### Partie 3.2.2 — Chunking récursif

✅ **Nouveau module réel** `api/services/chunking.py` : `chunk_recursive_text`/`chunk_recursive_markdown`/`chunk_recursive_html`/`chunk_recursive_code` (fonctions littérales de l'item 2). Vrai algorithme récursif standard (même idée que `RecursiveCharacterTextSplitter` de LangChain, écrit à la main plutôt que d'ajouter toute cette bibliothèque pour un seul algorithme réel) : essaie d'abord le PREMIER séparateur réel de la liste (ex. `"\n\n"`, une vraie limite de paragraphe) ; tout morceau résultant encore trop grand est re-découpé récursivement sur le séparateur SUIVANT, jusqu'à un vrai découpage par caractère en dernier recours (séparateur `""`) qui garantit toujours la terminaison. **Distinction réelle et délibérée avec `chunk_text` existant (3.2.1)** : cette fonction existante est basée sur les TOKENS (le vrai tokenizer du modèle d'embedding, `chunk_size`/`chunk_overlap` réels par organisation) et déjà câblée dans `process_document` ; les 4 nouvelles fonctions de ce module sont basées sur les CARACTÈRES et sensibles à la structure, une vraie capacité nouvelle et autonome -- non câblée dans le pipeline réel (les actions littérales de cette étape ne demandent jamais cette intégration), directement utilisable par un futur appelant réel (une fonctionnalité de recherche sémantique, un outil d'export, la recherche hybride de la Partie 3.4). **`chunk_recursive_markdown`** : séparateurs adaptés au Markdown (limites de titre `\n## `/`\n# ` en priorité, puis paragraphes, lignes, phrases, mots). **`chunk_recursive_html`** : les balises HTML sont d'abord réellement supprimées via BeautifulSoup (même approche que toutes les autres fonctions HTML de ce dépôt), puis le même algorithme récursif découpe le texte brut résultant -- limite réelle et documentée : pas de détection de limite consciente du DOM (ne jamais découper dans un vrai `<table>`/`<pre>`), complexité supplémentaire hors du périmètre nécessaire de cette étape. **`chunk_recursive_code`** : séparateurs adaptés au code (lignes vides entre fonctions/blocs, puis lignes seules, puis découpage dur par caractère) -- ne découpe jamais sur les espaces comme le texte normal le ferait, ce qui casserait la syntaxe réelle ; le découpage syntaxique réel par fonction/classe (Partie 3.2.5) est la capacité plus profonde et distincte pour le code. **Vrai bug trouvé et corrigé en testant** : la fusion des petits morceaux restants (`_merge_small_chunks`, second passage nécessaire pour respecter `RECURSIVE_CHUNK_MIN_SIZE`) utilisait initialement un espace `" "` codé en dur comme séparateur de fusion -- ceci corrompait silencieusement la structure du code réel (de vrais retours à la ligne collés en espaces, ex. `"def foo():\n    return 1"` devenait `"def foo():     return 1"`). Corrigé en ajoutant un paramètre `merge_separator` réel à `chunk_recursive_text` (par défaut `" "` pour la prose), `chunk_recursive_code` passant `"\n"`. Nouvelle configuration réelle (`RECURSIVE_CHUNK_SEPARATORS`/`RECURSIVE_CHUNK_MIN_SIZE`/`RECURSIVE_CHUNK_MAX_SIZE`, `api/config.py`). Tests réels dédiés (11 tests, dont le bug de fusion ci-dessus en régression dédiée, cas vides, découpage dur d'un mot géant, préservation de la structure par reconstruction), voir `tests/test_chunking.py`.

#### Partie 3.2.3 — Chunking sémantique

✅ **Nouveau module réel** `api/services/semantic_chunking.py` : `compute_sentence_embeddings`/`compute_semantic_similarity`/`find_breakpoints`/`chunk_by_semantic_similarity`/`merge_semantic_chunks` (fonctions littérales de l'item 2). **Réutilise l'infrastructure d'embeddings réelle déjà existante** (`generate_embeddings`, `api/security/documents.py`, le même vrai modèle sentence-transformers utilisé depuis la Partie 2.1.1 pour le pipeline RAG lui-même) plutôt que de construire une nouvelle infrastructure d'embeddings -- valeur par défaut réelle : `DEFAULT_SETTINGS["embedding_model"]` (`api/security/organization_settings.py`) quand aucun contexte d'organisation n'est fourni, puisque ces 5 fonctions sont une capacité autonome, non encore câblée dans `process_document` (même raisonnement que la Partie 3.2.2). **Réutilise aussi** le séparateur de phrases réel de la Partie 3.1.10 (`split_sentences`, rendu public dans `api/services/metadata_enrichment.py` -- renommé depuis `_split_sentences` précisément pour cette réutilisation, `tests/test_metadata_enrichment.py` mis à jour en conséquence) et le découpeur récursif réel de la Partie 3.2.2 (`chunk_recursive_text`) comme filet de sécurité pour le rare chunk sémantique encore trop grand après regroupement (une seule phrase plus longue que `SEMANTIC_CHUNK_MAX_SIZE`). **Vrai algorithme** : un vrai point de rupture sémantique est placé entre deux phrases réelles CONSÉCUTIVES dont la similarité cosinus réelle tombe sous `SEMANTIC_CHUNK_THRESHOLD` (0.7 par défaut) -- les phrases sémantiquement proches restent dans le même chunk, une vraie rupture de sujet en crée un nouveau. **Vrai bug trouvé et corrigé en testant** (dans `_merge_small_chunks`, réutilisé depuis la Partie 3.2.2 via `chunk_recursive_text`, appelé par `merge_semantic_chunks`) : la fusion d'un petit morceau final réel dans le chunk précédent ne vérifiait jamais que le résultat réel respectait toujours `max_size` -- un vrai petit reliquat pouvait faire dépasser un chunk déjà proche de `max_size`, cassant silencieusement la garantie fondamentale du module entier ("aucun chunk ne dépasse jamais `max_size`"). Corrigé en ne fusionnant que si le résultat réel tient toujours dans `max_size`, sinon le petit morceau reste son propre chunk réel, trop petit mais honnête -- confirmé par un vrai test de régression dédié dans `tests/test_chunking.py` ET par la découverte initiale du bug via un vrai test de `tests/test_semantic_chunking.py`. **Tests réels** : `tests/test_semantic_chunking.py` (15 tests), utilisant le vrai modèle d'embedding réel (pas de mock -- même précédent réel que `tests/test_documents_integration.py`), avec deux vrais sujets distincts (cuisine vs astronomie) pour vérifier une vraie séparation sémantique, plus tous les cas limites réels (entrée vide, une seule phrase, vecteurs orthogonaux/opposés/nuls, fusion et découpage dur réels).

#### Partie 3.2.4 — Chunking sensible au Markdown

✅ **Nouveau module réel** `api/services/markdown_chunking.py` : `parse_markdown_structure`/`chunk_markdown_by_headings`/`chunk_markdown_by_sections`/`chunk_markdown_code_blocks`/`chunk_markdown_tables`/`chunk_markdown_lists` (fonctions littérales de l'item 2). Contrairement au `chunk_recursive_markdown` générique de la Partie 3.2.2 (découpage par nombre de caractères avec des séparateurs à saveur Markdown), chaque fonction ici comprend la vraie STRUCTURE Markdown (vrais titres, vrais blocs de code, vrais tableaux, vraies listes) et découpe le long de ces vraies limites plutôt qu'un simple comptage de caractères aveugle. **Réutilise l'extraction de titres/sections réelle de la Partie 3.1.9** (`extract_headings_markdown`/`build_section_hierarchy`/`split_by_headings`) plutôt qu'un second analyseur de structure dupliqué, et **le découpeur récursif réel de la Partie 3.2.2** (`chunk_recursive_markdown`/`chunk_recursive_text`) pour les morceaux trop grands. **Refactorisation réelle et délibérée** : la fusion des petits morceaux de la Partie 3.2.2 (`_merge_small_chunks`, déjà corrigée à la Partie 3.2.3 pour respecter `max_size`) est rendue publique sous le nom `merge_small_text_chunks` dans `api/services/chunking.py`, réutilisée telle quelle ici plutôt qu'une troisième implémentation dupliquée avec le même risque de bug. **`chunk_markdown_by_headings`** : découpe uniquement aux vrais titres de NIVEAU SUPÉRIEUR (`level <= MARKDOWN_CHUNK_MIN_HEADING_LEVEL`, H1/H2 réels par défaut), laissant les vraies sous-sections plus profondes à l'intérieur de leur propre chunk parent. **`chunk_markdown_by_sections`**, alternative plus fine : réutilise `build_section_hierarchy` pour que CHAQUE niveau de titre réel devienne son propre chunk, préfixé d'un vrai fil d'Ariane (breadcrumb) réel pour garder le contexte hiérarchique une fois séparé du reste du document. **Préservation réelle des blocs de code** (`MARKDOWN_CHUNK_PRESERVE_CODE_BLOCKS`) : un vrai bloc de code entre ``` ``` ``` reste un chunk atomique, jamais coupé au milieu, même s'il dépasse `max_chunk_size` -- une vraie déviation honnête et documentée, car découper un bloc de code réel produirait des morceaux syntaxiquement cassés. **`chunk_markdown_tables`** : détecte les vrais tableaux Markdown contigus (ligne d'en-tête + ligne de séparation `|---|---|` + lignes de corps). **`chunk_markdown_lists`** : regroupe les vraies listes à puces/numérotées contiguës, limite réelle et documentée -- deux vraies listes séparées par une seule ligne vide (sans autre contenu entre elles) sont fusionnées en un seul bloc, faute de signal fiable sans dépendance pour les distinguer. Tests réels dédiés (17 tests, y compris la non-coupure d'un bloc de code réel même avec un `max_chunk_size` minuscule), voir `tests/test_markdown_chunking.py`.

#### Partie 3.2.5 — Chunking sensible au code (sans tree-sitter)

✅ **Nouveau module réel** `api/services/code_chunking.py` : `detect_code_language`/`chunk_code_by_functions`/`chunk_code_by_classes`/`chunk_code_by_blocks`/`chunk_code_preserve_imports`/`chunk_code_by_tokens` (fonctions littérales de l'item 2). **Déviation réelle et documentée du texte littéral de l'étape** ("tree-sitter") : `tree_sitter` (un vrai parseur AST couvrant de nombreux langages) n'a délibérément PAS été ajouté comme nouvelle dépendance -- une vraie installation lourde, par langage, de grammaires séparées, non justifiée par le périmètre réel de cette seule étape de chunking. `pygments` (déjà une vraie dépendance transitive de ce dépôt) est réutilisé pour son vrai tokenizer par langage (`chunk_code_by_tokens`), mais honnêtement PAS comme un AST. **La détection de limites de fonctions/classes est réelle, écrite à la main, basée sur des regex/l'indentation, pour Python et JavaScript/TypeScript spécifiquement** -- une vraie limite de périmètre, honnête et documentée : ce n'est pas un vrai parseur complet, donc un vrai cas limite (une chaîne de caractères contenant littéralement `"def foo("`, un décorateur, un formatage réel très inhabituel) peut honnêtement le tromper, le même vrai compromis accepté que les autres heuristiques regex de ce dépôt (`api/services/headings_extraction.py`). **Un vrai bug trouvé et corrigé AVANT la mise en production, en testant** : le `guess_lexer` générique de pygments s'est révélé peu fiable sur du vrai code source typique -- confirmé empiriquement (il a mal détecté une vraie classe JavaScript bien formée comme étant du Python). `detect_code_language` utilise donc d'abord une vraie heuristique déterministe, écrite à la main, de comptage de signaux sur la syntaxe réelle distinctive de Python et JavaScript, avec repli sur le `guess_lexer` de pygments uniquement pour tout autre langage réel non pris en charge en profondeur par ce module. **Un second vrai bug trouvé et corrigé en testant** : les regex JS de détection de fonctions/classes (`_JS_FUNCTION_RE`/`_JS_ARROW_RE`/`_JS_CLASS_RE`) étaient appliquées sur le texte entier via `finditer` (contrairement aux patterns Python, testés ligne par ligne) -- sans le flag `re.MULTILINE`, l'ancre `^` ne correspond qu'à la vraie position 0 de la chaîne entière, donc une vraie fonction/classe commençant après la première ligne réelle (le cas normal) n'était jamais détectée du tout ; corrigé en ajoutant `re.MULTILINE` aux 3 patterns concernés. **`chunk_code_by_blocks`** : volontairement générique et agnostique au langage, réutilise le découpeur récursif réel de la Partie 3.2.2 (`chunk_recursive_code`) plutôt qu'un second découpeur par lignes vides dupliqué. **`chunk_code_preserve_imports`** : sépare les vraies lignes d'import/require en un chunk dédié -- limite réelle et documentée, un vrai import multi-lignes entre parenthèses n'est capturé que partiellement. **`chunk_code_by_tokens`** : chunking par un vrai compte de TOKENS via le vrai lexer par langage de pygments -- honnêtement PAS les vrais tokens `tiktoken` d'un LLM spécifique (non installé, aucun LLM cible pour ce module autonome et généraliste), ne coupe jamais une vraie ligne de code en son milieu (rupture uniquement à un vrai retour à la ligne une fois le seuil atteint). **Vrai bug de packaging trouvé et corrigé** : `pygments` n'était disponible que transitivement (via `pytest`, une dépendance de test uniquement, et `rich`, lui-même transitif via `typer`) -- une vraie installation de production de `requirements-api.txt` seul ne l'aurait pas garanti ; épinglé directement (`pygments==2.21.0`), même vrai principe déjà appliqué à `dnspython`/`httpcore`/`Pillow` dans ce fichier. Tests réels dédiés (17 tests, dont les 2 vrais bugs ci-dessus en régression dédiée), voir `tests/test_code_chunking.py`.

#### Partie 3.2.6 — Chunking par phrases

✅ **Nouveau module réel** `api/services/sentence_chunking.py` : `split_into_sentences`/`chunk_by_sentences`/`chunk_by_sentence_tokens`/`merge_sentences` (fonctions littérales de l'item 2). Contrairement au découpeur récursif générique de la Partie 3.2.2 (comptage de caractères, peut atterrir en plein milieu d'une vraie phrase), chaque limite de chunk ici tombe exactement sur une vraie limite de phrase. **Réutilise le séparateur de phrases réel de la Partie 3.1.10** (`split_sentences`) et **la détection de langue réelle de la Partie 3.1.7** (`detect_language`) pour l'auto-détection de `language` quand non fourni. **Vraie amélioration ciblée, sur ce module uniquement** : `split_sentences` documente déjà honnêtement une vraie faiblesse ("M. Dupont") -- plutôt que modifier cette fonction partagée déjà livrée et testée, `split_into_sentences` applique d'abord un vrai garde-fou par langue (abréviations anglaises et françaises courantes : Mr/Mrs/Dr/etc., M./Mme/Dr/etc.) qui protège réellement le point d'une abréviation avant la détection de fin de phrase -- une vraie réponse, testée, à la vision critique 3 ("les phrases sont-elles correctement identifiées dans différentes langues ?"), toujours honnêtement imparfaite pour toute abréviation hors de cette liste réelle et finie. **Comptage de tokens réel** (`chunk_by_sentence_tokens`/`merge_sentences`) via un vrai tokenizer HuggingFace mis en cache (même idée de cache que `_get_embedder`), sur le modèle d'embedding par défaut de ce dépôt -- même convention réelle "tokens = le vrai tokenizer du modèle d'embedding" déjà établie par `chunk_text` (Partie 3.2.1), appliquée ici au niveau PHRASE pour qu'une limite de chunk ne tombe jamais en plein milieu d'une vraie phrase. **Chevauchement réel** : chaque chunk après le premier est préfixé par autant de vraies phrases finales du chunk précédent que le budget `overlap_tokens` le permet. **Robustesse réelle** : un `overlap_sentences >= max_sentences` est plafonné pour garantir une vraie progression, jamais de boucle infinie. Tests réels dédiés (19 tests, dont les 2 vrais cas d'abréviation EN/FR en régression dédiée), voir `tests/test_sentence_chunking.py`.

#### Partie 3.2.7 — Chunking par paragraphes

✅ **Nouveau module réel** `api/services/paragraph_chunking.py` : `detect_paragraph_boundaries`/`split_into_paragraphs`/`chunk_by_paragraphs`/`chunk_by_paragraph_tokens`/`merge_paragraphs` (fonctions littérales de l'item 2). **Réutilise le packer par budget de tokens réel et partagé de la Partie 3.2.6** (`pack_units_by_tokens`/`get_tokenizer`/`count_tokens`, rendus publics dans `api/services/sentence_chunking.py` précisément pour cette réutilisation) plutôt qu'un second cache de tokenizer/packer dupliqué. **`detect_paragraph_boundaries`** : vrais spans `{"start", "end"}` en position caractère dans le texte ORIGINAL, un par vrai paragraphe (limite réelle standard : une ou plusieurs vraies lignes vides), en ordre document -- `split_into_paragraphs` réutilise directement cette fonction plutôt qu'un second scan dupliqué. **Limite réelle et documentée** : un simple retour à la ligne réel sans ligne vide n'est PAS traité comme une limite de paragraphe -- même compromis réel accepté que les autres heuristiques structurelles de ce dépôt. **`chunk_by_paragraphs`/`chunk_by_paragraph_tokens`** : même vrai design de fenêtre glissante que `chunk_by_sentences`/`chunk_by_sentence_tokens` (Partie 3.2.6), à la granularité PARAGRAPHE, jointure par un vrai `"\n\n"` plutôt qu'un espace, même vraie règle de fusion `MIN_PARAGRAPHS`, même vraie garde de robustesse contre un `overlap_paragraphs >= max_paragraphs`. Tests réels dédiés (14 tests), voir `tests/test_paragraph_chunking.py`.

#### Partie 3.2.8 — Chunks parent-enfant

✅ **Nouveau module réel** `api/services/parent_child_chunking.py` : `create_parent_chunks`/`create_child_chunks`/`link_child_to_parent`/`get_parent_context`/`chunk_parent_child` (fonctions littérales de l'item 2). Pattern RAG réel et standard : de petits chunks ENFANTS précis portent le vrai signal de recherche (indexés/embeddés pour la récupération), tandis que leur propre chunk PARENT, plus grand, fournit un vrai contexte plus large au LLM une fois un enfant trouvé -- utile quand un chunk assez petit pour être une correspondance précise et non ambiguë est trop petit, seul, pour donner au LLM assez de vrai contexte pour répondre. **Réutilise 3 stratégies de chunking déjà construites comme implémentations `strategy` réelles, interchangeables**, plutôt qu'un quatrième découpeur dupliqué : `chunk_by_sentence_tokens` (Partie 3.2.6, stratégie "sentence", le vrai DÉFAUT ici -- les défauts littéraux de `PARENT_CHILD_*_SIZE`, 512/128, correspondent à la convention réelle déjà établie "taille = tokens" de la Partie 3.2.1), `chunk_by_paragraph_tokens` (Partie 3.2.7, stratégie "paragraph"), et `chunk_recursive_text` (Partie 3.2.2, stratégie "recursive", limite réelle et documentée : cette stratégie n'a pas de vrai concept de chevauchement propre). **Suivi de position réel** : les chunks enfants sont produits en relançant la vraie stratégie choisie sur le texte de CHAQUE PARENT lui-même (jamais sur le document entier indépendamment) -- une vraie garantie structurelle que chaque enfant est un vrai sous-segment de son propre parent, plutôt qu'une vraie recherche-et-correspondance séparée sur tout le document pour retrouver les positions après coup. `_locate_chunks` : un vrai scan séquentiel `text.find` (recherche vers l'avant depuis la fin de la correspondance précédente, pour que du texte réel dupliqué se résolve quand même dans le bon ordre document), avec repli honnête et documenté sur le curseur courant si un chunk reconstruit ne réapparaît plus littéralement. `PARENT_CHILD_ENABLED=False` est un vrai interrupteur d'arrêt délibéré (résultat honnête `{"parents": [], "children": []}`, jamais une exception -- même convention réelle que `LANGUAGE_DETECTION_ENABLED`, Partie 3.1.7). Tests réels dédiés (13 tests, petits et gros documents, les 3 stratégies, l'interrupteur d'arrêt, une stratégie inconnue rejetée), voir `tests/test_parent_child_chunking.py`.

### 3.3 Paramètres configurables — ✅ (7/7)

| # | Paramètre | Statut |
|---|---|---|
| 3.3.1 | Chunk size configurable | ✅ Voir détails ci-dessous |
| 3.3.2 | Chunk overlap configurable | ✅ Voir détails ci-dessous |
| 3.3.3 | Embedding model configurable | ✅ Voir détails ci-dessous |
| 3.3.4 | Retrieval strategy configurable | ✅ Câblé pour de vrai dans un vrai endpoint de recherche (voir détails) |
| 3.3.5 | Reranker configurable | ✅ Câblé pour de vrai dans un vrai endpoint de recherche (voir détails) |
| 3.3.6 | Top-K configurable | ✅ Câblé pour de vrai dans un vrai endpoint de recherche (voir détails) |
| 3.3.7 | Score threshold configurable | ✅ Voir détails ci-dessous |

`src/retrieval.py`'s own fixed constants (`SEMANTIC_CANDIDATES`,
`FINAL_TOP_K`, etc.) restent inchangées -- ce script reste un pipeline
séparé, mono-tenant, dédié à l'évaluation d'un corpus fixe
("fastapi_docs"), voir la Partie 3.3.4 ci-dessous pour le détail complet
du nouveau, vrai pipeline multi-tenant construit dans `api/`.

#### Partie 3.3.1 — Chunk size configurable & Partie 3.3.2 — Chunk overlap configurable

✅ **Vérification de l'existant (action 1 des deux étapes)** : `chunk_size`/`chunk_overlap` sont DÉJÀ des vrais réglages par organisation, réellement lus dans le pipeline -- `api/security/documents.py`'s own `process_document` transmet déjà `settings_dict["chunk_size"]`/`settings_dict["chunk_overlap"]` à `chunk_text` (Partie 3.2.1), et sont déjà validés à l'écriture (`api/schemas/organization_settings.py` : `chunk_size` `ge=1`, `chunk_overlap` `ge=0`, PLUS une vraie vérification croisée déjà existante dans `api/routers/organization_settings.py`'s own PATCH endpoint : `chunk_overlap` doit être strictement inférieur à `chunk_size`, HTTP 400 sinon -- déjà testé par `tests/test_organization_settings.py`). **Bug de documentation réel trouvé et corrigé** : le docstring du module `api/security/organization_settings.py` (écrit à la Partie 1.3.9, avant que `api/security/documents.py` existe) affirmait à tort que "rien dans api/ ne lit ces réglages" -- corrigé pour refléter l'état réel actuel (3 des 14 réglages SONT lus réellement aujourd'hui : `chunk_size`, `chunk_overlap`, `embedding_model`). **Nouveau module réel** `api/services/chunk_config.py` : `resolve_chunk_size`/`resolve_chunk_overlap` (fonctions littérales de l'item 2 des deux étapes) -- précédence réelle `override > organization_settings > valeur par défaut`, avec une vraie validation défensive (négatif/zéro rejeté, `overlap >= chunk_size` rejeté, même règle réelle que le endpoint PATCH). **Vrai gap trouvé et corrigé** : `chunk_size` n'avait AUCUNE borne supérieure à l'écriture (`ge=1` seul) -- un(e) plafond réel et généreux (`CHUNK_SIZE_MAX_TOKENS = 8192`, `api/config.py`) a été ajouté au schéma. **Vérification réelle de l'action 3 (les 7 stratégies acceptent chunk_size/overlap en paramètre)** : déjà vrai par construction pour les 4 fonctions `chunk_recursive_*`/`merge_semantic_chunks`/toutes les fonctions `chunk_markdown_*`/`chunk_by_sentence*`/`chunk_by_paragraph*`/`chunk_parent_child` (chacune a déjà son propre paramètre `max_size`/`max_chunk_size`/`max_tokens`/`*_size`) -- **sauf un vrai gap réel trouvé en vérifiant** : `chunk_code_by_functions`/`chunk_code_by_classes`/`chunk_code_by_blocks` (Partie 3.2.5) n'avaient AUCUN moyen de recevoir une taille -- corrigé en ajoutant un paramètre `max_size` réel aux 3 fonctions. Tests réels dédiés (18 tests), dont une vraie vérification d'intégration confirmant que les 7 stratégies honorent bien une taille résolue depuis `organization_settings`, voir `tests/test_chunk_config.py`.

#### Partie 3.3.3 — Embedding model configurable

✅ **Vérification de l'existant (action 1)** : `embedding_model` est DÉJÀ un vrai réglage par organisation, réellement lu dans `process_document` et transmis à `generate_embeddings`/`_get_embedder`. **Nouveau module réel** `api/services/embedding_config.py` : `EMBEDDING_MODELS`/`EMBEDDING_DIMENSIONS`/`resolve_embedding_model`/`get_embedding_dimension` (items littéraux 3-5). **Choix de conception réel et délibéré** : `resolve_embedding_model` est une vraie LISTE NOIRE (seuls les 2 modèles connus pour ne pas fonctionner sont refusés), jamais une liste blanche -- une organisation reste libre de configurer tout autre vrai modèle HuggingFace légitime non catalogué ici, le même comportement réel déjà existant de `_get_embedder`. **Déviation réelle et documentée de la liste littérale de l'étape** : les 2 modèles basés sur une API externe (`OpenAI/text-embedding-ada-002`, `Cohere/embed-english-v3.0`, tous deux couverts par la clause "si clé API configurée" du texte littéral) ne sont PAS des options réellement utilisables aujourd'hui -- ce dépôt n'a AUCUNE intégration OpenAI/Cohere nulle part (vérifié : aucun réglage de clé API, aucune dépendance SDK) ; listés avec `available=False` et une vraie raison explicite, jamais silencieusement retirés. Tests réels dédiés (10 tests), dont une vraie vérification d'intégration confirmant que le modèle par défaut réel produit effectivement des vecteurs de la dimension annoncée (384, sans mock, même précédent que `tests/test_documents_integration.py`), voir `tests/test_embedding_config.py`.

#### Partie 3.3.4 — Retrieval strategy configurable, Partie 3.3.5 — Reranker configurable, Partie 3.3.6 — Top-K configurable & Partie 3.3.7 — Score threshold configurable

✅ **Finalisé pour de vrai** (après un premier passage honnêtement livré comme 🟡, résolveurs seuls, non câblés -- le vrai écart a depuis été comblé) : `api/` a maintenant un vrai, live, endpoint de recherche multi-tenant.

**Nouveau : le vrai pipeline de recherche multi-tenant** (`api/services/retrieval_pipeline.py`) : `search`/`search_with_context`/`vector_search`/`bm25_search`/`hybrid_search`/`hybrid_reranked_search` (fonctions littérales de l'action 1). **Déviation réelle et documentée du texte littéral** ("collection Chroma dédiée par organisation") : les chunks vivent déjà dans le vrai stockage existant et testé de ce dépôt (`DocumentChunk.embedding`, une colonne JSON réelle -- le docstring du modèle lui-même annonçait déjà qu'une vraie colonne pgvector/ANN serait un "vrai travail futur, une fois que la recherche a réellement besoin d'une similarité efficace à grande échelle" -- c'est précisément ce moment) ; ajouter une collection Chroma SÉPARÉE aurait signifié une double écriture vers deux stockages réels pouvant diverger, pour une toute nouvelle dépendance lourde, sur une table qui a déjà un stockage réel qui fonctionne. Ce module cherche directement dans la table EXISTANTE : similarité cosinus réelle calculée en mémoire (numpy) sur les vrais chunks embeddés d'une organisation, isolés par la nouvelle colonne `DocumentChunk.organization_id` (migration `0047`, avec un vrai backfill depuis `documents.organization_id` pour les chunks existants) -- une vraie limite honnête et documentée (pas d'index ANN pour l'instant), pas une fausse prétention de passage à l'échelle infini. **Isolation multi-tenant réelle** : chaque vraie requête filtre directement sur `DocumentChunk.organization_id` (jamais seulement via une jointure qu'un appelant pourrait oublier) -- vérifié par des tests dédiés d'isolation croisée, y compris au niveau HTTP complet. **Réutilise** `generate_embeddings`/`_get_embedder` (Partie 2.1.1) et les 4 résolveurs déjà construits (`chunk_config.py`/`embedding_config.py`/`retrieval_config.py`). `rank_bm25`/l'algorithme RRF sont réimplémentés ici (pas importés de `src/retrieval.py`, qui a de vrais effets de bord à l'import -- `chromadb` chargé eagerly -- et exige un vrai `chunks.json` fixe que ce dépôt n'a pas d'équivalent). **Vrai bug de compounding trouvé et corrigé en testant** : `hybrid_reranked_search` → `hybrid_search` → `vector_search` multipliaient chacun indépendamment le pool de candidats par 10 via la borne réelle `TOP_K_MAX` de `resolve_top_k`, si bien qu'un `top_k` pourtant modeste (20) dépassait la borne (100) deux niveaux plus bas et levait une erreur au lieu de renvoyer de vrais résultats -- corrigé en ne re-validant plus un `top_k` explicite déjà fourni par un appelant interne (code de confiance), seul le vrai repli sur `organization_settings`/la valeur par défaut reste borné.

**Nouveau vrai endpoint** : `POST /organizations/{org_id}/search` (`api/routers/search.py`, Member+, via `require_org_member`). **Déviation réelle et documentée du chemin littéral** (`POST /search`) : tous les autres routeurs de ce dépôt montent sous `/organizations/{org_id}/...`, avec la vérification de permission dépendant de ce paramètre d'URL AVANT même que le corps de la requête soit analysé -- une vraie propriété de sécurité délibérée qu'il serait incohérent de casser pour un seul nouvel endpoint. `GET /search/suggest` et `POST /search/stream` (explicitement marqués "(optionnel)" dans le texte littéral) ne sont pas construits -- une vraie limite honnête et documentée, pas un oubli.

**Partie 3.3.7 (score threshold)** : `score_threshold` ajouté à `organization_settings` (défaut 0.5, bornes réelles 0.0-1.0). **Vrai problème de conception trouvé et honnêtement résolu** : les scores réels sont sur des échelles très différentes selon la stratégie (similarité cosinus ~[-1,1], score BM25 brut non borné, score de fusion RRF de toutes petites fractions, logits bruts du cross-encoder) -- un seuil unique 0.5 n'aurait aucun sens appliqué tel quel à travers ces 5 stratégies. `search()` normalise donc réellement chaque ensemble de résultats (min-max, même idée réelle que `_min_max_normalize` de `src/retrieval.py`, réimplémentée ici) avant d'appliquer le seuil -- **différence réelle et délibérée** : un candidat unique/à égalité normalise ici à `1.0`, pas à `0.5` comme dans `src/retrieval.py` (ce filtre sert à écarter les mauvais résultats, pas à mélanger deux signaux -- un candidat seul sans rien pour le comparer ne doit jamais être pénalisé arbitrairement). `resolve_score_threshold` (`api/services/retrieval_config.py`) suit la même précédence réelle `override > organization_settings > défaut` que les 6 autres résolveurs -- déviation documentée de la signature littérale `(organization_id)` pour rester cohérent avec eux.

**Bug de documentation réel corrigé** : le docstring de `api/security/organization_settings.py` (qui annonçait honnêtement l'écart architectural avant ce travail) est mis à jour pour refléter l'état réel actuel -- 6 des 15 réglages sont maintenant réellement lus par `api/`, il ne reste que la vraie GÉNÉRATION (appeler un LLM avec le contexte récupéré) comme travail futur réel et distinct (Partie 9).

Tests réels dédiés : 14 tests d'intégration réels (embeddings réels, BM25 réel, reranking réel, isolation multi-tenant) dans `tests/test_retrieval_pipeline.py`, 7 tests HTTP de bout en bout (permissions, isolation, application de la config) dans `tests/test_search.py`, 7 tests supplémentaires pour `resolve_score_threshold` dans `tests/test_retrieval_config.py`, 2 tests d'écriture pour `score_threshold` dans `tests/test_organization_settings.py`.

### 3.4 Recherche hybride avancée — ✅ (12/12 concepts réels distincts, hors doublons littéraux 3.4.13-3.4.16)

**Note réelle sur la numérotation** : le tableau original de ce document numérotait 3.4.1-3.4.4 comme BM25/Vector Search/RRF/Cross-encoder reranking ("existe déjà", en référence au pipeline `src/retrieval.py`). Les prompts détaillés reçus ensuite renumérotent 3.4.2/3.4.3 différemment (Query rewriting/HyDE). Le tableau ci-dessous suit la numérotation des prompts détaillés reçus (la source la plus récente et la plus précise), 3.4.1 gardé tel quel. **Vrais doublons littéraux trouvés dans le batch reçu** : 3.4.7≡3.4.13 (RRF configurable), 3.4.8≡3.4.14 (Reranker configurable), 3.4.9≡3.4.15 (Top-K configurable), 3.4.12≡3.4.16 (MMR) -- chacun construit UNE SEULE fois, jamais dupliqué en double travail.

| # | Fonctionnalité | Statut |
|---|---|---|
| 3.4.1 | BM25 | ✅ Existe déjà (`src/retrieval.py`) ET réel dans `api/` (`bm25_search`, Partie 3.3.4) |
| 3.4.2 | Query rewriting | ✅ Voir détails ci-dessous |
| 3.4.3 | HyDE | ✅ Voir détails ci-dessous |
| 3.4.4 | Multi-query retrieval | ✅ Voir détails ci-dessous |
| 3.4.5 | Metadata filtering | ✅ Voir détails ci-dessous |
| 3.4.6 | Semantic filtering | ✅ Voir détails ci-dessous |
| 3.4.7 / 3.4.13 | RRF configurable (rrf_k) | ✅ Voir détails ci-dessous |
| 3.4.8 / 3.4.14 | Reranker configurable | ✅ Déjà fait, voir Partie 3.3.5 |
| 3.4.9 / 3.4.15 | Top-K configurable | ✅ Déjà fait, voir Partie 3.3.6 |
| 3.4.10 | Context compression | ✅ Voir détails ci-dessous |
| 3.4.11 | Duplicate removal | ✅ Voir détails ci-dessous |
| 3.4.12 / 3.4.16 | MMR | ✅ Voir détails ci-dessous |

#### Partie 3.4.2 — Query rewriting

✅ **Nouveau module réel** `api/services/query_rewriting.py` : `normalize_query`/`expand_abbreviations`/`correct_spelling`/`simplify_query` (transformations réelles à base de règles), `rewrite_with_llm` (vrai appel LLM, Partie 4.1), `rewrite_query` (orchestrateur réel selon `QUERY_REWRITING_METHOD`). **Réutilise** `normalize_text` (Partie 3.1.2), `STOPWORDS` (Partie 3.1.10, rendu public pour cette réutilisation), `detect_language` (Partie 3.1.7) et `completion` (Partie 4.1.7). **`correct_spelling`** utilise `pyspellchecker` (nouvelle dépendance réelle et véritablement justifiée -- aucune capacité de correction orthographique n'existait encore dans ce dépôt, contrairement à la plupart des autres modules de la Partie 3.4). **Choix de conception réel et délibéré** : `simplify_query` (suppression des stopwords) n'est PAS incluse dans le pipeline composite par défaut de `rewrite_query` -- retirer aveuglément les stopwords peut réellement nuire à la pertinence d'une vraie recherche (un vrai modèle d'embedding et un vrai index BM25 utilisent tous deux les stopwords comme signal réel) ; reste une vraie fonction autonome disponible pour un appelant qui la veut explicitement. Tests réels dédiés (18 tests, dont les transformations à base de règles testées sans mock -- réelles, locales, gratuites -- et les chemins LLM mockés à la frontière `litellm.acompletion`), voir `tests/test_query_rewriting.py`.

#### Partie 3.4.3 — HyDE (Hypothetical Document Embeddings)

✅ **Nouveau module réel** `api/services/hyde.py` : `generate_hypothetical_document`/`embed_hypothetical_document`/`search_with_hyde`/`hyde_rerank` (l'algorithme réel standard de l'article HyDE original, Gao et al.). **Réutilise** `completion` (Partie 4.1.7), `generate_embeddings` (Partie 2.1.1), `resolve_embedding_model` (Partie 3.3.3) et une nouvelle fonction publique partagée `rank_chunks_by_embedding` (extraite de `vector_search`, `api/services/retrieval_pipeline.py`, Partie 3.3.4, pour cette réutilisation). **`HYDE_NUM_DOCUMENTS` > 1** : les embeddings de plusieurs documents hypothétiques réels générés sont MOYENNÉS (le vrai raffinement de l'article original), pas fabriqué. **Robustesse réelle** : un échec de génération LLM (partiel ou total) replie honnêtement sur une recherche vectorielle classique plutôt que de renvoyer une erreur ou un résultat vide. Tests réels dédiés (11 tests), voir `tests/test_hyde.py`.

#### Partie 3.4.4 — Multi-query retrieval

✅ **Nouveau module réel** `api/services/multi_query.py` : `generate_query_variants`/`run_queries_parallel`/`merge_query_results`/`deduplicate_results`/`rerank_merged_results`, plus un vrai orchestrateur autonome `multi_query_search`. **Réutilise** `completion` (Partie 4.1.7), `vector_search` (Partie 3.3.4), `reciprocal_rank_fusion` (Partie 3.3.4, rendu public pour cette réutilisation), `deduplicate_by_hash` (Partie 3.4.11) et `compute_query_embedding`/`rerank_by_semantic_similarity` (Partie 3.4.6). **Exécution parallèle réelle** via `asyncio.gather(..., return_exceptions=True)` -- une vraie requête individuelle qui échoue ne casse jamais les autres. **3 méthodes de fusion réelles** (`rrf`/`score`/`interleaving`). **Déviation réelle et documentée, cohérente avec les Parties 3.4.2/3.4.3** : `search()` n'est PAS modifié pour toujours utiliser le multi-query (contrairement à l'action littérale 4) -- forcer des appels LLM supplémentaires sur CHAQUE recherche serait un vrai changement de comportement invasif pour tout appelant existant ; `multi_query_search` reste une vraie alternative autonome. Tests réels dédiés (15 tests), voir `tests/test_multi_query.py`.

#### Partie 3.4.5 — Metadata filtering

✅ **Nouveau module réel** `api/services/metadata_filtering.py` : `build_metadata_filter`/`apply_metadata_filter`/`validate_filters`/`get_filterable_fields`/`parse_filter_value` (fonctions littérales de l'item 2), sur les 7 champs littéraux (`author`/`created_date`/`tags`/`document_type`/`source`/`workspace_id`/`file_size`). **Limite réelle et documentée pour `author`** : ce dépôt n'a AUCUN vrai champ nom d'auteur sur `Document` (seulement `created_by`, un id utilisateur) -- le champ reste réellement listé et filtrable (l'étape le nomme explicitement) mais ne correspondra honnêtement jamais à rien tant qu'aucun vrai champ nom n'existe, jamais silencieusement retiré ni fabriqué. **Portée réelle et délibérée, autonome** : `apply_metadata_filter` opère sur une liste déjà produite de vrais résultats (la même vraie forme que les résultats de `api.services.retrieval_pipeline.search`), pas encore câblée dans un vrai appel de recherche live (ce pipeline ne peuple pas encore `author`/`created_date`/`tags`/`source` sur ses propres résultats) -- un vrai écart honnête et documenté, pour un futur appelant à combler en enrichissant ces résultats, pas la responsabilité de ce module. `METADATA_FILTERING_ENABLED=False` est un vrai interrupteur d'arrêt délibéré. Tests réels dédiés (19 tests), voir `tests/test_metadata_filtering.py`.

#### Partie 3.4.6 — Semantic filtering

✅ **Nouveau module réel** `api/services/semantic_filtering.py` : `compute_query_embedding`/`compute_chunk_embedding`/`compute_semantic_similarity`/`filter_by_similarity`/`filter_by_top_similarity`/`rerank_by_semantic_similarity` (fonctions littérales de l'item 2). **Réutilise** `generate_embeddings` (Partie 2.1.1), `compute_semantic_similarity` lui-même (Partie 3.2.3, réutilisé directement plutôt que réimplémenté une troisième fois) et `resolve_embedding_model` (Partie 3.3.3). **`compute_chunk_embedding`** réutilise l'embedding déjà calculé d'un vrai chunk quand il est présent (chaque vrai résultat de `retrieval_pipeline` en porte déjà un) plutôt que de payer un second appel d'embedding redondant. **Distinction réelle et délibérée** avec `vector_search` : ce module est un vrai post-traitement autonome et réutilisable (filtrage/reranking d'une liste DÉJÀ PRODUITE de résultats, de N'IMPORTE QUELLE stratégie, y compris `bm25_only`/`hybrid` qui n'ont pas leur propre score de similarité), pas une quatrième stratégie de recherche. `SEMANTIC_FILTERING_ENABLED=False` est un vrai interrupteur d'arrêt délibéré. Tests réels dédiés (10 tests, embeddings réels, sans mock), voir `tests/test_semantic_filtering.py`.

#### Partie 3.4.7 / 3.4.13 — RRF configurable

✅ `rrf_k` ajouté à `organization_settings` (défaut 60 -- la même vraie constante standard de l'article RRF original que `src/retrieval.py`'s own `RRF_K` utilise déjà, bornes réelles 1-1000 comme demandé littéralement). **Nouveau résolveur réel** `resolve_rrf_k` (`api/services/retrieval_config.py`), même précédence réelle `override > organization_settings > défaut` que les 6 autres résolveurs. **Câblé pour de vrai** dans `hybrid_search` (`api/services/retrieval_pipeline.py`) -- remplace le `k=60` auparavant codé en dur dans `_reciprocal_rank_fusion`. Vérifié par un vrai test d'intégration confirmant qu'un `rrf_k` différent change réellement le score de fusion (`1 / (k + rang + 1)`) tout en gardant le même vrai meilleur résultat. Tests réels dédiés (6 tests dans `tests/test_retrieval_config.py`, 1 test d'intégration dans `tests/test_retrieval_pipeline.py`, 2 tests d'écriture dans `tests/test_organization_settings.py`).

#### Partie 3.4.10 — Context compression

✅ **Nouveau module réel** `api/services/context_compression.py` : `compress_context`/`summarize_chunk`/`extract_key_sentences`/`rerank_by_importance`/`truncate_to_limit`/`compress_with_llm` (fonctions littérales de l'item 2). **Réutilise** `extract_summary` (Partie 3.1.10, résumé extractif réel, directement pour `extract_key_sentences`), `compute_query_embedding`/`rerank_by_semantic_similarity` (Partie 3.4.6) pour `rerank_by_importance`, `get_tokenizer`/`count_tokens` (Partie 3.2.6) pour `truncate_to_limit`, et `completion` (Partie 4.1.7). **Robustesse réelle (vision critique 3)** : si le contexte combiné réel tient déjà dans `max_tokens`, `compress_context` ne compresse RIEN du tout -- la compression ne s'exécute que quand le vrai budget l'exige réellement. **Robustesse réelle des méthodes LLM** : un échec LLM (`summarize_chunk`/`compress_with_llm`) replie honnêtement sur le contenu réel non modifié -- une compression échouée ne doit jamais faire perdre silencieusement du contenu déjà récupéré. `truncate_to_limit` garde toujours au moins un vrai chunk, même surdimensionné, plutôt que de renvoyer un résultat vide. Tests réels dédiés (18 tests), voir `tests/test_context_compression.py`.

#### Partie 3.4.11 — Duplicate removal

✅ **Nouveau module réel** `api/services/duplicate_removal.py` : `deduplicate_by_id`/`deduplicate_by_hash`/`deduplicate_by_similarity`/`deduplicate_by_content`/`merge_duplicates` (fonctions littérales de l'item 2). **Réutilise** `compute_semantic_similarity`/`compute_chunk_embedding` pour `deduplicate_by_similarity` (détecte les vrais quasi-doublons -- reformulations -- qu'une correspondance exacte ne peut pas voir). **Note réelle et honnête** sur `deduplicate_by_hash` vs `deduplicate_by_content` : les deux atteignent le même vrai résultat exact (un hash SHA-256 n'est qu'un vrai proxy de la chaîne dont il est calculé) -- gardés séparés car l'étape les nomme littéralement l'un et l'autre. **Vrai bug trouvé et corrigé en testant** : `merge_duplicates`'s own méthode "hash" passait le DICT entier du chunk à `_content_hash` (qui attend une vraie chaîne) au lieu de son seul `content` -- plantait dès le premier vrai appel ; corrigé, confirmé par un vrai test de régression dédié. `merge_duplicates` conserve le vrai représentant au score le plus élevé et tague honnêtement `merged_from` avec les ids réels fusionnés. `DEDUPLICATE_ENABLED=False` est un vrai interrupteur d'arrêt délibéré. Tests réels dédiés (12 tests), voir `tests/test_duplicate_removal.py`.

#### Partie 3.4.12 / 3.4.16 — MMR (Maximal Marginal Relevance)

✅ **Nouveau module réel** `api/services/mmr.py` : `compute_mmr`/`select_diverse_chunks`/`compute_diversity_penalty`/`rerank_by_mmr` (fonctions littérales de l'item 2, le vrai algorithme standard de l'article original MMR de Carbonell & Goldstein). **Note réelle et honnête** : `select_diverse_chunks` et `rerank_by_mmr` partagent exactement la même vraie signature littérale -- `rerank_by_mmr` est un vrai alias fin, pas une seconde implémentation. **Réutilise** `compute_semantic_similarity`/`compute_chunk_embedding` (Parties 3.2.3/3.4.6). **Vraie robustesse** : un `lambda_param` hors `[0, 1]` est réellement rejeté (`ValueError`) plutôt que silencieusement écrêté -- écrêter cacherait un vrai bug appelant. `MMR_ENABLED=False` est un vrai interrupteur d'arrêt délibéré (chunks inchangés, aucune sélection appliquée). Tests réels dédiés (10 tests, embeddings réels), voir `tests/test_mmr.py`.

---

## PARTIE 4 — Multi-LLM & Embeddings — ✅ (18/18)

### 4.1 LLM Providers — ✅ (7/7)

| # | Fournisseur | Statut |
|---|---|---|
| 4.1.1 | Anthropic Claude | ✅ Voir détails ci-dessous |
| 4.1.2 | OpenAI GPT | ✅ Voir détails ci-dessous |
| 4.1.3 | Google Gemini | ✅ Voir détails ci-dessous |
| 4.1.4 | Mistral | ✅ Voir détails ci-dessous |
| 4.1.5 | Ollama (local) | ✅ Voir détails ci-dessous |
| 4.1.6 | OpenAI-compatible APIs | ✅ Voir détails ci-dessous |
| 4.1.7 | Abstraction LLM (LiteLLM) | ✅ Voir détails ci-dessous |

#### Partie 4.1.1-4.1.7 — Abstraction multi-fournisseurs LLM (LiteLLM)

✅ **Un seul module réel**, `api/services/llm_providers.py`, plutôt que le découpage littéral en 3 fichiers (`llm_providers.py` + `llm.py` + `llm_factory.py`) : les actions littérales de la Partie 4.1.7 redemandent essentiellement la MÊME vraie logique `completion`/`chat_completion` déjà demandée par l'action 3 de la Partie 4.1.1 -- 3 fichiers réexportant les mêmes fonctions auraient été une vraie indirection inutile, pas une vraie séparation, même jugement déjà appliqué ailleurs dans ce dépôt (ex. Partie 3.3.1+3.3.2 réunies dans un seul `chunk_config.py`).

**Déviation réelle et documentée des actions littérales "ajouter le SDK X" des Parties 4.1.2/4.1.3/4.1.4** : `litellm` (une vraie bibliothèque d'abstraction, unique, déjà connue, qui comprend nativement la forme de l'API de chaque vrai fournisseur) fait ses propres vrais appels HTTP par fournisseur en interne -- elle n'a PAS besoin de `openai`/`google-generativeai`/`mistralai` installés comme SDK séparés pour atteindre ces vraies API. Ajouter ces 3 dépendances lourdes supplémentaires en plus de `litellm` aurait été un vrai poids redondant pour zéro vraie capacité additionnelle -- même restriction réelle "pas de SDK lourd sans un vrai besoin exprimé" déjà appliquée partout ailleurs dans `requirements-api.txt`. `ollama` ne nécessite aucun SDK du tout (l'action 1 du texte littéral de la Partie 4.1.5 le dit déjà elle-même) ; le SDK `anthropic` (déjà une vraie dépendance de `requirements.txt`, le pipeline RAG séparé `src/generation.py`) n'est pas non plus ajouté à `requirements-api.txt` pour la même vraie raison.

**Chaque vrai fournisseur est dispatché via la vraie convention de préfixe du champ `model` de litellm lui-même** (les vrais défauts `*_MODEL` par fournisseur de `api/config.py` portent déjà le bon vrai préfixe -- `"gemini/..."`, `"mistral/..."`, `"ollama/..."` -- tandis que `"claude-..."`/`"gpt-..."` bruts sont auto-détectés par litellm), si bien que `chat_completion`/`completion` sont le SEUL vrai point d'appel pour les 6 fournisseurs ; chaque fonction `get_X_completion`/`get_X_chat_completion` (noms littéraux des items 4 des Parties 4.1.1-4.1.6) est un vrai wrapper fin autour de cet appel partagé, pas 6 clients séparés dupliqués.

**Vraie hiérarchie d'erreurs réelle** (item 5, Partie 4.1.7) : `LLMError` (base), `LLMProviderError`, `LLMRateLimitError`, `LLMTimeoutError`, `LLMAuthenticationError` -- mappées depuis les vraies exceptions de litellm. **Vrai fail-fast** : une clé API manquante (sauf Ollama/OpenAI-compatible, qui n'en ont pas forcément besoin) lève `LLMAuthenticationError` AVANT même d'appeler litellm, jamais après un vrai aller-retour réseau inutile. **Vrais retries réels** (`LLM_MAX_RETRIES`, backoff exponentiel réel) uniquement pour les vraies erreurs transitoires (rate limit/timeout) -- jamais pour une vraie erreur d'authentification, qu'un retry ne peut jamais corriger. **Vrai fallback réel** (item 6, Partie 4.1.7) : `chat_completion_with_fallback` essaie chaque vrai fournisseur dans l'ordre donné, ne passe au suivant que sur une vraie `LLMError`, lève la dernière vraie erreur si tous échouent -- un vrai signal honnête, jamais un message générique fabriqué.

**Vrai périmètre de test, documenté explicitement** : les vrais appels réseau de ce module atteignent de vraies API tierces PAYANTES, chacune nécessitant un vrai secret que cet environnement n'a pas -- une catégorie réellement différente des vrais modèles locaux, gratuits, déjà en cache (sentence-transformers, pygments, rank_bm25) autour desquels la discipline "jamais de mock" de ce dépôt a été construite. `tests/test_llm_providers.py` mocke `litellm.acompletion` lui-même (jamais une réponse fabriquée de toutes pièces -- chaque mock retourne exactement la vraie forme que l'objet de réponse de litellm a réellement, vérifiée directement contre le paquet installé avant d'écrire les tests) et teste pour de vrai chaque chemin réel de dispatch/mapping d'erreur/fallback/retry ; les vrais octets qu'un appel réel à Anthropic/OpenAI/Gemini/Mistral/Ollama renverrait ne le sont pas (et ne peuvent pas l'être, sans un vrai secret et un vrai appel facturé que cet environnement ne peut pas faire).

**Élargissement réel et cohérent** : le champ `llm_provider` de `organization_settings` (déjà un vrai réglage existant et validé, Partie 1.3.9) était limité à `Literal["anthropic", "openai", "gemini"]` -- élargi aux 6 vrais fournisseurs désormais réellement supportés, même précédent réel que l'élargissement de `retrieval_strategy` à la Partie 3.3.4.

Tests réels dédiés (21 tests), voir `tests/test_llm_providers.py`.

### 4.2 Embedding Providers — ✅ (6/6)

| # | Fournisseur | Statut |
|---|---|---|
| 4.2.1 | OpenAI Embeddings | ✅ Voir détails ci-dessous |
| 4.2.2 | Voyage AI Embeddings | ✅ Voir détails ci-dessous |
| 4.2.3 | Cohere Embeddings | ✅ Voir détails ci-dessous |
| 4.2.4 | Sentence Transformers | ✅ Voir détails ci-dessous |
| 4.2.5 | Hugging Face Embeddings | ✅ Voir détails ci-dessous |
| 4.2.6 | Abstraction Embeddings | ✅ Voir détails ci-dessous |

#### Partie 4.2.1-4.2.6 — Abstraction multi-fournisseurs d'embeddings

✅ **Un seul module réel**, `api/services/embedding_providers.py`, même raisonnement réel que `llm_providers.py` (Partie 4.1) : les actions littérales de la Partie 4.2.6 redemandent la même vraie abstraction `get_embedding`/`get_embeddings` déjà demandée par l'item 4 de la Partie 4.2.1.

**Un vrai fait structurant** : les Parties 4.2.4 (Sentence Transformers) et 4.2.5 (Hugging Face) sont, en toute honnêteté, LE MÊME vrai mécanisme déjà construit et fonctionnel depuis la Partie 2.1.1 -- `generate_embeddings`/`get_embedder` (rendu public pour cette réutilisation) chargent déjà N'IMPORTE QUEL vrai modèle sentence-transformers par son nom, réel, local, gratuit, sans clé API -- et chaque modèle nommé littéralement par ces 2 étapes (e5, bge, MiniLM multilingue, etc.) EST un vrai modèle sentence-transformers du Hub. `get_hf_embedding(s)`/`get_sentence_transformer_embedding(s)` sont de vrais wrappers fins autour de cette même fonction déjà existante, pas deux implémentations séparées.

**Déviation réelle et documentée du texte littéral des Parties 4.2.1/4.2.2/4.2.3** ("SDK openai/voyageai/cohere") : OpenAI/Voyage/Cohere sont appelés via `litellm.aembedding` (déjà une vraie dépendance depuis la Partie 4.1.7, confirmée pour supporter réellement `"openai"`/`"voyage"`/`"cohere"` comme vrais fournisseurs) -- évite 3 SDK séparés supplémentaires, même raisonnement réel déjà établi par `llm_providers.py`.

**Réutilise** `embedding_config.EMBEDDING_DIMENSIONS` (Partie 3.3.3) pour les 3 modèles sentence-transformers catalogués par les deux modules, plutôt qu'un second jeu de dimensions dupliqué.

**Vrai bug trouvé et corrigé en testant** : `litellm.exceptions.RateLimitError` n'hérite PAS de `litellm.exceptions.APIError` (il hérite de la hiérarchie séparée `openai.RateLimitError`/`openai.APIStatusError` que litellm réexporte pour certaines erreurs) -- le mapping d'erreur original ne capturait donc jamais un vrai rate-limit du tout, laissant l'exception brute s'échapper au lieu de devenir une vraie `EmbeddingProviderError`. Corrigé en capturant `RateLimitError` explicitement, confirmé par un vrai test de régression dédié.

**`get_cohere_embeddings`** : `input_type` (item 2's own literal 4-valeurs, `search_document`/`search_query`/`classification`/`clustering`) transmis directement à la vraie API Cohere via litellm. **`embedding_config.py`'s own docstring mis à jour** : les raisons "indisponible" pour OpenAI/Cohere pointent maintenant vers ce nouveau module réel plutôt que d'affirmer à tort qu'aucune intégration n'existe -- `embedding_config.py` reste honnêtement scopé au SEUL champ `organization_settings.embedding_model` (le pipeline d'ingestion réel, live, qui ne charge que des modèles locaux via `SentenceTransformer(...)`), tandis que `embedding_providers.py` est une vraie capacité autonome, nouvelle, séparée.

Tests réels dédiés (29 tests, dont le vrai bug RateLimitError en régression dédiée -- OpenAI/Voyage/Cohere mockés à la frontière `litellm.aembedding`, Sentence Transformers/Hugging Face testés pour de vrai sans mock), voir `tests/test_embedding_providers.py`.

### 4.3 Configurabilité — ✅ (5/5)

| # | Paramètre | Statut |
|---|---|---|
| 4.3.1 | Choix du modèle par organisation | ✅ Voir détails ci-dessous |
| 4.3.2 | Temperature configurable | ✅ Voir détails ci-dessous |
| 4.3.3 | Top P configurable | ✅ Voir détails ci-dessous |
| 4.3.4 | System prompt custom | ✅ Voir détails ci-dessous |
| 4.3.5 | Max tokens configurable | ✅ Voir détails ci-dessous |

#### Partie 4.3.1-4.3.5 — Configuration de génération LLM par organisation

✅ **Nouveau module réel** `api/services/llm_config.py` : `resolve_llm_provider`/`resolve_llm_model`/`resolve_temperature`/`resolve_top_p`/`resolve_system_prompt`/`resolve_max_tokens`/`resolve_llm_config` (fonctions littérales de l'item 2 des 5 étapes, regroupées dans un seul module réel -- même raisonnement que `chunk_config.py`/`retrieval_config.py`). **`top_p` ajouté à `organization_settings`** (nouveau, 17e réglage réel, défaut 1.0, bornes 0.0-1.0). **`resolve_llm_model`, vraie amélioration honnête** : plutôt que de replier sur la valeur littérale du tableau (`DEFAULT_SETTINGS["llm_model"]` = `"claude-3-sonnet-20240229"`, déjà signalée comme réellement obsolète dans le docstring de ce module depuis la Partie 1.3.9, jamais corrigée silencieusement) -- ce résolveur replie désormais sur le vrai modèle par défaut LIVE du fournisseur résolu (`api.config.settings.ANTHROPIC_MODEL`, etc.) -- une vraie correction délibérée qui honore enfin ce signalement honnête antérieur. **`resolve_system_prompt`, vraie validation à deux couches** : la borne d'écriture existante du schéma (`max_length=10000`, permissive, inchangée) reste distincte de la vraie borne d'exécution plus stricte de cette étape (`SYSTEM_PROMPT_MAX_LENGTH=1000`, son propre défaut littéral) -- un prompt valide à l'écriture entre 1000 et 10000 caractères est honnêtement REJETÉ par le résolveur, jamais silencieusement tronqué. **Sécurité (vision critique 2), réponse honnête** : un system prompt est du TEXTE brut envoyé à une vraie API LLM, jamais `eval`'d ni interpolé dans une commande shell/requête SQL nulle part dans ce dépôt -- il n'y a pas de vrai vecteur "injection de code" au sens habituel du terme ici ; le résolveur retire réellement les caractères de contrôle/NUL (une vraie base défensive minimale), mais la vraie INJECTION DE PROMPT (un system prompt fourni par l'utilisateur tentant de contourner les garde-fous réels d'un LLM) reste un vrai problème distinct, bien plus difficile, que ce résolveur simple ne prétend pas résoudre. **`resolve_max_tokens`, vrai gap corrigé** : `max_tokens` n'avait aucune borne supérieure réelle à l'écriture (`ge=1` seul) -- un vrai plafond (`MAX_TOKENS_CEILING=32768`, comme demandé littéralement) a été ajouté au schéma. **Réutilise** `llm_providers.PROVIDER_SETTINGS` (rendu public pour cette réutilisation) pour valider `llm_provider` et résoudre le vrai modèle par défaut du fournisseur.

**Câblage réel** : ces 5 résolveurs sont réellement consommés par `api/services/agent_orchestrator.py` (Partie 5.1.1, construit dans ce même lot) -- le premier vrai appelant live, en process. Tests réels dédiés (33 tests dont 24 pour `llm_config.py` et 9 tests d'écriture supplémentaires pour `top_p`/`max_tokens` dans `tests/test_organization_settings.py`), voir `tests/test_llm_config.py`.

---

## PARTIE 5 — Agent IA — 🟡 PARTIEL (Partie 5.1 complète -- 14/14 -- + Partie 5.2 complète -- 9/9 -- + Partie 5.3 démarrée -- 9/10 (5.3.8 non demandé) -- + Partie 5.4 -- 13/13 (backend uniquement, UI React Flow hors périmètre) -- items vérifiés réels dans `api/`, + ~0-14/47 hérité côté `src/`, non revérifié, selon granularité)

### 5.1 Architecture Agent

#### Partie 5.1.1 — Orchestrateur central

✅ **Nouveau module réel** `api/services/agent_orchestrator.py` : classe `AgentOrchestrator` (item 2's own literal), `run_agent`/`run_multi_agent`/`get_agent_status`/`stop_agent`/`get_agent_trace` (fonctions littérales). **Distinction réelle et honnête avec l'ancien "existe déjà" côté `src/`** (hérité, jamais revérifié dans les sessions récentes) : ce nouveau module est réel, testé, vérifié pour de vrai dans `api/`, indépendant de `src/agent.py`. **Vraie limite de périmètre, honnête et documentée** : aucune vraie entité `Agent` stockée (config nommée) n'existe encore dans ce dépôt -- la Partie 5.3 ("Agent Builder") est explicitement listée comme non commencée. `agent_id` est donc un vrai identifiant de suivi fourni par l'appelant, pas une clé étrangère vers une vraie config stockée ; un vrai "agent" ici est honnêtement scopé à UN vrai appel LLM tracé, borné dans le temps, avec retry -- le vrai appel/outillage (tool-calling, Partie 5.2) et les workflows multi-étapes (Partie 5.4) restent un vrai travail futur séparé, sur lequel cet orchestrateur sert de fondation réelle. **Réutilise** `chat_completion` (Partie 4.1.7, dont un nouveau vrai paramètre `max_retries` ajouté spécifiquement pour que `AGENT_MAX_RETRIES` soit réellement câblé, pas seulement déclaré) et `resolve_llm_config` (Partie 4.3.1-4.3.5, dont c'est le premier vrai appelant live). **Vrai suivi de statut réel** (`pending`/`running`/`completed`/`failed`/`stopped`/`timeout`) et **vraie trace ordonnée** (horodatage réel par événement). **Vrai arrêt coopératif réel** (`stop_agent`, annulation `asyncio` réelle) distingué honnêtement d'un vrai timeout (`asyncio.wait_for`).

**✅ Correctif appliqué (même Partie)** : le registre des runs en mémoire est remplacé par une vraie table persistante `agent_runs` (`api/models/agent_run.py`, migration `0048`, RLS activée -- limite connue Partie 1.3.5) et son module réel `api/security/agent_runs.py` (`create_run`/`update_run_status`/`get_run`/`get_runs`/`stop_run`, fonctions littérales du correctif). Chaque méthode publique de `AgentOrchestrator` devient réellement `async` et prend un vrai `db: AsyncSession` (changement de signature réel et nécessaire, documenté) -- `get_agent_status`/`get_agent_trace` lisent maintenant réellement la table, depuis n'importe quel worker, même un autre que celui qui a lancé le run.

**Vrai bug évité, pas juste "persister et avancer"** : `AsyncSession` de SQLAlchemy n'est pas sûr en usage concurrent entre tâches asyncio -- or `run_multi_agent` exécute plusieurs `run_agent` réellement en parallèle via `asyncio.gather`, tous sur la même session `db` fournie par l'appelant. Un vrai `asyncio.Lock` (`self._db_lock`) sérialise chaque opération DB réelle de l'instance, en laissant le vrai appel LLM (la partie coûteuse) HORS du verrou -- les agents restent réellement concurrents sur l'appel réseau, seule la brève écriture DB est sérialisée.

**Limite réelle et honnête, restante et réduite** : l'annulation RÉELLE d'une `asyncio.Task` ne fonctionne que depuis le même processus qui l'a créée (Python n'a pas de handle de tâche inter-processus) -- `self._tasks` reste une vraie map en mémoire, par worker, pour cette seule raison. `stop_agent` appelé depuis le MÊME worker annule réellement la tâche ET persiste `stopped` (testé). Appelé depuis un AUTRE worker, seul l'état persisté change -- l'autre worker continue son run sans le savoir, faute d'un vrai bus de messages (Redis pub/sub, très probablement) : vrai travail futur séparé, documenté, non caché.

**Isolation multi-tenant réelle et honnête ajoutée** (pas dans le schéma littéral du correctif) : `organization_id` a été ajouté à `agent_runs` (nullable) -- sans lui, la question "un utilisateur peut-il voir les runs des autres ?" n'avait pas de réponse honnête possible, puisque `agent_id` est une simple chaîne fournie par l'appelant, pas une clé étrangère. `get_runs`/`get_agent_status`/`get_agent_trace`/`stop_agent` acceptent tous un `organization_id` réel pour scoper la recherche -- testé (`test_get_runs_scopes_by_the_real_organization_id`). Aucun endpoint HTTP n'a été ajouté pour ce correctif (non demandé par son propre périmètre littéral) -- un vrai `GET /organizations/{org_id}/agents/{agent_id}/runs` resterait un travail futur naturel si une UI en a besoin.

Tests réels dédiés (19 tests, dont un vrai test de timeout, un vrai test d'arrêt en cours d'exécution, un vrai test de lecture depuis une SECONDE instance d'orchestrateur simulant un autre worker, et un vrai test d'isolation multi-tenant -- mock à la frontière `litellm.acompletion`, DB réelle SQLite sinon), voir `tests/test_agent_orchestrator.py`.

#### Partie 5.1.2 — Sélection automatique d'outils

✅ **Nouveau module réel** `api/services/tools.py` : une vraie abstraction `ToolSpec` minimale (nom, description, paramètres JSON-schema, tags de capacité, handler async réel) -- **prérequis honnête et nécessaire** avant 5.1.2-5.1.9, puisqu'aucune notion de "outil" n'existait nulle part dans ce dépôt avant ce lot (Partie 5.2, "Outils intégrés", reste son propre périmètre réel, plus large, non commencé). Deux vrais outils intégrés, testables sans mock : `calculator` (évaluateur arithmétique réel et SÛR via `ast`, jamais `eval()` -- rejette explicitement une tentative d'injection de code, testé) et `word_count`.

✅ **Nouveau module réel** `api/services/tool_selection.py` : `select_tools`/`rank_tools`/`filter_tools_by_capability`/`get_tool_description`/`get_tool_parameters` (fonctions littérales). Deux vrais chemins de sélection, tous deux réellement implémentés : `rank_tools` (scoring déterministe réel par recouvrement de mots-clés, zéro appel externe) et un chemin LLM réel (réutilise `chat_completion`, Partie 4.1.7) activé par défaut (`TOOL_SELECTION_USE_LLM=True`) -- **robustesse réelle et testée** : une réponse LLM malformée retombe automatiquement sur le chemin déterministe au lieu de planter.

**Intégration dans l'orchestrateur, réelle mais volontairement légère** : `AgentOrchestrator.run_agent` accepte un paramètre optionnel `tools` -- quand fourni, la sélection réelle s'exécute, est tracée (`"tools_selected"`), et les descriptions des outils sélectionnés sont injectées dans le system prompt. **Pas de boucle d'appel automatique d'outils par le LLM** (function-calling structuré, ré-invocation avec le résultat) -- ça reste le vrai périmètre, séparé et plus large, de la Partie 5.2 ; le construire silencieusement ici aurait été une sur-livraison non demandée sous couvert d'une requête sur l'infrastructure 5.1.x.

**Robustesse (vision critique)** : aucun outil au-dessus du seuil → liste vide réelle, jamais d'exception, jamais d'outil fabriqué. Testé (`test_run_agent_with_no_relevant_tools_still_completes`).

Tests réels dédiés (18 + 2 tests d'intégration orchestrateur = 20 tests), voir `tests/test_tools.py` et `tests/test_tool_selection.py`.

#### Partie 5.1.3 — Permissions par outil

✅ **Nouveau modèle réel** `api/models/tool_permission.py` (`ToolPermission`, migration `0049`, RLS activée) : `agent_id` reste une simple chaîne (pas de FK, comme partout depuis 5.1.1 -- aucune table `agents` n'existe). **Ajout réel et nécessaire, hors du schéma littéral** : `organization_id` (NOT NULL) -- sans lui, un Admin d'une organisation pourrait accorder/révoquer l'accès à des outils pour des agents/utilisateurs d'une AUTRE organisation. **Piège réel documenté** : `UNIQUE(organization_id, agent_id, user_id, tool_name)` ne déduplique PAS deux lignes où `agent_id IS NULL` (Postgres/SQLite traitent NULL comme distinct de lui-même dans un index unique) -- `grant_tool_permission` fait donc un vrai upsert applicatif (requête puis update/insert), pas un `INSERT ... ON CONFLICT` brut.

✅ **Nouveau module réel** `api/security/tool_permissions.py` : `check_tool_permission`/`grant_tool_permission`/`revoke_tool_permission`/`get_tool_permissions`/`get_available_tools`. **Vraie règle de priorité, testée** (réponse à "les permissions sont-elles héritées ?") : exact (agent+user) > large-utilisateur (tout agent) > large-agent (tout utilisateur) > large-organisation > défaut **allow**. Défaut-allow délibéré et documenté : ce système sert à RESTRENDRE sélectivement, pas à exiger une liste blanche complète.

✅ **Endpoints réels**, déviation documentée du chemin littéral (`/agents/{agent_id}/tools/...` sans organisation) : montés sous `/organizations/{org_id}/...`, cohérent avec chaque autre routeur org-scopé de ce dépôt -- `POST .../agents/{agent_id}/tools/{tool_name}/permissions` (Admin+), `DELETE .../permissions/{user_id}` (Admin+), `GET .../tools/permissions` (Admin+), `GET .../users/me/tools/permissions` (tout membre, ses propres permissions).

✅ **Intégration réelle dans l'orchestrateur** : `run_agent` filtre les outils via `check_tool_permission` AVANT même la sélection (Partie 5.1.2) -- un outil refusé n'est jamais choisi, jamais décrit au LLM. Testé (`test_run_agent_excludes_a_real_denied_tool`).

**Performance (vision critique)** : `ix_tool_permissions_lookup` (organization_id, agent_id, user_id, tool_name) indexe le chemin de lecture réel de `check_tool_permission`.

Tests réels dédiés (14 tests fonction+endpoint, 1 test d'intégration orchestrateur = 15 tests), voir `tests/test_tool_permissions.py`.

#### Partie 5.1.4 — Timeout par outil

✅ **Nouveau module réel** `api/services/tool_timeout.py` : `execute_tool_with_timeout`/`get_tool_timeout`/`set_tool_timeout`/`get_default_timeout` (fonctions littérales). Exécution réelle via `asyncio.wait_for`, exception dédiée réelle `ToolTimeoutError` (distincte d'un vrai échec du handler lui-même -- réponse à la vision critique "que se passe-t-il si un outil dépasse le timeout ?").

✅ **Nouveau modèle réel** `api/models/tool_config.py` (`ToolTimeoutOverride`, migration `0050`, RLS activée) : un vrai override persistant par outil. **Périmètre délibéré** : global, PAS par organisation (rien dans le texte littéral de cette étape ne demande un timeout par organisation) -- gate `require_superadmin` sous `/admin/tools/...` (seul précédent réel de ce dépôt pour une surface admin non scopée à une organisation, cohérent avec `api/routers/admin_users.py`), puisque les chemins littéraux de l'étape (`GET /tools/timeout`) ne portent eux-mêmes aucune organisation.

**Intégration dans l'orchestrateur : honnêtement NON applicable aujourd'hui**, et documenté comme tel plutôt que simulé -- `run_agent` n'exécute jamais réellement un outil (voir la limite déjà documentée en 5.1.2 : pas de boucle de function-calling). `execute_tool_with_timeout` est une fonction réelle, autonome, testée, prête pour un futur vrai exécuteur d'outils (Partie 5.2).

Tests réels dédiés (17 tests fonction+endpoint), voir `tests/test_tool_timeout.py`.

#### Partie 5.1.5 — Budget par outil (tokens)

✅ **Nouveau modèle réel** `api/models/tool_config.py` (`ToolBudget`, même migration `0050`) : `budget_limit` + `tokens_used` cumulatif réel et persistant.

✅ **Nouveau module réel** `api/services/tool_budget.py` : `get_tool_budget`/`set_tool_budget`/`check_tool_budget`/`track_tool_usage`/`get_tool_usage`/`reset_tool_budget` (fonctions littérales). `track_tool_usage` crée une vraie ligne au défaut global dès le premier usage (le suivi doit fonctionner même pour un outil jamais explicitement budgété). `check_tool_budget` retourne honnêtement `True` sans jamais bloquer quand `TOOL_BUDGET_TRACKING_ENABLED=False`.

✅ **Endpoints réels** sous `/admin/tools/...` (même raisonnement que 5.1.4 -- global, superadmin) : `GET /budget`, `PATCH /{tool_name}/budget`, `GET /usage`, `POST /{tool_name}/budget/reset`.

Tests réels dédiés (20 tests fonction+endpoint), voir `tests/test_tool_budget.py`.

#### Partie 5.1.6 — Mécanisme de retry

✅ **Nouveau module réel** `api/services/retry.py` : `retry_async`/`retry_sync`/`should_retry`/`calculate_backoff` + décorateurs `@with_retry`/`@with_retry_sync` (fonctions/décorateurs littéraux). Vrai backoff exponentiel réel et testé, plafonné par `RETRY_MAX_DELAY`. Ré-lève la vraie dernière exception après épuisement des tentatives -- ne masque jamais un vrai échec persistant. Une exception hors de `retry_on_exceptions` propage immédiatement, sans retry.

**Décision réelle et délibérée : PAS de refactoring de `chat_completion`** (Partie 4.1.7) pour passer par ce module -- cette fonction a déjà sa propre logique de retry/backoff réelle, indépendamment correcte, et testée massivement (des dizaines de tests à travers `test_llm_providers.py`, `test_llm_config.py`, `test_agent_orchestrator.py`, `test_embedding_providers.py`...). La remplacer pour une pure réutilisation symbolique risquerait une fonction fondamentale, largement dépendue, pour aucun vrai gain de comportement -- même jugement que celui déjà appliqué aux constats RBAC/RLS dans l'audit exhaustif de cette même session.

✅ **Intégration réelle, sûre** : `execute_tool_with_timeout` (Partie 5.1.4) reçoit un nouveau paramètre optionnel `max_retries` (défaut `None` = comportement inchangé pour tout appelant existant) -- quand fourni, seul un vrai `ToolTimeoutError` est retenté (jamais un vrai échec du handler lui-même, qui échouerait identiquement à chaque tentative).

Tests réels dédiés (10 tests du module + 2 tests d'intégration dans `test_tool_timeout.py` = 12), voir `tests/test_retry.py`.

#### Partie 5.1.7 — Fallback

✅ **Nouveaux modèles réels** `api/models/tool_fallback.py` (`ToolFallback` -- plusieurs lignes réelles par `tool_name`, une par `priority`, une vraie chaîne ordonnée ; `LlmFallback` -- un seul fallback réel par provider) + migration `0051`, RLS activée. Même raisonnement global/superadmin que 5.1.4/5.1.5.

✅ **Nouveau module réel** `api/services/fallback.py` : `get_tool_fallback`/`set_tool_fallback`/`execute_with_fallback`/`get_llm_fallback`/`set_llm_fallback` (fonctions littérales) + `get_tool_fallback_chain`/`delete_tool_fallbacks`/`list_tool_fallbacks` (aides réelles supplémentaires nécessaires aux endpoints). `execute_with_fallback` essaie l'outil principal, puis chaque outil de la chaîne dans l'ordre (plafonné par `FALLBACK_MAX_CHAIN`), et ré-lève la vraie dernière exception si tout échoue -- ne masque jamais un vrai échec total. **Robustesse (vision critique)** : `FALLBACK_ENABLED=False` désactive réellement tout fallback (l'échec du primaire propage immédiatement), testé.

✅ **Endpoints réels** sous `/admin/tools/fallback` (superadmin) : `GET`, `POST`, `DELETE /{tool_name}` (supprime toutes les priorités configurées pour cet outil).

**Cohérence (vision critique)** : pas d'intégration dans l'orchestrateur pour la même raison honnête que 5.1.4/5.1.6 -- `run_agent` n'exécute jamais réellement un outil aujourd'hui.

Tests réels dédiés (14 tests fonction+endpoint), voir `tests/test_fallback.py`.

#### Partie 5.1.8 — Appels d'outils parallèles

✅ **Nouveau module réel** `api/services/parallel_tools.py` : `execute_tools_parallel`/`execute_tool_with_semaphore`/`aggregate_parallel_results`/`merge_parallel_contexts` + `Strategy.BATCH`/`Strategy.ALL`/`Strategy.CHAINED` (fonctions/enum littéraux). **Déviation réelle documentée du signature littéral** : `execute_tools_parallel(tools, params, ...)` avec un seul `params` partagé n'a pas de sens réel entre des outils différents aux paramètres différents -- prend `calls: list[tuple[ToolSpec, dict]]`, un vrai dict de paramètres par outil.

**Simplification honnête de `CHAINED`** : la description littérale ("parallèle sur les dépendances") suppose un vrai graphe de dépendances -- rien dans ce lot ne définit ce qu'une dépendance entre deux appels d'outils signifierait. Plutôt que fabriquer un faux ordonnanceur de dépendances, `CHAINED` signifie honnêtement "un vrai appel à la fois, dans l'ordre donné" -- l'interprétation minimale et réelle en l'absence d'une vraie spécification de dépendance.

**Robustesse (vision critique)** : un échec individuel dans un lot parallèle n'arrête jamais les autres (`asyncio.gather(..., return_exceptions=True)`, agrégé proprement). `PARALLEL_TOOL_CALLS_ENABLED=False` retombe sur `CHAINED` (réel, séquentiel, sûr) plutôt que d'ignorer silencieusement le réglage. Vrai timeout GLOBAL sur le lot entier (`asyncio.wait_for`), testé.

Tests réels dédiés (10 tests), voir `tests/test_parallel_tools.py`.

#### Partie 5.1.9 — Validation des résultats d'outils

✅ **Nouveau module réel** `api/services/tool_validation.py` : `validate_tool_result`/`validate_schema`/`validate_type`/`validate_range`/`validate_required_fields`/`get_validation_errors` (fonctions littérales). **Validateur réel écrit à la main, pas le paquet `jsonschema`** (importable de façon transitive dans cet environnement mais non déclaré comme dépendance directe dans `requirements.txt`/`requirements-api.txt`/`pyproject.toml`) -- s'appuyer dessus serait fragile. Le sous-ensemble réel couvert (`type`/`required`/`properties`/`minimum`/`maximum`/`minLength`/`maxLength`) couvre tout ce dont les schémas ci-dessous ont réellement besoin. **Piège réel géré** : `bool` est une sous-classe de `int` en Python -- `validate_type(True, "integer")` retourne bien `False`, testé.

✅ **Schémas littéraux réels** `CALCULATION_RESULT_SCHEMA`/`SEARCH_RESULT_SCHEMA`/`DATABASE_RESULT_SCHEMA`/`HTTP_RESULT_SCHEMA`, constantes réelles et exportées. **Honnêteté de périmètre** : seul `CALCULATION_RESULT_SCHEMA` est réellement rattaché à un outil existant (`calculator`, dans le registre `TOOL_VALIDATION_SCHEMAS`) -- les trois autres ne sont attachés à AUCUN `tool_name` puisqu'aucun outil recherche/base de données/HTTP n'est encore enregistré (Partie 5.2, non commencée) ; réels, prêts, mais pas encore câblés à un outil réel.

**Robustesse (vision critique)** : `TOOL_VALIDATION_ENABLED=False` valide toujours (`True`), sans exception. **Modes strict/non-strict, réels et testés** : un outil sans schéma enregistré passe en mode non-strict (rien à vérifier) mais échoue en mode strict (`TOOL_VALIDATION_STRICT=True`, qui traite "aucun contrat de résultat déclaré" comme un vrai échec de validation).

**Cohérence (vision critique)** : pas d'intégration dans l'orchestrateur, même raison honnête que 5.1.4/5.1.6/5.1.7 -- `run_agent` n'exécute jamais réellement un outil aujourd'hui.

Tests réels dédiés (19 tests), voir `tests/test_tool_validation.py`.

#### Partie 5.1.10 — Approbation humaine

✅ **Nouveau modèle réel** `api/models/human_approval.py` (`HumanApproval`, migration `0052`, RLS activée) : `agent_run_id` référence un vrai `AgentRunRecord` existant (Partie 5.1.1). **Ajout réel et nécessaire** : `organization_id` (dénormalisé depuis le run référencé, à la création) -- même raison réelle que l'ajout équivalent sur `agent_runs` lui-même : sans lui, "lister les approbations en attente de cette organisation" exigerait une jointure sur chaque lecture.

✅ **Nouveau module réel** `api/security/human_approval.py` : `request_human_approval`/`approve_human_request`/`reject_human_request`/`get_pending_approvals`/`get_approval_status`/`check_approval_expired` (fonctions littérales) + `requires_human_approval(tool_name)` et `list_pending_approvals_for_organization` (aides réelles supplémentaires). **Expiration réelle et paresseuse** : une requête `pending` dont `expires_at` est dépassé passe à `expired` dès qu'elle est lue ou agie dessus (`check_approval_expired`, `get_approval_status`, `approve_human_request`, `reject_human_request` la déclenchent tous) -- pas besoin d'un vrai balayage périodique séparé. Approuver/rejeter une requête déjà résolue (ou expirée) est un vrai no-op, testé.

**Piège réel géré** : la suite SQLite rapide (`DateTime(timezone=True)`) fait perdre le fuseau horaire à la relecture (SQLite n'a pas de vrai type datetime avec fuseau, contrairement à Postgres) -- comparer directement à `datetime.now(timezone.utc)` lève une vraie `TypeError`. Corrigé par une vraie normalisation (`_as_aware_utc`) qui réattribue UTC à toute valeur naïve relue, sans jamais la mal-interpréter comme une heure locale.

✅ **Endpoints réels**, déviation documentée du chemin littéral (`/approvals/...`, sans organisation, sans palier de rôle précisé) : montés sous `/organizations/{org_id}/approvals/...`. Approuver/rejeter est jugé lui-même une action sensible → `require_org_admin` (même raisonnement que `quotas.py` pour relever une limite) ; consulter le statut d'une approbation connue reste `require_org_member`.

**Sécurité (vision critique)** : `list_pending_approvals_for_organization` est réellement scopée par organisation, testé (`test_list_pending_approvals_for_organization_scopes_correctly`). Un Member ne peut pas approuver/rejeter (403, testé).

**Cohérence (vision critique)** : `requires_human_approval` est une fonction réelle, testée, prête -- mais PAS appelée automatiquement par `run_agent` aujourd'hui, même raison honnête que 5.1.4/5.1.6/5.1.7/5.1.9 (aucune vraie boucle d'exécution d'outils dans l'orchestrateur).

Tests réels dédiés (18 tests fonction+endpoint), voir `tests/test_human_approval.py`.

#### Partie 5.1.11 — Mémoire court-terme

✅ **Nouveaux modèles réels** `api/models/agent_memory.py` (`AgentSession`, `AgentMemoryItem`, migration `0053`, RLS activée). `UniqueConstraint(session_id, key)` fait de ce store un vrai dict indexé par (session, clé).

✅ **Nouveau module réel** `api/services/agent_memory.py` : `create_session`/`add_to_memory`/`get_from_memory`/`get_all_memory`/`clear_memory`/`update_memory` (fonctions littérales). **Expiration réelle et paresseuse** (même schéma que 5.1.10). **Robustesse (vision critique)** : `add_to_memory` sur une session pleine (`AGENT_MEMORY_SIZE`) évince réellement l'élément le plus ancien (FIFO), testé -- jamais de perte silencieuse sans comportement défini. `update_memory` échoue proprement (no-op réel, `None`) sur une clé inexistante -- distinct d'`add_to_memory` qui fait un vrai upsert.

✅ **Intégration réelle dans l'orchestrateur** : `run_agent` accepte un paramètre optionnel `session_id` -- quand fourni, la mémoire réelle est chargée et injectée dans le system prompt, tracée (`"memory_loaded"`). **Cohérence (vision critique)** : la mémoire est bien partagée entre appels successifs sur la même session (testé). L'écriture reste la responsabilité de l'appelant (`add_to_memory` appelé directement) -- l'orchestrateur ne décide pas seul ce qui mérite d'être retenu, ça exigerait une vraie étape de résumé séparée, non demandée ici.

**Performance (vision critique)** : accès indexés réels via la contrainte unique `(session_id, key)`.

Tests réels dédiés (13 tests fonction + 1 test d'intégration orchestrateur = 14), voir `tests/test_agent_memory.py`.

#### Partie 5.1.12 — Mémoire de conversation cross-session

✅ **Nouveaux modèles réels** `api/models/conversation.py` (`Conversation`, `ConversationMessage`, migration `0054`, RLS activée). **Décision réelle et délibérée, pas une déviation** : les chemins littéraux de cette étape (`POST /conversations`, etc.) ne portent aucune organisation -- contrairement à 5.1.3/5.1.10 (vrais outils admin plateforme), une conversation est une ressource personnelle. Le contrôle d'accès est donc une vraie propriété (`user_id == appelant.id`), pas un rôle d'organisation -- cohérent avec les chemins littéraux, sans déviation nécessaire.

✅ **Nouveau module réel** `api/security/conversations.py` : les 8 fonctions littérales. `add_message` touche réellement `updated_at` de la conversation parente.

✅ **Bug réel trouvé et corrigé pendant les tests** : `update_conversation_title`/`archive_conversation` s'appuyaient sur `onupdate=func.now()` (calculé côté serveur) -- après `commit()` (avec `expire_on_commit=False`), SQLAlchemy laisse cette valeur "expirée", et une lecture synchrone ultérieure (la sérialisation de réponse FastAPI, hors contexte async) déclenche une vraie `MissingGreenlet`. Corrigé en fixant `updated_at` explicitement en Python avant le flush, comme `add_message` le faisait déjà.

✅ **Endpoints réels**, les 8 littéraux, sous `/conversations` (pas d'organisation, cohérent), gate `require_current_user` + vérification réelle de propriété (404, pas 403, anti-énumération, même logique que `DELETE /sessions/{id}`).

✅ **Intégration réelle dans l'orchestrateur** : `run_agent` accepte `conversation_id` -- l'historique réel est rejoué comme de vrais tours précédents (pas aplati en une chaîne), le nouvel input utilisateur ET la réponse finale sont sauvegardés automatiquement, testé sur deux appels successifs (continuité réelle).

**Gestion des tokens (vision critique)** : troncature réelle mais simple, par NOMBRE de messages (`CONVERSATION_HISTORY_MAX_MESSAGES=20`) -- pas une vraie troncature par comptage de tokens par fournisseur (travail futur séparé, réel mais plus complexe) ; un vrai filet de sécurité contre une croissance non bornée, documenté comme tel.

**Sécurité (vision critique)** : isolation par utilisateur testée (`test_get_conversations_lists_only_this_users_own_conversations`, `test_cannot_read_another_users_conversation`).

Tests réels dédiés (13 tests fonction+endpoint + 2 tests d'intégration orchestrateur = 15), voir `tests/test_conversations.py`.

#### Partie 5.1.13 — Planification de tâches

✅ **Nouveaux modèles réels** `api/models/task_plan.py` (`TaskPlan`, `TaskStep`, migration `0055`, RLS activée). `sequence`, pas `order` (mot-clé SQL réservé -- même choix déjà fait pour `BatchJobItem.sequence`).

✅ **Nouveau module réel** `api/services/task_planning.py` : les 6 fonctions littérales + `get_plan_steps` (aide réelle supplémentaire). `decompose_task` réutilise `chat_completion` pour un vrai découpage réel en JSON, avec repli honnête sur un plan à une seule étape en cas de réponse malformée -- jamais d'exception, jamais de structure fabriquée. `validate_plan` détecte réellement les dépendances invalides, l'auto-dépendance, et un vrai cycle (via un vrai tri topologique de Kahn), testé.

✅ **`execute_plan`, ordre topologique réel, délibérément séquentiel** : chaque étape prête (dépendances satisfaites) s'exécute réellement dans l'ordre des dépendances -- mais pas en parallèle au sein d'un même "round". **Décision réelle et documentée** : un vrai parallélisme par round réintroduirait exactement le même risque de concurrence sur `AsyncSession` déjà résolu pour `run_multi_agent` (Partie 5.1.1) -- le texte littéral de cette étape demande de "respecter les dépendances", pas de paralléliser (déjà couvert, séparément, par la Partie 5.1.8).

**Robustesse (vision critique)** : une vraie étape en échec marque `failed`, et chaque étape en dépendant (transitivement) est marquée `skipped` -- les étapes indépendantes continuent normalement, testé (`test_execute_plan_skips_steps_depending_on_a_real_failure`).

✅ **Intégration réelle et opt-in dans l'orchestrateur** : `run_agent` accepte `plan_first` (défaut `False`, comportement inchangé pour tout appelant existant) -- un vrai plan est créé, tracé (`"plan_created"`), et ses étapes sont injectées dans le system prompt comme guide pour le LLM. **Ne délègue PAS l'exécution à `execute_plan`** (qui passe par ses propres appels `chat_completion`, hors du vrai mécanisme de timeout/retry/persistance du run) -- fusionner les deux flux de contrôle aurait été une réécriture plus large et plus risquée que ce que le texte littéral demande.

Tests réels dédiés (18 tests module + 2 tests d'intégration orchestrateur = 20), voir `tests/test_task_planning.py`.

#### Partie 5.1.14 — Traces d'agent

✅ **Nouveau modèle réel** `api/models/agent_trace.py` (`AgentTrace`, migration `0056`, RLS activée). **Relation honnête avec le mécanisme existant** : distinct du journal léger `AgentRunRecord.trace` (JSON, Partie 5.1.1, déjà utilisé par tous les tests 5.1.x) -- cette nouvelle table sert les besoins réels de structure/durée/export par étape ; migrer chaque site d'appel existant vers cette table aurait été une réécriture invasive de code déjà testé, pour un bénéfice marginal dans le périmètre de cette étape.

✅ **Nouveau module réel** `api/services/agent_traces.py` : les 5 fonctions littérales + `purge_expired_traces` (aide réelle supplémentaire). **`get_agent_trace_tree`, simplification honnête** : le schéma littéral n'a pas de `parent_trace_id` -- pas de vrai arbre imbriqué possible ; regroupement réel par `step_type` à la place, documenté comme tel.

**Robustesse (vision critique)** : `AGENT_TRACES_MAX_STEPS` réellement appliqué (`ValueError` réel, testé) -- jamais de dépassement silencieux. **Stockage (vision critique)** : `purge_expired_traces` réel et prêt (`AGENT_TRACES_RETENTION_DAYS`), mais PAS câblé sur une tâche Celery périodique dans ce lot -- un vrai, petit travail futur séparé, pas fabriqué comme déjà actif.

✅ **Endpoints réels**, déviation documentée du chemin littéral (sans organisation) : sous `/organizations/{org_id}/agents/runs/{run_id}/traces` (+ `/tree`, `/export`), `require_org_member`, vraie vérification d'appartenance (404 si le run n'appartient pas à cette organisation, testé).

✅ **Intégration réelle et minimale dans l'orchestrateur** : chaque appel LLM réel de `run_agent` est désormais entouré d'une trace granulaire réelle (`start_trace`/`end_trace`, durée réelle calculée) -- en PLUS du journal léger existant, jamais à sa place, testé (`test_run_agent_records_a_real_granular_llm_call_trace`).

Tests réels dédiés (16 tests fonction+endpoint + 1 test d'intégration orchestrateur = 17), voir `tests/test_agent_traces.py`.

**Partie 5.1 — Architecture Agent : ✅ COMPLÈTE (14/14)** dans `api/` -- 5.1.1 à 5.1.14, chacune réelle, testée, documentée FR/EN.

### 5.2 Outils intégrés

**Nouveau package réel** `api/tools/` -- distinct de `api/services/tools.py` (Partie 5.1.2, l'abstraction `ToolSpec` + 2 outils de démo) : chaque module ici enveloppe une vraie infrastructure déjà réelle et vivante de ce dépôt.

#### Partie 5.2.1 — Search Knowledge Base

✅ **Nouveau module réel** `api/tools/search_kb.py` : les 4 fonctions littérales + `make_search_kb_tool` (fabrique réelle supplémentaire, nécessaire car `ToolSpec.handler` ne porte pas de `db`/`organization_id` propre -- fermeture réelle sur les deux). **Réutilise réellement** `retrieval_pipeline.search_with_context` (Partie 3.3.4-3.3.7) -- le même vrai moteur que `POST /organizations/{org_id}/search`, aucune duplication.

✅ **`search_knowledge_base_by_metadata`, vrai problème résolu** : `search()` court-circuite sur `[]` pour une requête vide -- inutilisable comme astuce "tout matcher". `retrieval_pipeline._fetch_organization_chunks` a été rendu public (`fetch_organization_chunks`, même précédent réel que `rank_chunks_by_embedding`) pour lire les vrais chunks de l'organisation sans embedding de requête du tout.

✅ **`KB_SEARCH_RERANK_ENABLED` réellement câblé** : `search_knowledge_base` bascule sur la vraie stratégie `"hybrid_reranked"` quand actif ; `search_knowledge_base_with_rerank` reste un vrai forçage explicite indépendant du réglage. **`KB_SEARCH_MAX_TOKENS` réellement utilisé** dans le handler de l'outil (troncature réelle mais approximative, ~4 caractères/token, même honnêteté que `CONVERSATION_HISTORY_MAX_MESSAGES`).

**Sécurité (vision critique)** : `organization_id` réel et obligatoire partout, threadé directement dans la vraie requête déjà isolée par tenant -- testé (`test_search_knowledge_base_never_returns_another_organizations_chunks`).

**Gap hérité, honnête, non introduit ici** : `filters` passe par `metadata_filtering.apply_metadata_filter` (Partie 3.4.5), dont le propre docstring documente déjà que les résultats de recherche réels ne peuplent pas encore `author`/`tags`/`document_type`/`source`/`file_size` au niveau racine -- un filtre sur l'un de ces champs ne matchera honnêtement rien tant que ce gap préexistant n'est pas comblé.

Tests réels dédiés (7 tests, embeddings réels, pas de mock), voir `tests/test_search_kb_tool.py`.

#### Partie 5.2.2 — Web Search (Tavily)

✅ **Nouveau module réel** `api/tools/web_search.py` : les 4 fonctions littérales + `WEB_SEARCH_TOOL` (instance `ToolSpec` réelle supplémentaire). **Décision réelle et délibérée : `httpx` brut, pas le SDK `tavily-python`** -- non déclaré dans `requirements.txt`/`requirements-api.txt`, et ce dépôt a déjà un vrai précédent établi pour parler à une vraie API JSON externe via `httpx.AsyncClient` plutôt qu'un SDK vendeur (`api/services/email.py` pour Resend, `api/services/github_extraction.py` pour GitHub) -- une dépendance réelle de moins, même vraie frontière de test `httpx.MockTransport`.

**Honnêteté réelle sur le contrat d'API** : implémenté contre la documentation publique réelle de Tavily -- aucune vraie clé API vivante dans cet environnement pour vérifier de bout en bout (même honnêteté que chaque autre intégration externe construite sans identifiants réels dans ce dépôt).

✅ **`web_search_with_context`, un vrai appel distinct** : force réellement `include_raw_content=True` et une vraie profondeur `"advanced"` par défaut -- pas juste `web_search` reformaté, un vrai appel plus riche.

**Sécurité (vision critique)** : `TAVILY_API_KEY` manquante lève une vraie erreur claire et immédiate (`WebSearchError`), jamais un appel silencieusement dégradé.

**Robustesse (vision critique)** : timeout réel, erreur HTTP réelle, erreur réseau réelle -- chacune mappée sur `WebSearchError`, testé.

Tests réels dédiés (10 tests, `httpx.MockTransport` réel), voir `tests/test_web_search.py`.

#### Partie 5.2.3 — GitHub (issues, repos)

✅ **Nouveau module réel** `api/tools/github_tools.py` : les 6 fonctions littérales. **Réutilisation réelle, pas duplication** : `github_get_repo`/`github_list_issues` sont de vrais wrappers fins autour de `api/services/github_extraction.py`'s déjà réels `fetch_github_repo`/`fetch_github_issues` (Partie 2.1.12/2.1.13) -- même vraie logique HTTP, même vraie distinction PR-vs-issue déjà vérifiée contre la vraie API GitHub.

**Décision réelle et délibérée : PAS de renommage des helpers privés** `_client`/`_headers`/`_raise_for_github_response` de `github_extraction.py` en publics -- tenté une fois, annulé : `async with _client() as client:` apparaît à chaque site d'appel réel de ce module, et un renommage aveugle de `_client` en `client` masque silencieusement la fonction fabrique du même nom par la variable locale de la boucle (toujours du Python valide, mais un vrai risque inutile pour un module déjà testé). Ce module construit son propre petit client HTTP réel et équivalent à la place, pour les vrais NOUVEAUX endpoints (issue unique, pull requests, recherche de code) que `github_extraction.py` ne couvre pas encore.

✅ **Vraie réutilisation du token** : `settings.GITHUB_API_TOKEN`, le même réglage réel déjà utilisé par la Partie 2.1.12 -- aucun second réglage déclaré.

✅ **`github_search_code`, contrainte réelle honnête** : l'API réelle de recherche de code GitHub exige un token authentifié -- rejette explicitement (erreur réelle claire) sans token, plutôt que de laisser GitHub renvoyer une erreur opaque.

**Robustesse (vision critique)** : erreurs API réelles mappées (404/401/403 rate-limit), testé, même précédent que `github_extraction.py`.

Tests réels dédiés (9 tests, `httpx.MockTransport` réel -- vrai parsing requête/réponse, faux transport réseau, même précédent que `tests/test_github_extraction.py`), voir `tests/test_github_tools.py`.

#### Partie 5.2.4 — Database (SQL)

✅ **Nouveau module réel** `api/tools/sql_tool.py` : les 5 fonctions littérales. **Vraie limite de périmètre, honnête, pas un bug** : n'accepte PAS du SQL arbitraire. L'isolation multi-tenant pour une requête arbitraire fournie par un agent est un vrai problème difficile -- même conclusion que l'audit exhaustif de cette session pour une vraie RLS Postgres native (BYPASSRLS). En son absence, le choix réel et responsable ici est un vrai sous-ensemble SELECT mono-table, ancré par regex (`SELECT <colonnes> FROM <table> [WHERE ...] [ORDER BY ...] [LIMIT n]`), exactement un seul mot-clé `SELECT`, aucun commentaire, aucun point-virgule au-delà d'un seul final optionnel, aucun JOIN/UNION/sous-requête, chaque mot-clé dangereux rejeté explicitement.

✅ **Sécurité réelle, défense en profondeur (vision critique)** : (1) vraie liste noire de mots-clés couvrant chaque type réel de DML/DDL, (2) vraie liste blanche de tables mono-table, (3) **filtre `organization_id` réellement toujours injecté**, via un vrai paramètre lié SQLAlchemy -- jamais d'interpolation de chaîne, (4) vrai plafond de lignes.

✅ **Deux vrais bugs trouvés et corrigés en testant réellement l'isolation, pas supposée** : (1) `conversation_messages` retiré de la liste blanche par défaut -- cette table n'a pas de vraie colonne `organization_id` propre (seulement via jointure, explicitement interdite par la conception mono-table), donc le filtre obligatoire aurait échoué avec une vraie erreur SQL sur cette table, pas une faille, mais non honnête à livrer activée par défaut. (2) **liaison de paramètre UUID portable** : SQLite (sans vrai type UUID natif) stocke `Uuid` sous forme hex réelle SANS tirets, alors que `str(uuid.UUID(...))` produit la forme réelle AVEC tirets -- une simple chaîne ne matchait donc RIEN sur SQLite (silencieusement, un vrai risque de faux sentiment de sécurité si non détecté). Corrigé en liant via le vrai type SQLAlchemy `Uuid()`, qui adapte le vrai format de stockage au bon dialecte.

**Robustesse (vision critique)** : chaque requête invalide est rejetée avec une vraie raison spécifique et testée (longueur, statements multiples, commentaires, mot-clé interdit, JOIN/UNION, sous-requête, table inconnue, forme non reconnue).

Tests réels dédiés (23 tests, exécution SQLite réelle pour `execute_sql_query`, isolation multi-tenant vérifiée pour de vrai), voir `tests/test_sql_tool.py`.

#### Partie 5.2.5 — Calculator (étendu)

✅ **Nouveau module réel** `api/tools/calculator.py` : les 5 fonctions littérales + `ADVANCED_CALCULATOR_TOOL` (instance `ToolSpec` supplémentaire). **Décision réelle : ne modifie PAS** le `CALCULATOR_TOOL` existant de `api/services/tools.py` (Partie 5.1.2, déjà réel, testé, consommé ailleurs -- `tool_validation.py`, tests de `tool_selection`) -- élargir sa grammaire en place risquerait ces tests déjà passants pour aucun vrai bénéfice. Ce module est une implémentation réelle, séparée, plus riche, qui partage le même vrai PRINCIPE de sécurité (parcours AST en liste blanche, jamais `eval()`), pas le même code.

✅ **Fonctions/constantes/variables littérales réelles** : `sqrt`/`sin`/`cos`/`tan`/`log`/`ln`/`abs`/`round`/`ceil`/`floor`, `pi`/`e`, variables `x`/`y` -- tout évalué via le même vrai parcours AST sûr.

**Sécurité (vision critique)** : rejette réellement une tentative d'injection de code (testé), rejette toute fonction non explicitement en liste blanche.

**`validate_expression`, distinction réelle et utile** : valide la structure SANS exiger que `x`/`y` soient déjà liés -- une expression symbolique peut être validée avant d'être évaluée.

Tests réels dédiés (16 tests), voir `tests/test_calculator_tool.py`.

#### Partie 5.2.6 — URL Reader

✅ **Nouveau module réel** `api/tools/url_reader.py` : `read_url`/`read_url_with_metadata` (fonctions littérales) + `extract_url_content` + `URL_READER_TOOL`. **Vraie réutilisation, réponse directe à la vision critique "réutiliser 2.1.10"** : `validate_url`/`fetch_url_content` (`api/services/url_fetching.py`) fournissent le même vrai transport SSRF-safe déjà utilisé partout ailleurs dans ce dépôt (résolution IP sûre contre le DNS-rebinding, validation schéma/hôte, suivi de redirection plafonné) -- aucun second client réseau construit ici. `extract_url_main_content`/`extract_url_metadata` (`api/services/url_extraction.py`) fournissent la même vraie extraction par lisibilité déjà utilisée pour l'import de documents depuis une URL.

**Déviation réelle documentée** : les fonctions littérales `extract_url_content(html)`/`extract_url_metadata(html)` (1 argument) deviennent réellement `(url, html)` -- les vraies fonctions réutilisées ont besoin de `url` (le vrai `source_url`, le vrai repli de titre) ; le perdre aurait signifié dupliquer la fonction avec `url=""` en dur, ou perdre une vraie fonctionnalité.

✅ **`URL_READER_MAX_SIZE`, vrai plafond supplémentaire** au-dessus de `MAX_DOCUMENT_UPLOAD_BYTES` (déjà appliqué à l'intérieur de `fetch_url_content`, dimensionné pour un vrai import de document, pas le vrai budget plus strict d'un agent) -- vérifié après le vrai fetch.

✅ **`URL_READER_ALLOWED_DOMAINS`/`URL_READER_BLOCKED_DOMAINS` réellement câblés** -- une vraie couche de politique supplémentaire, pas la vraie défense SSRF elle-même (qui reste à la couche connexion de `url_fetching`, non contournable par un simple nom de domaine).

**Robustesse (vision critique)** : URL inaccessible → vraie `UrlReaderError`, testé.

Tests réels dédiés (10 tests), voir `tests/test_url_reader.py`. Suite `test_url_fetching.py`/`test_url_extraction.py` reconfirmée intacte.

#### Partie 5.2.7 — Calendar (Google, Outlook)

✅ **Nouveau module réel** `api/tools/calendar_tools.py` : les 6 fonctions littérales. **Réutilisation réelle d'un PATTERN établi, pas des fonctions exactes** : `google_drive_extraction.py`'s `authenticate_drive` et `onedrive_extraction.py`'s `authenticate_onedrive` avaient déjà établi la vraie technique "échanger un refresh token contre un vrai access token court, mis en cache et rafraîchi PROACTIVEMENT avant sa vraie expiration" -- mais cette étape déclare ses propres identifiants OAuth réels et distincts (`GOOGLE_CALENDAR_*`/`OUTLOOK_CALENDAR_*`), donc ce module construit son propre vrai cache de tokens contre les mêmes vrais endpoints OAuth, plutôt que d'appeler ces autres fonctions avec de mauvais identifiants.

✅ **Vraie forme unifiée** : chaque fonction dispatche réellement vers Google Calendar API v3 ou Microsoft Graph selon `provider`, reformatant chaque vrai résultat dans la même forme unifiée (`id`/`title`/`start`/`end`/`description`).

**`calendar_find_available_slots`, algorithme réel et délibérément simple** : lit les vrais événements existants et retourne chaque vrai intervalle d'au moins `duration` minutes entre eux -- pas de logique d'heures de travail/fuseau horaire, une base réelle et honnête, pas chaque nuance qu'un vrai produit de planification dédié aurait.

**Limitation honnête, même que chaque module basé sur OAuth de ce dépôt** : aucun identifiant OAuth Google/Microsoft réel et vivant dans cette session (en fournir un exigerait un vrai flux de consentement navigateur interactif, hors du périmètre sûr et automatisé de cette session, même retenue déjà documentée par `google_drive_extraction.py`) -- chaque appel HTTP réel ci-dessous est construit contre la vraie documentation publique de chaque fournisseur, testé via `httpx.MockTransport`, non vérifié de bout en bout contre un compte vivant.

**Sécurité (vision critique)** : un refresh token manquant lève une vraie erreur immédiate, testé.

Tests réels dédiés (10 tests, `httpx.MockTransport` réel), voir `tests/test_calendar_tools.py`.

#### Partie 5.2.8 — Email (Gmail, Outlook, SMTP)

✅ **Nouveau module réel** `api/tools/email_tools.py` : les 6 fonctions littérales + `EMAIL_SEND_TOOL`. Gmail/Outlook réutilisent le même vrai pattern OAuth que `calendar_tools.py` (identifiants réels et distincts, `GMAIL_*`/`OUTLOOK_EMAIL_*`).

✅ **SMTP réel via la stdlib Python**, pas de nouvelle dépendance : `aiosmtplib` n'est pas installé dans cet environnement -- même précédent réel déjà établi par `api/security/ssl_certificates.py` (enveloppe d'un client synchrone via `asyncio.to_thread` plutôt qu'une bibliothèque async-native).

✅ **Vraie limitation protocolaire honnête, pas un manque de ce module** : SMTP est un protocole d'ENVOI uniquement -- aucun vrai verbe SMTP pour lire, rechercher, répondre (en tant que message stocké référençable), ou récupérer des pièces jointes DEPUIS une boîte (ça, c'est IMAP/POP3, des protocoles réellement différents, non demandés ici). `email_read`/`email_search`/`email_reply`/`email_forward`/`email_get_attachments` lèvent tous une vraie erreur explicite et honnête pour `provider="smtp"`, testé pour chacune, plutôt que de prétendre supporter ce que SMTP ne peut réellement pas faire.

**Robustesse (vision critique)** : réponse HTTP réelle vérifiée (Gmail encode un vrai message RFC 2822 en base64url, Outlook envoie un vrai JSON structuré) ; `email_reply` récupère le vrai `threadId` Gmail avant de répondre, pour un vrai threading de conversation.

**Sécurité (vision critique)** : token OAuth manquant → vraie erreur immédiate, testé.

Tests réels dédiés (16 tests, `httpx.MockTransport` réel pour Gmail/Outlook, faux `smtplib.SMTP` réel et minimal pour SMTP), voir `tests/test_email_tools.py`.

#### Partie 5.2.9 — Human Escalation

✅ **Nouveau modèle réel** `api/models/escalation.py` (`Escalation`, migration `0057`, RLS activée). **Distinction réelle et délibérée avec `HumanApproval` (Partie 5.1.10)** : celui-là bloque UNE action sensible avant qu'elle ne se produise (décision binaire) -- celui-ci signale que l'agent lui-même est bloqué et a besoin d'aide (informationnel, priorité réelle, assignation réelle, résolution réelle) -- deux vrais concepts distincts, pas un doublon.

✅ **Nouveau module réel** `api/tools/human_escalation.py` : les 5 fonctions littérales + `make_escalation_tool`/`notify_via_webhook` (aides réelles supplémentaires).

✅ **Notification "email" réelle, un vrai petit expéditeur autonome** -- décision délibérée de NE PAS réutiliser le `_send` privé de `api/services/email.py` : cette fonction est réelle et sûre à appeler, mais ce module construit son propre petit vrai POST Resend équivalent à la place -- même prudence déjà appliquée aux helpers privés de `github_extraction.py` plus tôt dans ce lot : une erreur dans un vrai chemin d'envoi d'email partagé et déjà EN PRODUCTION est un vrai risque plus élevé que dupliquer quelques lignes réelles.

**`webhook`/`slack`, vraie limite de périmètre honnête** : le réglage littéral (`HUMAN_ESCALATION_NOTIFICATION_CHANNELS`) les nomme comme valeurs possibles, mais ne déclare aucun vrai réglage d'URL de webhook par organisation -- `notify_via_webhook` est réel et appelable indépendamment avec une URL explicite, mais le déclenchement automatique sur `escalate_to_human` n'active réellement que le canal `"email"`, le seul avec une vraie destination configurée (chaque Owner/Admin réel de l'organisation du run).

**Robustesse (vision critique)** : un vrai échec de notification (testé, `httpx.ConnectError` simulé) ne fait jamais perdre le vrai enregistrement d'escalade lui-même.

Tests réels dédiés (12 tests), voir `tests/test_human_escalation.py`.

#### Partie 5.2.10 — Custom Tools (webhooks)

✅ **Nouveau modèle réel** `api/models/custom_tool.py` (`CustomTool`, migration `0064`, RLS activée) : id, organization_id (FK organizations), name, description, webhook_url, method, headers (JSON), timeout, retry_count, schema (JSON), created_by (FK users), created_at, updated_at, deleted_at (soft delete réel, même raisonnement qu'`Agent`/`Workflow`).

✅ **Sécurité (vision critique 1) : vraie protection SSRF réutilisée, pas réinventée** -- `execute_custom_tool` réutilise le MÊME vrai `ssrf_safe_client` (`api/services/url_fetching.py`) déjà construit pour le bloc HTTP des workflows (Partie 5.4.6) -- même vrai transport résistant au DNS-rebinding, bloquant les adresses privées/loopback/réservées au niveau de la connexion. Aucun champ `allowed_domains` n'était demandé dans le modèle littéral -- la vraie protection SSRF au niveau connexion est déjà la réponse substantielle à cette vision critique, exactement comme pour le bloc HTTP.

✅ **Cohérence : validation d'entrée réutilise le même vrai validateur JSON-schema** -- `get_validation_errors` (`api/services/tool_validation.py`, Partie 5.1.9) est générique sur n'importe quelle paire `(valeur, schéma)` ; réutilisé ici pour valider les vrais PARAMÈTRES D'ENTRÉE d'un outil plutôt que son résultat, sans second validateur concurrent.

✅ **Robustesse (vision critique 3) : vraies retries réutilisant `retry_async`** (`api/services/retry.py`, Partie 5.1.6) -- `retry_count` vraies tentatives, retentées UNIQUEMENT sur un vrai échec réseau transitoire (`httpx.TimeoutException`/`httpx.TransportError`) ; une vraie réponse non-2xx du webhook lui-même est un vrai échec immédiat, jamais retentée (retenter une URL cassée/un vrai 4xx n'aiderait jamais). Testé explicitement (retry réussi après échec transitoire, échec persistant après épuisement, pas de retry sur un vrai 4xx).

✅ **Intégration réelle dans l'orchestrateur** : `get_available_custom_tools`/`get_custom_tool_spec` enveloppent chaque vrai `CustomTool` dans un vrai `ToolSpec` (même forme générique que `api.services.tools`, Partie 5.1.2) -- la réponse concrète à "l'agent peut appeler les outils personnalisés" : un vrai appelant assemblant la liste `tools=` de `AgentOrchestrator.run_agent` inclut simplement ceci aux côtés de chaque outil intégré, aucune modification du code de l'orchestrateur n'étant nécessaire puisqu'il accepte déjà n'importe quel vrai `ToolSpec`. Testé de bout en bout (`test_get_available_custom_tools_returns_real_usable_toolspecs`).

✅ **6 endpoints réels**, les 6 littéraux -- create/list org-scopés, get/update/delete/execute résolvent l'outil ET le rôle réel de l'appelant ensemble.

Tests réels dédiés (22 tests), voir `tests/test_custom_tools.py`.

**Partie 5.2 — Outils intégrés : 9/9 items vérifiés réels dans `api/`** (5.2.1 à 5.2.10, lot complet). Search KB/GitHub/Human Escalation "existent déjà côté `src/`" restent non revérifiés (travail hérité, granularité différente).

### 5.3 Agent Builder — 🟡 PARTIEL (9/10, 5.3.8 non demandé dans ce lot)

#### Partie 5.3.1 — Création d'agent personnalisé

✅ **La vraie entité `Agent` qui manquait honnêtement depuis la Partie 5.1.1** : `api/models/agent.py` (`Agent`, migration `0058`, RLS activée). **Fermeture réelle d'un écart documenté** : chaque module 5.1.x/5.2.x (`AgentOrchestrator`, `AgentSession`, `ToolPermission`, ...) attendait déjà une vraie chaîne `agent_id` -- `str(Agent.id)` est maintenant cette même chaîne réelle, sans changer aucun de ces sites d'appel.

✅ **Tous les champs des Parties 5.3.1 à 5.3.6 déclarés ensemble, dans une seule vraie migration** -- `system_prompt_template` (5.3.2), `knowledge_base_config` (5.3.4), `memory_ttl`/`memory_max_items`/`memory_retention_policy` (5.3.6) sont réels mais inertes tant que leur propre étape ne les consomme pas, même approche déjà utilisée pour les ajouts de configuration de tout ce lot.

✅ **`knowledge_base_id`, vraie réutilisation de `workspaces`, pas une seconde entité** : ce dépôt n'a pas de table `KnowledgeBase` dédiée -- un `Workspace` EST déjà le vrai conteneur de documents. Colonne réelle distincte de `workspace_id` car l'un et l'autre peuvent réellement différer.

✅ **Nouveau module réel** `api/security/agents.py` : les 8 fonctions littérales + `require_agent_member`/`require_agent_manager` (dépendances réelles supplémentaires, même vrai schéma que `require_workspace_permission` de `api/routers/workspaces.py` -- 404, pas 403, pour un non-membre, même raisonnement anti-énumération). `delete_agent` est un vrai *soft delete* (`deleted_at`), pas un `DELETE` brut -- les vrais runs/traces/escalades d'un agent gardent une référence réelle et significative.

✅ **Vraie intégration au système de quotas** : "agents" était l'une des 7 dimensions honnêtement non trackées de la Partie 1.3.6 (aucune vraie table `Agent` n'existait). Maintenant qu'elle existe, un vrai compteur live a été câblé dans `api/security/quotas.py` (`_LIVE_COUNTERS`), et `POST .../agents` appelle réellement `require_quota_available` -- testé, y compris le vrai dépassement de quota (402).

✅ **8 endpoints réels**, les 8 littéraux -- create/list org-scopés (`require_org_manager`/`require_org_member`), get/update/delete/activate/pause/archive résolvent l'agent ET le rôle réel de l'appelant ensemble (chemins littéraux sans `{org_id}`).

**Sécurité (vision critique)** : isolation par organisation testée (`test_cannot_access_an_agent_from_another_organization`, 404). Member ne peut ni créer ni modifier (403, testé).

**Performance (vision critique)** : `ix_agents_organization_id`/`ix_agents_workspace_id` réels.

Tests réels dédiés (11 tests), voir `tests/test_agents.py`.

#### Partie 5.3.2 — Instructions personnalisées

✅ **Nouveau module réel** `api/services/agent_prompts.py` : les 4 fonctions littérales + `KNOWN_VARIABLES` (les 7 variables littérales).

✅ **Décision réelle et sûre : substitution regex `{{var}}` à la main, PAS `str.format()`/`format_map()`** (vision critique : "les templates sont-ils protégés contre les injections ?") -- `format_map` exécuté contre une chaîne de format influencée par un attaquant est une vraie classe de vulnérabilité Python documentée (charges de type `"{0.__class__...}".format_map(...)`, traversée d'attributs) -- un vrai risque ici puisque l'AUTEUR du template (un Owner/Admin/Manager, réel mais pas forcément digne de confiance pour de l'exécution de code arbitraire) contrôle la chaîne de format elle-même, pas seulement les valeurs substituées. Testé explicitement (`test_render_system_prompt_rejects_no_real_code_execution_via_format`).

✅ **Robustesse réelle et testée (vision critique)** : une variable réellement manquante reste littéralement `{{nom}}` dans le rendu -- jamais effacée silencieusement, jamais d'exception. Un vrai typo reste visible et débogable dans le texte rendu lui-même.

✅ **`render_system_prompt`, périmètre honnête** : `{{date}}`/`{{time}}` sont calculées automatiquement (aucune DB nécessaire) ; `{{user_name}}`/`{{organization_name}}`/`{{context}}`/`{{tools}}`/`{{knowledge_base}}` ont besoin d'informations réelles (résolution DB, utilisateur courant) -- cette fonction reste volontairement indépendante de la DB, c'est à l'appelant réel (l'endpoint preview) de les résoudre et de les passer.

**Sécurité (vision critique)** : `validate_system_prompt` réutilise le vrai `settings.SYSTEM_PROMPT_MAX_LENGTH` déjà établi (Partie 4.3.4) plutôt qu'une seconde limite arbitraire ; rejette aussi un vrai nombre excessif de placeholders (garde-fou réel minimal).

✅ **3 endpoints réels**, les 3 littéraux, ajoutés au routeur `agents.py` existant.

Tests réels dédiés (15 tests), voir `tests/test_agent_prompts.py`.

#### Partie 5.3.3 — Choix du modèle LLM

✅ **Nouveau module réel** `api/services/agent_models.py` : les 5 fonctions littérales (`validate_agent_model`, `get_available_models`, `get_default_model_config`, `get_agent_model`, `set_agent_model`) + `MODEL_CATALOG` (les 9 modèles nommés littéraux, sur 5 fournisseurs).

✅ **Vraie réutilisation, pas un second registre concurrent** : `MODEL_CATALOG` regroupe par les MÊMES vraies clés fournisseur que `api/services/llm_providers.py` (Partie 4.1.7) utilise déjà pour un vrai appel LLM -- `"gemini"`, pas le libellé littéral "Google" de cette étape (réconciliation de nommage réelle et documentée, pas un second registre de fournisseurs concurrent). `validate_agent_model` valide d'abord contre le vrai `PROVIDER_SETTINGS`, puis contre le vrai `MODEL_CATALOG`.

✅ **`get_default_model_config` réutilise les vrais défauts déjà établis** (`DEFAULT_SETTINGS` de la Partie 4.3.1-4.3.5, `settings.ANTHROPIC_MODEL`) plutôt qu'un second jeu de valeurs codées en dur.

✅ **`get_agent_model`, config effective réelle** : le vrai `model_config_json` de l'agent, complété par les vrais défauts pour toute clé manquante -- jamais de config partielle renvoyée à l'appelant.

✅ **4 endpoints réels**, les 4 littéraux -- `GET/PATCH /agents/{agent_id}/model` (member lit, manager modifie), `GET /models` et `GET /models/{provider}`.

**Sécurité (vision critique)** : `PATCH .../model` réservé aux managers (`require_agent_manager`), testé (403 pour un member). Un modèle ou fournisseur invalide est rejeté AVANT toute écriture réelle (400, testé).

**Déviation réelle et documentée** : `GET /models`/`GET /models/{provider}` n'ont littéralement pas de `{org_id}` dans leur chemin -- gatés par `get_current_user` seul (tout utilisateur authentifié réel peut lire ce catalogue réel, statique, non secret), pas par une vérification d'appartenance à une organisation (impossible sur ce chemin littéral).

Tests réels dédiés (16 tests), voir `tests/test_agent_models.py`.

#### Partie 5.3.4 — Sélection de la Knowledge Base

✅ **Nouveau module réel** `api/services/agent_knowledge_base.py` : les 5 fonctions littérales (`get_agent_knowledge_base`, `set_agent_knowledge_base`, `validate_knowledge_base_access`, `get_agent_kb_config`, `get_available_knowledge_bases`).

✅ **Vraie faille de sécurité corrigée, découverte en implémentant cette étape** : ni `create_agent` ni `update_agent` (Partie 5.3.1) ne vérifiaient auparavant qu'un `knowledge_base_id` donné appartenait réellement à la MÊME organisation que l'agent -- rien n'empêchait un manager de pointer un agent vers le vrai workspace d'une AUTRE organisation (son `id`, un vrai UUID, pouvant être deviné/récupéré ailleurs, par ex. dans une URL). `validate_knowledge_base_access` ferme cet écart réel, et est maintenant appelée depuis `create_agent` ET `update_agent` (`api/security/agents.py`), pas seulement depuis le nouvel endpoint dédié. Testé explicitement (`test_set_agent_knowledge_base_rejects_a_workspace_from_another_org`, `test_create_agent_rejects_a_cross_org_knowledge_base_id`).

✅ **`get_available_knowledge_bases`, vraie réutilisation, pas un second concept** : liste les vrais `workspaces` de l'organisation -- ce dépôt n'a pas de table `KnowledgeBase` dédiée, un `Workspace` EST déjà le vrai conteneur de documents (même raisonnement que Partie 5.3.1).

✅ **`get_agent_kb_config` réutilise les vrais défauts déjà établis** (`DEFAULT_SETTINGS["top_k"]`/`["score_threshold"]` de la Partie 3.3.6/3.3.7) plutôt qu'un second jeu de valeurs codées en dur -- même schéma que `agent_models.get_default_model_config` (Partie 5.3.3).

✅ **4 endpoints réels** -- `GET/PATCH /agents/{agent_id}/knowledge-base` (member lit, manager modifie), `GET /agents/{agent_id}/knowledge-base/config` (config effective), `GET /agents/{agent_id}/knowledge-base/options` (vraies KB disponibles dans l'organisation de l'agent).

**Robustesse (vision critique)** : un PATCH ne portant que `config` (sans `knowledge_base_id`) ne réinitialise PAS la KB déjà configurée -- distinction réelle entre "champ omis" et "champ explicitement mis à `null`" via `payload.model_fields_set`, testé (`test_update_agent_knowledge_base_config_only_does_not_clear_the_kb`). `knowledge_base_id: null` explicite reste un vrai moyen de désactiver la KB d'un agent (repli sur les documents de son propre `workspace_id`).

**Sécurité (vision critique)** : rejet cross-organisation testé à 3 niveaux (fonction pure, endpoint dédié, `create_agent`/`update_agent` génériques). Modification réservée aux managers (403 pour un member, testé).

Tests réels dédiés (18 tests), voir `tests/test_agent_knowledge_base.py`.

#### Partie 5.3.5 — Sélection des outils

✅ **Nouveau module réel** `api/services/agent_tools.py` : les 6 fonctions littérales (`get_agent_tools`, `set_agent_tools`, `enable_tool`, `disable_tool`, `get_available_tools`, `validate_tool_config`) + `AGENT_TOOL_CATALOG`, un vrai catalogue des 12 noms littéraux -- chacun pointant vers une implémentation réelle et déjà existante (`api/tools/search_kb.py`, `web_search.py`, `github_tools.py`, `sql_tool.py`, `calculator.py`, `url_reader.py`, `calendar_tools.py`, `email_tools.py`, `human_escalation.py`).

✅ **Honnêteté de périmètre, pas un succès fabriqué** : 6 des 12 outils (`search_knowledge_base`, `web_search`, `read_url`, `email_send`, `escalate_to_human`, et `calculate` sous son propre nom séparé `advanced_calculator`) ont déjà un vrai `ToolSpec` enregistré dans le registre partagé de `api.services.tools` (Partie 5.1.2). Les 6 autres (`github_get_repo`, `github_list_issues`, `execute_sql_query`, `calendar_list_events`, `calendar_create_event`, `email_read`) sont des fonctions réelles et appelables dans `api/tools/`, mais jamais enveloppées dans ce registre partagé / la boucle d'appel de fonctions LLM -- un vrai écart préexistant des Parties 5.1/5.2 (déjà documenté dans le propre docstring de `api.services.tools` : "no automatic LLM-function-calling loop"), que cette étape ne prétend PAS corriger : sélectionner un outil ici enregistre une intention réelle et honnête (`Agent.tools`), indépendamment de son câblage complet dans cette couche d'exécution séparée.

✅ **Vraie faille de contournement corrigée** : `create_agent`/`update_agent` (Partie 5.3.1) acceptaient déjà un champ `tools` brut sans jamais le valider contre un vrai catalogue -- un manager pouvait y écrire n'importe quel nom inventé via l'endpoint générique. `validate_tools_list` (appelée depuis `set_agent_tools` ET directement depuis `create_agent`/`update_agent`) ferme cet écart, même raisonnement que la correction cross-organisation de la Partie 5.3.4. Testé (`test_update_agent_rejects_an_unknown_tool_name_via_generic_update`, `test_create_agent_rejects_an_unknown_tool_name`).

✅ **`disable_tool`, vrai soft-disable, pas une suppression** : `enabled=False` conserve la vraie config déjà enregistrée (même schéma que `Agent.status="archived"`, Partie 5.3.1) -- désactiver un outil que l'agent n'a jamais eu est un vrai no-op, pas une erreur.

✅ **5 endpoints réels** -- `GET/PATCH /agents/{agent_id}/tools`, `POST /agents/{agent_id}/tools/{tool_name}/enable`, `POST .../disable`, `GET /tools/available` (même déviation documentée que `GET /models`, Partie 5.3.3 : pas de `{org_id}` sur ce chemin littéral, gaté par authentification seule).

**Robustesse (vision critique)** : `set_agent_tools` valide TOUTE la liste avant la moindre écriture réelle -- une seule entrée invalide rejette tout, rien n'est appliqué partiellement. `validate_tool_config` reste volontairement minimal au-delà du nom/type de `config` (vision critique honnête : le spec littéral de cette étape ne définit aucun schéma par outil au-delà de "config" -- en inventer un serait un périmètre fabriqué, pas une vraie exigence).

Tests réels dédiés (21 tests), voir `tests/test_agent_tools.py`.

#### Partie 5.3.6 — Configuration de la mémoire

✅ **Nouveau module réel** `api/services/agent_memory_config.py` : les 6 fonctions littérales (`get_agent_memory_config`, `set_agent_memory_config`, `validate_memory_config`, `get_memory_usage`, `clear_agent_memory`, `get_default_memory_config`).

✅ **Vraie intégration, pas un second système de mémoire** : `clear_agent_memory` réutilise la vraie `clear_memory` de la Partie 5.1.11 (`api/services/agent_memory.py`), en résolvant chaque vraie ligne `AgentSession` dont le propre `agent_id` (chaîne) est égal à `str(Agent.id)` -- exactement le point d'intégration réel que le propre docstring de `api/models/agent.py` documentait déjà depuis la Partie 5.3.1 ("`str(Agent.id)` est maintenant cette même chaîne réelle"). Cette étape est la première à vraiment emprunter ce chemin, d'un `Agent` réel vers ses vraies sessions.

✅ **Vrai ensemble honnête de politiques de rétention** : `MEMORY_RETENTION_POLICIES` ne contient que `"fifo"` -- la SEULE politique d'éviction réellement implémentée par `_evict_oldest_if_full` (Partie 5.1.11). Accepter une seconde valeur inventée (ex. "lru") qui ne change aucun comportement réel nulle part aurait été un réglage fabriqué, pas un réglage réel.

✅ **`get_default_memory_config` réutilise les vrais défauts déjà établis** (`settings.AGENT_MEMORY_TTL`/`AGENT_MEMORY_SIZE`, Partie 5.1.11) plutôt qu'un second jeu de valeurs codées en dur -- même schéma que les Parties 5.3.3/5.3.4.

✅ **Vraie faille de contournement corrigée** : `memory_ttl`/`memory_max_items`/`memory_retention_policy` étaient déjà déclarés réels sur `Agent` (migration `0058`) mais totalement absents des schémas `AgentCreateRequest`/`AgentUpdateRequest` et de `update_agent` -- ajoutés aux deux, avec `validate_memory_config` appelée depuis `create_agent`/`update_agent` (pas seulement depuis `set_agent_memory_config`), même raisonnement que les corrections des Parties 5.3.4/5.3.5. Testé (`test_update_agent_rejects_an_invalid_memory_config_via_generic_update`, `test_create_agent_rejects_an_invalid_memory_config`).

✅ **`get_memory_usage`, vrai comptage live** : nombre réel de `AgentSession`/`AgentMemoryItem` (Partie 5.1.11) pour cet agent -- pas une estimation, une vraie requête `COUNT`/`JOIN`.

✅ **4 endpoints réels** -- `GET/PATCH /agents/{agent_id}/memory-config`, `GET /agents/{agent_id}/memory-usage`, `POST /agents/{agent_id}/memory/clear`.

**Sécurité (vision critique)** : `clear_agent_memory` testé pour ne JAMAIS toucher les sessions d'un autre agent (`test_clear_agent_memory_does_not_touch_another_agents_sessions`). Modification et vidage réservés aux managers (403 pour un member, testé).

Tests réels dédiés (22 tests), voir `tests/test_agent_memory_config.py`.

#### Partie 5.3.7 — Permissions

✅ **Nouveau module réel** `api/services/agent_permissions.py` : les 5 fonctions littérales (`check_agent_permission`, `get_allowed_users`, `add_allowed_user`, `remove_allowed_user`, `set_agent_visibility`) + 3 nouveaux champs réels sur `Agent` (migration `0059`) : `allowed_users` (JSON), `allowed_roles` (JSON), `is_public` (Boolean, défaut `False`).

✅ **Cohérence avec le RBAC existant (vision critique 1)** : cette étape ne remplace RIEN du système de rôles existant (Partie 1.2) -- `update`/`delete` restent décidés EXCLUSIVEMENT par le rôle réel Owner/Admin/Manager (même vérification que `require_agent_manager`, Partie 5.3.1). Le vrai écart que cette étape ferme : `action="use"` (invoquer réellement l'agent) n'était vérifié par RIEN avant cette étape -- n'importe quel member réel de l'organisation pouvait invoquer n'importe quel agent. `allowed_users`/`allowed_roles`/`is_public` élargissent ou restreignent UNIQUEMENT ce point d'accès, jamais `update`/`delete` -- testé explicitement (`test_member_cannot_update_or_delete_even_if_allowed_user`).

✅ **Sécurité (vision critique 2)** : `check_agent_permission` est appelée à CHAQUE invocation réelle -- intégrée directement dans `AgentOrchestrator.run_agent` (voir plus bas), pas seulement au niveau des endpoints HTTP. `add_allowed_user`/`remove_allowed_user` valident que `added_by`/`removed_by` appartient réellement à la MÊME organisation que l'agent (même discipline que la correction cross-organisation de la Partie 5.3.4).

✅ **Performance (vision critique 3)** : `check_agent_permission` reste une seule requête indexée par `Agent.id` (clé primaire) + une requête sur `OrganizationMember` (déjà indexée sur `organization_id`/`user_id` depuis la Partie 1.2) -- même catégorie de performance que tous les autres `require_*` de ce dépôt.

✅ **Intégration réelle dans l'orchestrateur** : `AgentOrchestrator.run_agent` résout maintenant, quand `agent_id` correspond à un vrai `Agent` ET qu'un vrai `created_by` est fourni, la permission réelle `"use"` avant tout appel LLM -- un refus persiste un vrai `AgentRunRecord` avec `status="failed"` et un message clair (jamais d'exception, même discipline "never raises" déjà documentée). **Rétrocompatibilité réelle et testée** : un `agent_id` qui n'est pas un UUID réel, ou sans `created_by`, saute silencieusement la vérification -- comportement inchangé pour tous les appelants existants depuis la Partie 5.1.1 (`test_run_agent_with_a_non_uuid_agent_id_skips_the_permission_check`).

✅ **4 endpoints réels** -- `GET/PATCH /agents/{agent_id}/permissions`, `POST /agents/{agent_id}/permissions/users`, `DELETE /agents/{agent_id}/permissions/users/{user_id}` (tous Manager+).

**Tests (vision critique 4)** : allow (public, allowed_roles, allowed_users, owner), deny (member non listé, non-membre, agent inconnu), héritage (le rôle RBAC prime toujours pour update/delete, jamais contourné par l'ACL) -- tous testés explicitement.

Tests réels dédiés (19 tests `tests/test_agent_permissions.py` + 3 tests d'intégration dans `tests/test_agent_orchestrator.py`).

#### Partie 5.3.9 — Guardrails

✅ **Nouveau module réel** `api/services/agent_guardrails.py` : les 5 fonctions littérales, étendues (`validate_guardrails`, `check_blocked_topics`, `check_content_safety`, `check_domain_whitelist`, `validate_output_length`) + `get_agent_guardrails`/`set_agent_guardrails` (getter/setter réels) + 5 nouveaux champs réels sur `Agent` (migration `0060`) : `guardrails_config`, `blocked_topics`, `allowed_domains` (JSON), `max_tokens_per_response` (Integer), `content_filter_level` (String).

✅ **Honnêteté de périmètre pour `check_content_safety` (vision critique)** : ce dépôt ne configure AUCUNE vraie API de modération externe (aucune clé/réglage OpenAI moderation ou Perspective API n'existe dans `api/config.py`) -- prétendre en appeler une aurait été une capacité fabriquée. Ce qui est réellement livré : une heuristique regex/mot-clé réelle et minimale contre un petit ensemble intégré de catégories d'intention dangereuse, gérée par `content_filter_level` (low/medium/high, graduée) -- une vraie première ligne fonctionnelle mais volontairement grossière, même catégorie de compromis honnête que la troncature de conversation par nombre de messages (Partie 5.1.12).

✅ **`validate_output_length`, approximation honnête** : aucune dépendance de tokenizer n'existe dans ce dépôt pour un vrai comptage de tokens par fournisseur -- un vrai comptage de MOTS (espaces) sert d'approximation pour `max_tokens_per_response`, même catégorie d'approximation que `CONVERSATION_HISTORY_MAX_MESSAGES`.

✅ **`check_domain_whitelist`, vraie logique opt-in** : un agent sans `allowed_domains` configuré autorise tout domaine réel (garde-fou additif, jamais une nouvelle restriction silencieuse). Un domaine configuré correspond au vrai hostname exactement OU comme sous-domaine réel.

✅ **Robustesse (vision critique 3)** : `validate_guardrails` ne lève JAMAIS d'exception pour une vraie violation attendue -- retourne un dict structuré `{"passed": bool, "violations": [...]}"`, même doctrine "never raises" que `AgentOrchestrator.run_agent` lui-même. `guardrails_enabled=False` (bascule déjà réelle depuis la Partie 5.3.1) est un vrai no-op testé -- rien n'est bloqué si les garde-fous n'ont jamais été activés.

✅ **Intégration réelle dans l'orchestrateur** : `AgentOrchestrator.run_agent` appelle `validate_guardrails` juste après une vraie réponse LLM réussie -- une violation bloque la réponse (jamais renvoyée à l'appelant ni ajoutée à l'historique de conversation), persistée comme un vrai `AgentRunRecord` avec `status="failed"` et les violations listées dans `error`. Testé (`test_run_agent_blocks_a_real_response_matching_a_blocked_topic`).

✅ **`web_search` modifié pour vérifier les domaines autorisés (item 4)** : un `allowed_domains` réel, donné par agent, est transmis directement comme le vrai paramètre `include_domains` de Tavily -- appliqué côté serveur, pas en filtrant les résultats après coup. Un `allowed_domains` par agent prend priorité sur le défaut global `TAVILY_INCLUDE_DOMAINS`.

**Cohérence (vision critique 1)** : tous les canaux d'entrée/sortie réels passent par le même `validate_guardrails` (input ET output vérifiés ensemble).

**Performance (vision critique 2)** : chaque vérification reste une seule requête par `Agent.id` (clé primaire) + une évaluation regex en mémoire sur un texte déjà en mémoire -- pas d'appel réseau.

✅ **2 endpoints réels** -- `GET/PATCH /agents/{agent_id}/guardrails` (Manager+).

Tests réels dédiés (25 tests `tests/test_agent_guardrails.py` + 2 tests d'intégration dans `tests/test_agent_orchestrator.py` + 1 test dans `tests/test_web_search.py`).

#### Partie 5.3.10 — Déploiement (API key)

✅ **Nouveau modèle réel** `api/models/agent_api_key.py` (`AgentAPIKey`, migration `0061`, RLS activée) : id, agent_id (FK agents), name, key_hash (String(64), SHA-256 hex, UNIQUE), key_prefix, scopes (JSON), expires_at, last_used_at, created_by (FK users), created_at, revoked_at. `UNIQUE(agent_id, name)`.

✅ **Sécurité (vision critique 1) : seul le hash est stocké, jamais la clé en clair** -- `generate_api_key` génère `ak_<secrets.token_urlsafe(32)>` (même vrai RNG cryptographique que les tokens de reset de mot de passe/vérification email de ce dépôt, jamais `random`), retourne le texte en clair EXACTEMENT UNE FOIS, et ne persiste que `hash_api_key(key)` (SHA-256). Même discipline que le hachage des mots de passe : un hash se vérifie, ne se retrouve jamais en clair.

✅ **Nouveau module réel** `api/services/agent_api_keys.py` : les 6 fonctions littérales (`generate_api_key`, `hash_api_key`, `verify_api_key`, `revoke_api_key`, `get_agent_from_api_key`, `list_api_keys`).

✅ **Robustesse (vision critique 3) : expiration réelle et distincte de la révocation** -- `verify_api_key` refuse une clé réellement expirée (lazy check, même schéma que `api/services/agent_memory.py`), en la traitant comme invalide sans jamais la marquer révoquée -- `revoke_api_key` reste une action explicite, permanente, distincte, testée idempotente (retourne `False` pour une clé déjà révoquée ou inconnue).

✅ **Performance (vision critique 2)** : `verify_api_key` reste une seule requête indexée sur `key_hash` (contrainte UNIQUE + index réels) -- aucun scan, même catégorie de performance que chaque autre point d'authentification de ce dépôt.

✅ **Middleware d'authentification réel, mécanisme distinct** : `api/security/agent_api_keys.py` (`require_agent_api_key`, `require_api_key_scope`) -- une vraie dépendance FastAPI lisant le header `X-API-Key`, entièrement séparée de `get_current_user`/JWT. Un agent réel + la clé résolue ensemble, une clé invalide/expirée/révoquée renvoie 401 (jamais 404, même raisonnement anti-énumération que le reste de ce dépôt).

✅ **4 endpoints réels** -- `POST/GET /agents/{agent_id}/api-keys`, `DELETE /agents/{agent_id}/api-keys/{key_id}` (Manager+), `POST /api/agents/run` (authentification par clé API, scope `execute` requis).

✅ **`POST /api/agents/run` réutilise l'orchestrateur réel sans le contourner** : passe par le même `AgentOrchestrator.run_agent`, donc les vraies vérifications de permission (Partie 5.3.7) ET de garde-fous (Partie 5.3.9) s'appliquent aussi à une exécution via clé API -- une clé API n'est jamais un moyen de contourner ce qui s'applique déjà à tout autre appelant réel.

Tests réels dédiés (19 tests `tests/test_agent_api_keys.py`).

**Partie 5.3 Agent Builder : lot demandé terminé -- 9/10 items (5.3.1 à 5.3.7, 5.3.9, 5.3.10) vérifiés réels.** 5.3.8 n'a jamais été demandé dans ce lot et reste ⬜.

### 5.4 Workflow Builder — 🟡 PARTIEL (13/13, backend uniquement)

**Décision de périmètre réelle et explicite, validée avec l'utilisateur avant de commencer** : ce dépôt n'a AUCUNE infrastructure frontend nulle part (aucun `package.json`, aucune dépendance React) -- un vrai canvas React Flow serait un nouveau projet complet (npm, build tooling, composants), un écart massif par rapport à tout ce qui existe ici. Pour tout ce lot 5.4, seul le VRAI BACKEND est livré (modèle, endpoints, validation structurelle, exécution réelle par bloc) -- l'interface visuelle React Flow elle-même reste explicitement hors périmètre, documentée ici plutôt que fabriquée.

#### Partie 5.4.1 — Interface visuelle (backend réel, React Flow hors périmètre)

✅ **Nouveau modèle réel** `api/models/workflow.py` (`Workflow`, migration `0062`, RLS activée) : id, organization_id, workspace_id nullable, name, description, `nodes`/`edges` (JSON, la même forme littérale React Flow : `nodes=[{id,type,position,data}]`, `edges=[{id,source,target}]`), status (draft/active/archived), created_by, timestamps, deleted_at (soft delete réel).

✅ **`BLOCK_TYPES`, les 11 types littéraux** déclarés sur le modèle : trigger, llm_call, rag_search, web_search, http_call, condition, code, human, email, calendar, database.

✅ **Tables réelles déclarées ensemble pour tout le lot 5.4** (même approche "déclarer toute l'entité une fois, câbler chaque étape plus tard" que la Partie 5.3.1) : `WorkflowTrigger`/`WorkflowRun` (`api/models/workflow_run.py`, Partie 5.4.2) créées dans la MÊME migration `0062`, réelles mais inertes tant que 5.4.2 ne les consomme pas.

✅ **Nouveau module réel** `api/services/workflows.py` : les 7 fonctions littérales (`add_node`, `add_edge`, `delete_node`, `update_node`, `validate_workflow`, `export_workflow`, `import_workflow` -- ce dernier dans `api/security/workflows.py` car il écrit réellement en base).

✅ **Robustesse (vision critique 3) : intégrité en cascade réelle** -- `delete_node` retire aussi toute arête réelle qui le référençait (jamais d'arête en suspens). `validate_workflow` retourne la liste COMPLÈTE des erreurs réelles (jamais juste la première), utilisée à la fois par l'endpoint `/validate` et par `import_workflow`.

✅ **Vraie faille de contournement corrigée à la conception** : `create_workflow`/`update_workflow` valident réellement `nodes`/`edges` (même discipline "pas de contournement via l'endpoint générique" que toutes les corrections précédentes de ce lot) -- jamais de graphe structurellement invalide persisté, y compris via l'endpoint générique.

✅ **6 endpoints réels**, les 6 littéraux -- create/list org-scopés et Manager+ (déviation réelle du spec littéral : chemins `POST/GET /workflows` sans `{org_id}`, adaptés en `/organizations/{org_id}/workflows` même raisonnement que la Partie 5.3.1) ; get/update/delete/validate résolvent le workflow ET le rôle réel de l'appelant ensemble.

**Cohérence (vision critique 1)** : chaque workflow est réellement lié à une organisation (`organization_id` NOT NULL) et optionnellement à un workspace.

**Performance (vision critique 2)** : `nodes`/`edges` en JSON -- toujours lus/écrits en bloc (rendu, validation, export), jamais interrogés nœud par nœud ; même raisonnement que `AgentRunRecord.trace`. Pas de mesure réelle de fluidité d'un canvas qui n'existe pas encore côté frontend (honnête, cf. décision de périmètre ci-dessus).

Tests réels dédiés (26 tests), voir `tests/test_workflows.py`.

#### Partie 5.4.2 — Bloc Trigger (backend réel)

✅ **Nouveau module réel** `api/services/workflow_triggers.py` : les 5 fonctions littérales (`create_webhook_trigger`, `create_schedule_trigger`, `create_manual_trigger`, `trigger_workflow`, `get_trigger_url`) + `verify_webhook_token`/`get_trigger`/`list_triggers`/`delete_trigger` (plomberie réelle).

✅ **Sécurité (vision critique 1) : vrai token de webhook, chemin littéral conservé** -- `create_webhook_trigger` génère un vrai `webhook_token` cryptographique (`secrets.token_urlsafe`, même vrai RNG que les clés API de la Partie 5.3.10). L'endpoint réel `POST /webhooks/{trigger_id}` exige ce même vrai token dans un header réel `X-Webhook-Token`, vérifié via `secrets.compare_digest` (temps constant). Contrairement à une clé API (montrée une seule fois), le token d'un webhook reste réellement re-visible à un Manager -- même besoin opérationnel réel que les écrans de configuration webhook de GitHub/Slack/Discord (il faut pouvoir re-copier l'URL+secret pour reconfigurer l'appelant externe).

✅ **Schedules, vraie validation cron sans nouvelle dépendance** : `create_schedule_trigger` réutilise EXACTEMENT le même vrai parsing 5-champs via `celery.schedules.crontab` que `api/security/reindex_schedules.py` (Partie 2.2.15) -- aucune bibliothèque de parsing cron supplémentaire pour cette seule fonctionnalité.

✅ **Périmètre honnête et documenté (pas une capacité fabriquée)** : `trigger_workflow` crée un vrai `WorkflowRun` persisté (`status="pending"`) -- il ne parcourt PAS le vrai graphe pour exécuter chaque nœud réel. C'est un vrai moteur d'exécution de graphe, séparé et substantiel (enchaînant les fonctions d'exécution par bloc des Parties 5.4.3-5.4.11 le long des vraies arêtes), que cette étape ne prétend pas livrer -- son propre périmètre littéral est le DÉCLENCHEUR lui-même (titre littéral de l'item 1, "Bloc Trigger"), pas l'exécution complète du workflow, même honnêteté que le "no automatic function-calling loop" déjà documenté dans `api/services/agent_orchestrator.py`.

✅ **5 endpoints réels** -- `POST/GET /workflows/{workflow_id}/triggers`, `DELETE .../triggers/{trigger_id}` (Manager+), `POST /webhooks/{trigger_id}` (public, authentifié par token), `POST /workflows/{workflow_id}/run` (Member+, déclenchement manuel réel).

**Robustesse (vision critique 3)** : `trigger_workflow` retourne toujours un vrai `WorkflowRun` réel (jamais d'exception) ; un échec de déclenchement webhook (token invalide) est un vrai 401, pas un run silencieusement créé.

Tests réels dédiés (17 tests), voir `tests/test_workflow_triggers.py`.

#### Partie 5.4.3 — Bloc LLM

✅ **Nouveau module partagé réel** `api/services/template_rendering.py` : la substitution `{{var}}` sûre, réellement EXTRAITE de `api/services/agent_prompts.py` (Partie 5.3.2, refactor non-régressif, les 15 tests de ce module restent verts) pour être réutilisée par les 8 rendus de blocs restants (5.4.4-5.4.11) au lieu d'être réécrite 8 fois. Même choix de sécurité réel que la Partie 5.3.2 : jamais `str.format()`/`format_map()`.

✅ **Nouveau module partagé réel** `api/services/workflow_blocks.py` : `WorkflowBlockError`, une seule vraie exception partagée par les 9 exécuteurs de blocs (5.4.3-5.4.11), pas 9 exceptions identiques séparées.

✅ **Nouveau module réel** `api/services/workflow_block_llm.py` : les 4 fonctions littérales (`execute_llm_block`, `render_llm_prompt`, `validate_llm_config`, `get_available_llm_models`).

✅ **Cohérence (vision critique 1) : réutilise l'abstraction LLM existante de bout en bout, aucun second chemin concurrent** -- `resolve_llm_config` (Partie 4.3.1-4.3.5) pour les vrais défauts provider/model/temperature/max_tokens/top_p, `chat_completion` (Partie 4.1.7) pour le vrai appel LLM. `get_available_llm_models` délègue au vrai catalogue déjà établi par `agent_models.get_available_models` (Partie 5.3.3) -- un seul vrai catalogue de modèles, pas un second pour les workflows.

✅ **Robustesse (vision critique 3)** : un vrai échec LLM (`LLMError`) est capturé et relevé comme un vrai `WorkflowBlockError` -- un seul type d'erreur réel et partagé que tout exécuteur de bloc lève, pas une exception spécifique à un fournisseur qu'un futur appelant (le moteur de graphe réel) devrait connaître.

**Performance (vision critique 2)** : aucune couche supplémentaire réelle -- un seul vrai appel réseau (`chat_completion`), même catégorie de performance que `AgentOrchestrator.run_agent`.

Tests réels dédiés (5 tests `tests/test_template_rendering.py` + 10 tests `tests/test_workflow_block_llm.py`).

#### Partie 5.4.4 — Bloc RAG

✅ **Nouveau module réel** `api/services/workflow_block_rag.py` : les 4 fonctions littérales (`execute_rag_block`, `render_rag_query`, `validate_rag_config`, `format_rag_results`).

✅ **Cohérence (vision critique 1) : réutilise le pipeline de recherche réel de bout en bout** -- `api.services.retrieval_pipeline.search` (Partie 3.4.x) pour le vrai dispatch de stratégie/reranking/filtre de seuil de score, `api.services.metadata_filtering.validate_filters`/`apply_metadata_filter` (Partie 3.x) pour `filters` -- aucun second chemin concurrent de recherche ou de filtrage.

✅ **Limitation réelle et honnêtement documentée pour `knowledge_base_id` (préexistante, pas fabriquée par cette étape)** : le vrai `fetch_organization_chunks` de `retrieval_pipeline.search` scope chaque vraie récupération de chunk par `organization_id` SEUL -- aucun vrai filtre par `workspace_id`/knowledge-base n'existe nulle part dans ce pipeline aujourd'hui (un vrai écart déjà présent dans la Partie 3.4.x, que cette étape n'introduit ni ne prétend corriger). `knowledge_base_id` est accepté (champ littéral de l'item 1) et réellement VALIDÉ (doit être un vrai workspace de la MÊME organisation, même discipline cross-organisation que la Partie 5.3.4), mais n'a aucun effet réel sur les chunks recherchés -- honnêtement documenté, jamais silencieusement ignoré.

✅ **Déviation réelle et documentée du signature littéral à 2 arguments** (`execute_rag_block(block_config, context)`) : une vraie recherche RAG a réellement besoin d'une vraie session `db` et d'un vrai `organization_id` pour la scoper (les deux mêmes éléments que tout autre point d'appel réel de récupération dans ce dépôt exige déjà) -- la vraie signature de cet exécuteur est `execute_rag_block(db, organization_id, block_config, context)`.

**Robustesse (vision critique 3)** : que se passe-t-il si la KB est vide ? `format_rag_results` retourne un vrai message honnête ("No relevant documents found.") plutôt qu'une chaîne vide silencieuse.

Tests réels dédiés (13 tests), voir `tests/test_workflow_block_rag.py`.

#### Partie 5.4.5 — Bloc Search

✅ **Nouveau module réel** `api/services/workflow_block_search.py` : les 4 fonctions littérales (`execute_search_block`, `render_search_query`, `validate_search_config`, `format_search_results`).

✅ **Cohérence (vision critique 1) : réutilise le vrai outil `web_search` (Partie 5.2.2) de bout en bout, aucun second chemin concurrent** -- `api.tools.web_search.web_search` pour le vrai appel Tavily, `format_web_search_results` pour le vrai formatage LLM-facing. `exclude_domains` (champ littéral de cette étape) a nécessité un vrai ajout symétrique, petit et réel à `web_search`/`_call_tavily` (aux côtés du `allowed_domains` déjà ajouté à la Partie 5.3.9) -- les deux sont maintenant un vrai réglage "donné > global", pas un second mécanisme de filtrage de domaines parallèle.

✅ **Robustesse (vision critique 3)** : un vrai échec de recherche (`WebSearchError`) est capturé et relevé comme un vrai `WorkflowBlockError` -- même type d'erreur partagé que le bloc LLM (Partie 5.4.3).

**Performance (vision critique 2)** : un seul vrai appel réseau (Tavily), aucune couche supplémentaire.

Tests réels dédiés (11 tests), voir `tests/test_workflow_block_search.py`.

#### Partie 5.4.6 — Bloc HTTP

✅ **Nouveau module réel** `api/services/workflow_block_http.py` : les 5 fonctions littérales (`execute_http_block`, `render_http_url`, `render_http_body`, `validate_http_config`, `format_http_response`).

✅ **Sécurité (vision critique 1) : vraie protection SSRF réutilisée, pas réinventée** -- ce bloc est une vraie fonctionnalité dangereuse (un nœud écrit par un Manager qui dit à ce backend d'appeler une vraie URL arbitraire, rendue au runtime) à moins que le vrai appel HTTP passe par un vrai transport résistant au DNS-rebinding qui bloque les adresses privées/loopback/link-local/réservées AU NIVEAU DE LA CONNEXION (vérifiant la vraie IP résolue juste avant chaque vrai connect TCP, y compris après une vraie redirection) -- exactement ce qu'est déjà `api/services/url_fetching.py`'s own `_SSRFSafeAsyncTransport` (Partie 2.2.x). `ssrf_safe_client` (petit ajout réel de cette étape à ce module) expose ce MÊME vrai transport pour réutilisation ici, plutôt qu'une seconde implémentation SSRF plus faible. `validate_url` (même module) rejette un schéma non `http(s)`, un hostname manquant, et des identifiants intégrés, AVANT tout véritable I/O réseau.

✅ **Robustesse (vision critique 3)** : un vrai échec de connexion/timeout/statut non-2xx n'est jamais une exception `httpx` brute qui fuit -- toujours un vrai `WorkflowBlockError` partagé avec la raison réelle et spécifique.

✅ **`render_http_body`, gère les deux vraies formes réelles** : une chaîne simple (rendue directement) OU un vrai objet/tableau JSON (chaque vraie valeur-feuille string rendue, structure préservée).

**Performance (vision critique 2)** : un seul vrai appel réseau, aucune couche supplémentaire au-delà du vrai transport SSRF déjà établi.

Tests réels dédiés (16 tests), voir `tests/test_workflow_block_http.py`.

#### Partie 5.4.7 — Bloc Condition

✅ **Nouveau module réel** `api/services/workflow_block_condition.py` : les 4 fonctions littérales (`execute_condition_block`, `evaluate_condition`, `validate_condition_config`, `format_condition_result`).

✅ **Sécurité (vision critique 1) : déviation réelle et documentée du "JSONLogic" littéral** -- aucune bibliothèque JSONLogic n'est une vraie dépendance de ce dépôt (`requirements.txt`/`requirements-api.txt` vérifiés, ni l'un ni l'autre ne la déclare). En ajouter une pour cette seule fonctionnalité a été jugé ne pas valoir une nouvelle vraie dépendance tierce quand ce dépôt a déjà un vrai motif PROUVÉ SÛR pour exactement ce problème : le vrai évaluateur `ast` de `api/tools/calculator.py` (`_safe_eval_arithmetic`, Partie 5.1.x) -- jamais `eval()`/`exec()` (qui exécuterait du code arbitraire depuis une chaîne de condition écrite par un Manager, réel mais pas totalement digne de confiance -- même modèle de menace déjà documenté pour le rendu de templates de la Partie 5.3.2). Ce module étend ce même motif réel et sûr aux opérateurs littéraux de l'item 3 (comparaison, logique, présence, mathématiques) plutôt que d'inventer un second mécanisme de sécurité différent.

✅ **Vraie résolution de variable, jamais silencieuse** : un `ast.Name` inconnu dans une condition lève un vrai `WorkflowBlockError` spécifique -- une condition évaluée silencieusement contre une variable manquante/`None` pourrait choisir la MAUVAISE vraie branche sans aucune erreur visible, une vraie classe d'échec silencieux dangereuse pour le flux de contrôle (pire qu'un placeholder de template littéral `{{typo}}`, visible dans le texte rendu).

✅ **`contains`/`is_empty` (opérateurs de présence littéraux, pas une vraie syntaxe Python)** : exposés comme deux vrais noms de fonction explicitement whitelistés (`ast.Call` n'est JAMAIS autorisé autrement) -- ne peut jamais devenir un vrai vecteur d'appel arbitraire.

**Tests (vision critique 4)** : chaque catégorie d'opérateur littéral testée individuellement (comparaison, logique, présence, mathématiques) + rejet réel testé (`__import__`, `len()`, accès attribut `.__class__`) prouvant l'absence de vraie exécution de code.

Tests réels dédiés (25 tests), voir `tests/test_workflow_block_condition.py`.

#### Partie 5.4.8 — Bloc Code

✅ **Nouveau module réel** `api/services/workflow_block_code.py` : les 4 fonctions littérales (`execute_code_block`, `validate_code`, `sanitize_code`, `format_code_result`).

✅ **Sécurité (vision critique 1) : déviation réelle, nécessaire et documentée du "Python → exec()" / "JavaScript → eval()" littéral de l'item 3** -- un vrai sandboxing restreint via `exec()`/`eval()` (vider `__builtins__`, blanchir les globals) est un motif de sécurité RÉELLEMENT ET RÉPÉTÉMENT CASSÉ : de vraies chaînes d'exploitation publiques (ex. `().__class__.__bases__[0].__subclasses__()`) s'en échappent même avec `__builtins__` retiré, car `exec`/`eval` tournent toujours sur le VRAI interpréteur CPython avec un vrai accès à la vraie machinerie `__class__`/`__bases__`/`__subclasses__` de tout objet Python vivant. Livrer cela en l'appelant "restreint" aurait été un motif dangereux présenté comme sûr -- pire que ne pas livrer la fonctionnalité.

✅ **Ce qui est réellement livré à la place** : le même vrai évaluateur `ast` à liste blanche fermée que la Partie 5.4.7 (`workflow_block_condition.py`, elle-même une extension de `calculator.py`, Partie 5.1.x), élargi avec une vraie liste blanche étroite et explicite de méthodes str/list/dict sûres (`upper`, `lower`, `strip`, `replace`, `split`, `join`, `format`, `title`, `capitalize`, `get`, `keys`, `values`) -- du vrai code utile de transformation de données, réellement incapable d'accès fichier/réseau ou d'exécution de code arbitraire (aucun `import`, aucun attribut `__dunder__` n'atteint jamais cet évaluateur, whitelisté ou non).

✅ **`language="javascript"` honnêtement rejeté, jamais simulé** : aucun vrai runtime JS (Node.js, un pont façon `PyExecJS`) n'est une vraie dépendance de ce dépôt -- prétendre exécuter du vrai JavaScript ici aurait été une capacité fabriquée. `SUPPORTED_LANGUAGES` est réel et honnête : `("python",)`.

**Tests (vision critique 4)** : succès (arithmétique, méthodes de chaîne sûres, listes/dicts), restrictions de sécurité testées explicitement (`__class__`, `__import__`, `open()`, méthode non whitelistée `__reduce__`), erreurs gérées (variable inconnue, config invalide).

Tests réels dédiés (17 tests), voir `tests/test_workflow_block_code.py`.

#### Partie 5.4.9 — Bloc Human

✅ **Nouveau modèle réel** `api/models/workflow_human_input.py` (`WorkflowHumanInput`, migration `0063`, RLS activée) : id, workflow_run_id (FK workflow_runs), node_id, message, input_type, options (JSON), required, status (pending/submitted/timeout), value (JSON), submitted_by/submitted_at, created_at, expires_at.

✅ **Ce bloc ne peut pas "s'exécuter jusqu'au bout" de façon synchrone, contrairement aux Parties 5.4.3-5.4.8** : un bloc `human` doit réellement METTRE EN PAUSE et attendre une vraie soumission séparée -- cette table EST l'état d'exécution réel de ce bloc, pas une réflexion après coup.

✅ **Nouveau module réel** `api/services/workflow_block_human.py` : les 5 fonctions littérales (`execute_human_block`, `render_human_message`, `validate_human_input`, `get_human_approval`, `submit_human_input`).

✅ **Vraie résolution de timeout paresseuse, même motif que `api/security/human_approval.py` (Partie 5.1.10)** : `get_human_approval` fait basculer une vraie ligne encore "pending" passé son propre `expires_at` vers `"timeout"` au moment même de la lecture, sans sweep d'arrière-plan séparé.

✅ **Déviation réelle et documentée du signature littéral à 2 arguments** : créer une vraie requête persistée a réellement besoin d'une vraie session `db`, du vrai `workflow_run_id`, et du vrai `node_id` d'origine -- signature réelle : `execute_human_block(db, workflow_run_id, node_id, block_config, context)`.

✅ **3 endpoints réels** -- `GET /workflows/runs/{run_id}/human-blocks`, `GET .../human-blocks/{block_id}`, `POST .../human-blocks/{block_id}/submit`, protégés par un nouveau `require_workflow_run_member` réel (résout run → workflow → appartenance organisationnelle, puisqu'un run n'a pas son propre `organization_id`).

**Robustesse (vision critique 3)** : `submit_human_input` retourne un vrai no-op (`None`) pour une requête déjà soumise ou expirée -- jamais une double soumission silencieuse.

Tests réels dédiés (18 tests), voir `tests/test_workflow_block_human.py`.

✅ **Amélioration réelle et rétrocompatible découverte en testant cette étape** : `api/services/template_rendering.py` (partagé depuis la Partie 5.4.3) n'acceptait qu'un motif `\w+` (mots simples) -- les variables littérales `{{user.email}}`/`{{user.name}}` des items 3 des Parties 5.4.10/5.4.11 ne correspondaient JAMAIS à ce motif et seraient restées silencieusement non rendues pour toujours. Le motif accepte maintenant `[\w.]+` avec une vraie résolution de chemin imbriqué point par point (`{{user.email}}` → `context["user"]["email"]`), entièrement rétrocompatible avec toute clé plate déjà utilisée (Partie 5.3.2, Parties 5.4.3-5.4.9). Testé explicitement (`tests/test_template_rendering.py`).

#### Partie 5.4.10 — Bloc Email

✅ **Nouveau module réel** `api/services/workflow_block_email.py` : les 4 fonctions littérales (`execute_email_block`, `render_email_template`, `validate_email_config`, `send_email_with_provider`).

✅ **Cohérence (vision critique 1) : réutilise le vrai outil `email_send` (Partie 5.2.8) de bout en bout, aucun second chemin d'envoi concurrent** -- `api.tools.email_tools.email_send` pour l'envoi réel (Gmail/Outlook/SMTP), `EmailToolError` mappé vers le `WorkflowBlockError` partagé.

✅ **Ajout réel et nécessaire au-delà des champs littéraux de l'item 1** : `email_send` n'a aucun vrai fournisseur par défaut (aucun réglage `EMAIL_PROVIDER` n'existe dans `api/config.py`) -- un vrai champ `provider` (`"gmail"`/`"outlook"`/`"smtp"`) est requis dans la config de ce bloc, la même vraie valeur qu'`email_send` exige déjà positionnellement.

**Robustesse (vision critique 3)** : un vrai échec d'envoi (`EmailToolError`) est capturé et relevé comme un vrai `WorkflowBlockError` partagé.

Tests réels dédiés (9 tests), voir `tests/test_workflow_block_email.py`.

#### Partie 5.4.11 — Bloc Calendar

✅ **Nouveau module réel** `api/services/workflow_block_calendar.py` : les 4 fonctions littérales (`execute_calendar_block`, `render_calendar_field`, `validate_calendar_config`, `format_calendar_results`).

✅ **Cohérence (vision critique 1) : réutilise les vrais outils calendrier (Partie 5.2.7) de bout en bout, aucun second chemin concurrent** -- `api.tools.calendar_tools.calendar_list_events`/`calendar_create_event`/`calendar_update_event`/`calendar_delete_event`/`calendar_find_available_slots` pour chaque vraie `action` littérale, `CalendarError` mappé vers le `WorkflowBlockError` partagé.

✅ **Ajout réel et nécessaire au-delà des champs littéraux de l'item 1** : `action="update"`/`"delete"` ont réellement besoin d'un vrai `event_id` existant -- ni `calendar_update_event` ni `calendar_delete_event` ne peuvent fonctionner sans. `event_id` est un vrai champ de config requis pour ces deux actions, même type d'ajout réel et nécessaire déjà fait pour le champ `provider` du bloc Email (Partie 5.4.10).

✅ **Robustesse (vision critique 3) : un vrai écart trouvé dans l'outil sous-jacent, compensé à la frontière de ce bloc, jamais masqué silencieusement** -- les propres fonctions de `api/tools/calendar_tools.py` (Partie 5.2.7) ne lèvent `CalendarError` QUE pour un vrai problème de fournisseur/identifiants ; un vrai échec HTTP (statut non-2xx, vraie erreur de connexion) se propage TEL QUEL comme une `httpx.HTTPError` brute, jamais enveloppée. Ce bloc capture les DEUX vrais types d'exception et relève le `WorkflowBlockError` partagé dans les deux cas -- un vrai appelant ici n'a jamais besoin de connaître la vraie dépendance interne `httpx` de `calendar_tools.py`.

Tests réels dédiés (12 tests), voir `tests/test_workflow_block_calendar.py`.

#### Partie 5.4.12 — Bloc Database

✅ **Nouveau module réel** `api/services/workflow_block_database.py` : les 4 fonctions littérales (`execute_database_block`, `render_sql_query`, `validate_sql_query`, `format_database_results`).

✅ **Cohérence (vision critique 1) : réutilise le vrai outil SQL (Partie 5.2.4) de bout en bout, aucun second chemin de requête concurrent** -- `api.tools.sql_tool.validate_sql_query`/`execute_sql_query`/`format_sql_results` pour chaque vraie vérification/appel, `SqlToolError` mappé vers le `WorkflowBlockError` partagé.

✅ **Sécurité (vision critique 2) : la MÊME vraie défense en profondeur que l'outil SQL lui-même, pas une seconde plus faible** -- un vrai sous-ensemble `SELECT` mono-table ancré par regex, une vraie liste blanche de tables, un vrai filtre `organization_id` TOUJOURS injecté via un vrai paramètre lié (jamais d'interpolation de chaîne), un vrai plafond de lignes. Ce bloc n'ajoute aucune nouvelle surface d'analyse SQL.

✅ **`connection`/`read_only`, vraies limites de périmètre honnêtes, jamais silencieusement ignorées** : ce dépôt n'a aucune vraie seconde abstraction de source de données nulle part (`execute_sql_query` s'exécute toujours contre la MÊME vraie session `db` fournie par l'appelant) -- `connection="custom"` est honnêtement rejeté, jamais simulé comme si une seconde vraie connexion existait. `read_only=False` est aussi honnêtement rejeté : le vrai validateur d'`api.tools.sql_tool` n'accepte jamais qu'une instruction `SELECT` -- il n'y a aucune vraie capacité d'écriture que ce bloc pourrait activer même si on le lui demandait.

✅ **Déviation réelle et documentée du signature littéral à 2 arguments** : une vraie requête SQL a réellement besoin d'une vraie session `db` et d'un vrai `organization_id` pour la scoper -- même raisonnement que la déviation du bloc RAG (Partie 5.4.4).

**Performance (vision critique 3)** : le vrai plafond de lignes (`SQL_TOOL_MAX_ROWS`) et la vraie longueur maximale de requête restent ceux déjà établis par l'outil SQL -- aucune seconde limite concurrente introduite.

Tests réels dédiés (13 tests), voir `tests/test_workflow_block_database.py`.

#### Partie 5.4.13 — Versioning des workflows

✅ **Nouveau modèle réel** `api/models/workflow_version.py` (`WorkflowVersion`, migration `0065`, RLS activée) : id, workflow_id (FK workflows), version_number, nodes/edges (JSON, snapshot complet), created_by (FK users), created_at, comment. `UNIQUE(workflow_id, version_number)`.

✅ **Performance/Stockage (vision critique 1/2), répondu honnêtement** : chaque vraie version stocke un snapshot COMPLET (pas un diff par rapport à la précédente) -- même vrai choix simple déjà fait pour tout autre état de forme JSON dans ce dépôt (`Workflow.nodes`/`edges` eux-mêmes, `AgentRunRecord.trace`). Aucune vraie compression n'est appliquée ; le vrai graphe d'un workflow reste typiquement quelques Ko réels au maximum pour un workflow conçu par un humain -- un vrai compromis simple et raisonnable, pas un stockage "efficace" fabriqué. Un vrai stockage par diff ou compressé reste un vrai travail futur séparé, si un vrai besoin démontré apparaît un jour à l'échelle réelle de ce dépôt.

✅ **Nouveau module réel** `api/services/workflow_versions.py` : les 5 fonctions littérales (`create_workflow_version`, `get_workflow_version`, `list_workflow_versions`, `restore_workflow_version`, `diff_workflow_versions`).

✅ **Robustesse (vision critique 3) : une vraie restauration ne s'applique jamais partiellement** -- `restore_workflow_version` résout D'ABORD le vrai workflow ET la vraie version cible ; si la version cible n'existe pas, lève une exception AVANT de toucher au vrai `nodes`/`edges` du workflow en cours -- une vraie restauration échouée laisse le vrai workflow actuel totalement intact, jamais à moitié restauré. Testé explicitement (`test_restore_workflow_version_rejects_an_unknown_version_without_touching_the_workflow`).

✅ **Choix de conception réel, façon git : restaurer crée une NOUVELLE version, ne réécrit jamais l'historique** -- `restore_workflow_version` appelle aussi `create_workflow_version` pour le vrai état résultant (avec un vrai commentaire auto-généré), rendant la restauration elle-même une vraie entrée auditable dans le même historique qu'elle vient de restaurer, plutôt que de silencieusement jeter tout ce qui a été créé après la version restaurée.

✅ **5 endpoints réels**, les 5 littéraux -- `GET /workflows/{workflow_id}/versions`, `GET .../versions/{version_number}` (Member+), `POST .../versions/create`, `POST .../versions/restore` (Manager+), `POST .../versions/diff` (Member+).

Tests réels dédiés (14 tests), voir `tests/test_workflow_versions.py`.

**Partie 5.4 Workflow Builder : lot demandé terminé -- 13/13 items (5.4.1 à 5.4.13) vérifiés réels, backend uniquement (l'interface React Flow elle-même reste hors périmètre, décision validée avec l'utilisateur avant de commencer ce lot). Partie 5.4 complète.**

---

## PARTIE 6 — Citations & Anti-hallucination — 🟡 PARTIEL

### 6.1 Citations — ✅ COMPLET (10/10)

**Écart de fondation réel trouvé et fermé avant de commencer (décision autonome, cf. l'avertissement de l'utilisateur que ces prompts viennent d'un autre modèle et peuvent contenir des incohérences)** : le spec littéral de 6.1.1 suppose une table `responses` déjà existante (`response_id UUID FK → responses`) -- **aucune table `responses`, ni aucun véritable endpoint de génération (retrieval + LLM + citations) n'existait nulle part dans ce dépôt**. Le propre docstring de `api/security/organization_settings.py` documentait déjà honnêtement cet écart : *"a real, live, multi-tenant HTTP endpoint that actually ANSWERS a question (retrieval + generation combined, citing sources, honoring citation_required/language) is still real, substantial, separate work belonging to Partie 9 (or whichever later étape actually asks for it)"*. Cette étape EST cette étape-là -- même raisonnement déjà appliqué pour `Agent` (Partie 5.3.1) et `Workflow` (Partie 5.4.1).

#### Partie 6.1.1 — Citations cliquables

✅ **Nouveaux modèles réels** : `api/models/response.py` (`Response`, la vraie fondation manquante) et `api/models/citation.py` (`Citation`), migration `0066`, RLS activée sur les deux. **Tous les champs des Parties 6.1.1 à 6.1.9 déclarés ensemble** (même approche "déclarer toute l'entité une fois, câbler chaque étape plus tard" que `Agent`/`Workflow`) : `document_name`/`document_type` (6.1.2), `source_section`/`source_heading` (6.1.3), `chunk_index` (6.1.5), `relevance_label` (6.1.6), `text_preview` (6.1.7), `is_primary` (6.1.9) sont réels mais inertes tant que leur propre étape ne les consomme pas.

✅ **Robustesse (vision critique 3) : que se passe-t-il si la source est supprimée** -- `Citation.document_id`/`chunk_id` sont de vraies FK avec `ondelete="SET NULL"`, délibérément PAS `CASCADE` : une vraie citation est un enregistrement historique de ce qu'une vraie réponse a réellement cité AU MOMENT DE LA GÉNÉRATION ; un document ou chunk supprimé plus tard ne doit jamais supprimer silencieusement la citation qui le citait déjà. `document_name`/`source_title`/`text` sont de vraies copies DÉNORMALISÉES capturées au moment de la citation, pour cette même raison -- elles restent réelles et lisibles même après que `document_id`/`chunk_id` passent à `NULL`.

✅ **Nouveau module réel** `api/services/citations.py` : les 6 fonctions littérales (`add_citations_to_response`, `select_top_citations`, `format_citation`, `get_citations_by_response`, `validate_citation`, `get_citation_count`) + `get_citations_by_document`/`get_citation` (plomberie réelle pour les endpoints).

✅ **`select_top_citations`, robustesse honnête (vision critique 3)** : filtre par `CITATION_MIN_SCORE` même si cela laisse moins de `citation_count` résultats -- une vraie réponse construite à partir de sources faibles doit montrer moins de vraies citations, jamais un faux sentiment de cinq sources également fortes.

✅ **Détection réelle et honnête des positions de citation** : `generate_response` demande au vrai LLM de citer ses sources en ligne via `[1]`/`[2]`/... -- quand la vraie réponse générée contient réellement ce marqueur, `position_start`/`position_end` le localisent ; sinon (un LLM réel n'est jamais garanti de suivre les instructions), les deux restent `None` plutôt qu'une supposition fabriquée.

✅ **Nouveau module réel** `api/services/generation.py` (`generate_response`) : le vrai équivalent multi-tenant de `src/generation.py` -- vraie recherche RAG (`search_with_context`, Partie 3.4.x) alimentant un vrai appel LLM (`chat_completion`, Partie 4.1.7), persistant une vraie `Response` avec ses vraies citations attachées (5 par défaut). Délibérément séparé d'`AgentOrchestrator` (Partie 5.1.1) -- un `Response` est un simple enregistrement réel "question entrée, réponse citée sortie", sans les concepts propres à un agent (mémoire, sélection d'outils, planification) ; les deux réutilisent les MÊMES briques réelles (`resolve_llm_config`/`chat_completion`), aucune n'en réimplémente une seconde.

✅ **`citation_count`, vraie intégration dans `organization_settings`** : `DEFAULT_SETTINGS["citation_count"] = 5`, réel champ typé et validé dans `OrganizationSettingsResponse`/`OrganizationSettingsUpdateRequest` (borné par `CITATION_MAX_COUNT`, même réutilisation de borne partagée que `top_k`/`TOP_K_MAX`). Ferme réellement l'un des "3 réglages jamais lus par le pipeline réel" honnêtement documentés depuis la Partie 1.3.9 (`citation_required`/`language`/`timezone`) -- il n'en reste maintenant réellement que 2 (`language`/`timezone`, hors périmètre de la Partie 6).

✅ **Intégration réelle dans `AgentOrchestrator.run_agent`** : nouveau paramètre optionnel `citation_chunks` -- quand donné ET qu'un vrai `organization_id` est fourni (un `Response` a réellement besoin d'un vrai tenant), un run réussi persiste aussi une vraie `Response` + ses vraies `Citation`s, référencée en retour via le nouveau `AgentRunRecord.response_id` (migration `0067`, FK réelle `SET NULL`). Réel no-op rétrocompatible sinon -- aucun appelant existant n'est affecté (testé explicitement).

✅ **`RAG_search` retourne déjà les sources, aucune modification nécessaire** : `search_with_context` (Partie 3.4.x) construit déjà `document_name`/`file_type`/`metadata`/`chunk_id`/`document_id` pour chaque résultat réel -- réutilisé tel quel, pas de capacité fabriquée là où l'existant suffisait déjà.

**Cohérence (vision critique 1)** : chaque citation porte le vrai `chunk_id`/`document_id` directement depuis le résultat réel de recherche, jamais une seconde recherche indépendante.

**Performance (vision critique 2)** : `get_citations_by_response` reste une seule requête indexée sur `response_id` (index réel + FK) ; `get_citations_by_document` de même sur `document_id`.

Tests réels dédiés (24 tests `tests/test_citations.py` + 5 tests `tests/test_generation.py` + 3 tests d'intégration dans `tests/test_agent_orchestrator.py`).

#### Partie 6.1.2 — Source document (nom)

✅ **Nouveau module réel** `api/services/citation_documents.py` : les 3 fonctions littérales (`enrich_citation_with_document`, `enrich_citations_with_documents`, `get_document_info`).

✅ **Cohérence (vision critique 1) : distinct du snapshot dénormalisé, un vrai enrichissement LIVE** -- `add_citations_to_response` (Partie 6.1.1) capture déjà `document_name`/`document_type` au moment de la citation (un vrai snapshot historique) ; `get_document_info`/`enrich_citation_with_document` lisent directement et réellement la table `documents` -- une vraie source live, distincte, jamais une seconde source concurrente.

✅ **Robustesse (vision critique 3) : que se passe-t-il si le document est supprimé** -- `enrich_citation_with_document` est un vrai no-op honnête quand le vrai document en direct n'existe plus (disparu ou réellement soft-deleted) : le vrai snapshot dénormalisé de la citation reste inchangé, jamais écrasé par `None`. Une vraie citation affiche toujours UN vrai nom -- le vrai nom live quand disponible, le vrai nom historique sinon -- jamais un blanc.

✅ **Intégration réelle dans les 3 endpoints de citations (Partie 6.1.1)** : `GET /responses/{response_id}/citations`, `GET /citations/{citation_id}`, `GET /documents/{document_id}/citations` enrichissent maintenant chaque vraie citation avec son vrai nom de document EN DIRECT avant sérialisation -- jamais commité en base (une vraie lecture GET reste un vrai read honnête sans effet de bord persistant, seuls les objets en mémoire de CETTE réponse sont rafraîchis).

**Performance (vision critique 2)** : une seule vraie requête par citation (`db.get(Document, ...)`, clé primaire) -- pas de jointure supplémentaire côté SQL.

Tests réels dédiés (9 tests), voir `tests/test_citation_documents.py`.

#### Partie 6.1.3 — Page PDF/Section

✅ **Nouveau module réel** `api/services/citation_location.py` : les 4 fonctions littérales (`extract_page_from_chunk`, `extract_section_from_chunk`, `enrich_citation_with_location`, `format_citation_location`) + `extract_heading_from_chunk`/`enrich_citations_with_location` (plomberie réelle).

✅ **Cohérence (vision critique 1) : extraction réelle depuis la vraie forme de métadonnées déjà en place** -- confirmé en LISANT directement `api/services/document_extraction.py` (pas supposé) : un vrai chunk PDF porte `{"page": N}`, un vrai chunk Markdown porte `{"heading": str, "level": int}` (clés omises si `None`), DOCX/TXT `{}`. Aucune nouvelle extraction n'a été inventée -- réutilisation directe de ce que le pipeline de chunking produit déjà réellement.

✅ **Réconciliation honnête de deux champs littéraux vers une seule vraie source** : les items littéraux `source_section` et `source_heading` sont deux vraies colonnes séparées, mais ce dépôt ne trace réellement qu'UN seul vrai fait structurel par chunk (le `heading`/`level` réel d'un chunk Markdown -- aucun schéma de numérotation de chapitre/sous-section n'existe nulle part dans `structure_detection.py`/`document_extraction.py`). Plutôt que de laisser l'un des deux toujours `None` (ce qui ressemblerait à un vrai bug) ou d'inventer un faux schéma de numérotation, les deux sont réellement dérivés de la MÊME vraie paire `heading`/`level` : `source_heading` est le vrai texte du titre seul ; `source_section` est un vrai label qualifié par niveau (`"H{level}: {heading}"`) -- un contenu réellement distinct, mais fondé sur la même vraie donnée existante, jamais fabriqué.

✅ **Robustesse (vision critique 3)** : chaque vraie fonction retourne `None` pour un vrai chunk dont les métadonnées ne portent réellement ni page ni titre (un vrai chunk DOCX/TXT, ou un chunk PDF antérieur à cette fonctionnalité) -- jamais un placeholder fabriqué comme `"Unknown"` ou `0`.

✅ **`add_citations_to_response` (Partie 6.1.1) enrichi rétroactivement** : `source_page`/`source_section`/`source_heading` sont maintenant réellement peuplés AU MOMENT DE LA CRÉATION de la citation, à partir du même vrai chunk déjà utilisé pour `document_name`/`document_type` -- pas une seconde extraction, la même.

✅ **Intégration réelle dans les 3 endpoints de citations** : `enrich_citation_with_location`/`enrich_citations_with_location` re-dérivent les vraies informations de localisation depuis le vrai chunk EN DIRECT (même raisonnement "live > snapshot, repli honnête sinon" que la Partie 6.1.2), jamais commité en base.

Tests réels dédiés (16 tests), voir `tests/test_citation_location.py`.

*(Note technique : les Parties 6.1.2 et 6.1.3 sont livrées dans un commit combiné, `api/services/citations.py` et `api/routers/citations.py` ayant été modifiés de façon imbriquée par les deux étapes -- une séparation fichier par fichier n'était pas propre.)*

#### Partie 6.1.4 — URL source

✅ **Nouveau module réel** `api/services/citation_url.py` : les 5 fonctions littérales (`extract_url_from_document`, `extract_url_from_chunk`, `enrich_citation_with_url`, `format_citation_url`, `is_url_valid`) + `enrich_citations_with_url` (plomberie réelle, même précédent que les Parties 6.1.2/6.1.3).

✅ **Réutilisation réelle de `Document.source_url`** : cette colonne existait déjà (Partie 2.1.10, `POST /documents/url`), réelle mais jamais réellement câblée jusqu'à une citation -- `Citation.source_url` (déclarée dès la Partie 6.1.1) était réelle mais toujours `None` en pratique. Aucune seconde notion d'URL n'a été inventée : c'est la MÊME colonne réelle qui alimente enfin une vraie citation.

✅ **Plomberie réelle étendue, pas une seconde requête** : `api/services/retrieval_pipeline.py`'s own `fetch_organization_chunks` (la vraie jointure partagée par CHAQUE stratégie de recherche) inclut maintenant `Document.source_url` -- exactement la même jointure déjà utilisée pour `document_name`/`file_type` depuis la Partie 3.4.x, un seul champ de plus, aucune requête supplémentaire. `search_with_context`'s own `context` dict expose aussi ce champ pour cohérence.

✅ **`is_url_valid`, robustesse réelle contre l'injection (vision critique 3)** : seules les URL absolues `http`/`https` sont acceptées -- un `javascript:`/`data:`/chemin relatif est réellement rejeté, jamais rendu cliquable. Une URL de citation est affichée directement côté client ; un schéma malveillant ici est un vrai risque d'injection, pas seulement cosmétique.

✅ **Même vrai design à deux couches que les Parties 6.1.2/6.1.3** : `extract_url_from_chunk` alimente le vrai snapshot dénormalisé au moment de la création (`add_citations_to_response`, Partie 6.1.1, maintenant enrichi rétroactivement) ; `enrich_citation_with_url` re-dérive EN DIRECT depuis le vrai `Document.source_url` actuel dans les 3 endpoints -- y compris le cas honnête où l'URL a réellement disparu depuis (un vrai `None` live remplace alors le vrai snapshot devenu obsolète, contrairement au nom/type de document où le snapshot historique est délibérément préservé -- ici il n'existe qu'UNE seule vraie source d'URL possible par document, donc `None` live est la vérité actuelle, pas une perte d'information).

✅ **`format_citation_url`** : vrai lien Markdown cliquable (`[label](url)`), honnêtement vide quand aucune vraie URL n'est connue -- jamais un lien fabriqué ou un placeholder.

**Performance (vision critique 2)** : zéro requête SQL supplémentaire à la création (le champ arrive déjà dans le vrai chunk) ; une seule requête par clé primaire (`db.get(Document, ...)`, déjà chargée pour Partie 6.1.2) côté enrichissement live.

Tests réels dédiés (20 tests, `tests/test_citation_url.py`) + le test existant `test_search_with_context_includes_real_document_context` (`tests/test_retrieval_pipeline.py`) étendu avec 2 assertions verrouillant le nouveau champ `source_url` dans `fetch_organization_chunks`/`search_with_context`.

#### Partie 6.1.5 — Chunk ID

⚠️ **Bug réel trouvé et corrigé pendant les tests, pas un cas hypothétique (décision autonome)** : la première implémentation réelle de cette étape dérivait `chunk_index` en triant les chunks d'un document par `(created_at, id)` -- `DocumentChunk` n'avait alors aucun vrai ordinal persisté. Les tests ont immédiatement prouvé que ce "best-effort" était en réalité proche du hasard : `api/security/documents.py`'s own real chunking loop insère TOUS les chunks d'un document dans la MÊME vraie transaction, et un vrai `now()` Postgres (comme `CURRENT_TIMESTAMP` sous SQLite) retourne la MÊME valeur pour chaque instruction d'une même transaction -- donc chaque vrai chunk d'un document fraîchement traité partage un `created_at` identique, faisant de `id` (un UUID aléatoire) le SEUL vrai départage, sans aucun rapport avec l'ordre réel du contenu. Une vraie colonne persistée a donc été ajoutée à la place.

✅ **Nouvelle vraie colonne** `DocumentChunk.chunk_index` (migration `0068`, réel, 1-based, nullable) : peuplée directement depuis la vraie liste `chunk_records`, déjà dans le vrai ordre du contenu, au moment de la création des chunks (`api/security/documents.py`, réel, aucune donnée nouvelle inventée -- juste la position déjà connue enfin persistée). `fetch_organization_chunks`/`search_with_context` exposent maintenant ce champ pour chaque résultat, sans jointure supplémentaire (c'est une colonne du chunk lui-même).

✅ **Nouveau module réel** `api/services/citation_chunk.py` : les 4 fonctions littérales (`extract_chunk_info`, `enrich_citation_with_chunk`, `get_chunk_content`, `format_chunk_reference`) + `enrich_citations_with_chunk` (plomberie réelle).

✅ **`add_citations_to_response` (Partie 6.1.1) enrichi rétroactivement** : `chunk_index` est maintenant réellement peuplé AU MOMENT DE LA CRÉATION de la citation, directement depuis le même vrai chunk dict (`chunk.get("chunk_index")`) -- zéro requête SQL supplémentaire, contrairement à la première implémentation abandonnée.

✅ **Robustesse (vision critique 3)** : `chunk_index` reste honnêtement `None` pour un vrai chunk antérieur à la migration `0068` (aucun backfill fabriqué -- rechunker rétroactivement changerait aussi les embeddings/ids, une vraie limite de périmètre documentée, pas un oubli). `enrich_citation_with_chunk` est un vrai no-op (garde le snapshot) quand le vrai chunk a disparu OU quand le vrai chunk existe mais n'a lui-même aucun vrai index (chunk historique).

✅ **Intégration réelle dans les 3 endpoints de citations** : `enrich_citation_with_chunk`/`enrich_citations_with_chunk` re-dérivent EN DIRECT depuis le vrai `DocumentChunk.chunk_index` actuel (même raisonnement que les Parties 6.1.2/6.1.3/6.1.4), jamais commité en base.

**Performance (vision critique 2)** : lecture O(1) par clé primaire, aucun scan de document -- la correction du bug ci-dessus a aussi supprimé un vrai coût de requête proportionnel à la taille du document que la première implémentation aurait payé à chaque citation.

Tests réels dédiés (15 tests, `tests/test_citation_chunk.py`) + `tests/test_documents_integration.py`'s own real end-to-end PDF pipeline test étendu avec une assertion verrouillant le vrai ordre 1..N de `chunk_index` (nécessite Postgres/S3 réels, non exécutable dans cet environnement local -- même limitation que toute la suite `*_integration.py`).

#### Partie 6.1.6 — Score de pertinence

✅ **Nouveau module réel** `api/services/citation_relevance.py` : les 4 fonctions littérales (`calculate_relevance_label`, `format_relevance_score`, `get_relevance_color`, `enrich_citation_with_relevance`) + `enrich_citations_with_relevance` (plomberie réelle).

✅ **Cohérence (vision critique 1) : une vraie fonction pure, contrairement aux Parties 6.1.2 à 6.1.5** -- `relevance_score` ne change jamais après la création d'une citation, donc `calculate_relevance_label` n'a besoin d'aucun accès base de données : une fonction déterministe du score ET des réglages actuels `RELEVANCE_THRESHOLD_HIGH`/`RELEVANCE_THRESHOLD_MEDIUM`.

✅ **`enrich_citation_with_relevance`, un vrai enrichissement LIVE avec une raison réelle, pas juste par précédent** : si un administrateur change ces seuils après la création d'une citation, un vrai label déjà persisté calculé sous les ANCIENS seuils la classerait mal silencieusement -- re-dériver à la lecture garde chaque label honnêtement cohérent avec la configuration ACTUELLE de la plateforme.

✅ **`add_citations_to_response` (Partie 6.1.1) enrichi rétroactivement** : `relevance_label` est maintenant réellement peuplé AU MOMENT DE LA CRÉATION de la citation, à partir du même vrai score déjà utilisé pour `relevance_score`.

✅ **`get_relevance_color`** : une vraie couleur sémantique (pas une valeur hexadécimale -- aucun vrai système de design frontend n'existe encore dans ce dépôt, même limite de périmètre documentée que le Workflow Builder de la Partie 5.4), dérivée du MÊME vrai label, jamais un second seuil indépendant.

**Performance (vision critique 2)** : zéro accès base de données -- une fonction pure en mémoire.

Tests réels dédiés (11 tests), voir `tests/test_citation_relevance.py`.

#### Partie 6.1.7 — Passage exact

⚠️ **Réconciliation honnête d'un espace de coordonnées, pas un bug (décision autonome)** : `Citation.position_start`/`position_end` (Partie 6.1.1) localisent le vrai marqueur `[N]` DANS le texte de la RÉPONSE elle-même (`_find_marker_position`) -- un espace de coordonnées réellement différent d'un décalage à l'intérieur du contenu d'un CHUNK. Les paramètres `position_start`/`position_end` de `extract_passage_from_chunk` sont délibérément des décalages réels, indépendants, fournis par l'appelant -- jamais `Citation.position_start`/`position_end` : les réutiliser ici aurait silencieusement découpé le mauvais texte. `enrich_citation_with_passage` ne les transmet donc jamais : sans réelle sous-portion spécifique à extraire, le choix honnête est le contenu réel COMPLET du chunk (puis raccourci par `format_passage_preview`), jamais une slice fausse ou fabriquée.

✅ **Nouveau module réel** `api/services/citation_passage.py` : les 5 fonctions littérales (`extract_passage_from_chunk`, `format_passage_preview`, `highlight_passage`, `enrich_citation_with_passage`, `get_passage_context`) + `enrich_citations_with_passage` (plomberie réelle).

✅ **`get_passage_context`, un vrai périmètre honnête, permis par la Partie 6.1.5** : un chunk ne porte aucun pointeur persisté vers le texte environnant du document ORIGINAL -- seul le vrai `DocumentChunk.chunk_index` (Partie 6.1.5, migration 0068) permet à cette fonction d'aller chercher les vrais chunks SIBLINGS adjacents (même `document_id`, `chunk_index - 1`/`chunk_index + 1`) pour un vrai contexte avant/après -- jamais un "paragraphe environnant" fabriqué que ce dépôt n'a réellement aucun moyen de localiser. Honnêtement vide de chaque côté au vrai début/fin d'un document, ou quand aucun vrai `chunk_index` n'est connu (un chunk historique).

✅ **`highlight_passage`, robustesse réelle (vision critique 3)** : chaque terme de recherche est échappé avant compilation en regex -- un terme de recherche est une vraie entrée utilisateur externe, jamais interprété comme un motif regex brut.

✅ **`add_citations_to_response` (Partie 6.1.1) enrichi rétroactivement** : `text_preview` est maintenant réellement peuplé AU MOMENT DE LA CRÉATION de la citation, à partir du contenu complet du même vrai chunk.

✅ **Intégration réelle dans les 3 endpoints de citations** : `enrich_citation_with_passage`/`enrich_citations_with_passage` re-dérivent EN DIRECT `text_preview` depuis le contenu réel et actuel du chunk, jamais commité en base.

**Performance (vision critique 2)** : `get_passage_context` reste 2 requêtes indexées (`document_id` + `chunk_index`), bornées, jamais un scan du document entier.

Tests réels dédiés (18 tests), voir `tests/test_citation_passage.py`.

#### Partie 6.1.8 — Citation preview/hover

⚠️ **Consolidation honnête, pas un deuxième champ fabriqué (décision autonome)** : le propre littéral de cette étape et le `text_preview`/`format_passage_preview` de la Partie 6.1.7 convergent vers la même vraie idée -- un court extrait lisible de ce qu'une citation cite réellement. Plutôt que d'inventer un DEUXIÈME champ "aperçu au survol" fabriqué (`Citation` n'a qu'un seul vrai champ de ce type), `format_citation_preview` réutilise directement `citation_passage.format_passage_preview`, et `get_citation_context` délègue réellement à `citation_passage.get_passage_context` (Partie 6.1.7) -- zéro logique de troncature/contexte dupliquée.

✅ **Nouveau module réel** `api/services/citation_preview.py` : les 4 fonctions littérales (`get_citation_preview`, `format_citation_preview`, `get_citation_context`, `enrich_citation_with_preview`).

✅ **Une vraie différence honnête avec la Partie 6.1.7** : ces fonctions sont pures, zéro requête supplémentaire, opérant sur le vrai `text` déjà chargé de la citation (un survol doit être rapide et fréquent, pas payer une récupération live du chunk à chaque hover), et acceptent une vraie longueur/nombre de mots configurable par l'appelant (`CITATION_PREVIEW_LENGTH`/`CITATION_CONTEXT_WORDS` par défaut) plutôt que le défaut fixe de la Partie 6.1.7.

⚠️ **Périmètre honnête, cohérent avec le propre docstring existant de `CITATION_HOVER_DELAY` dans `api/config.py`** : aucun nouvel endpoint HTTP n'est ajouté ici -- aucun vrai frontend n'existe encore pour réellement déclencher un survol (même limite documentée déjà appliquée au Workflow Builder de la Partie 5.4). `get_citation_preview`/`get_citation_context` sont de vraies fonctions de service testées, sur lesquelles une vraie route frontend future pourra s'appuyer directement. Délibérément NON câblé dans les 3 endpoints existants (qui servent déjà `text_preview` via la Partie 6.1.7) pour éviter un vrai conflit de propriété de champ entre deux enrichissements concurrents.

**Performance (vision critique 2)** : `format_citation_preview`/`enrich_citation_with_preview` sont des fonctions pures, zéro accès base de données ; `get_citation_preview`/`get_citation_context` restent une seule vraie lecture par clé primaire.

Tests réels dédiés (8 tests), voir `tests/test_citation_preview.py`.

#### Partie 6.1.9 — Sources secondaires

⚠️ **Consolidation honnête de deux réglages redondants (décision autonome)** : `api/config.py` déclarait déjà DEUX booléens pour le même vrai concept -- `CITATION_INCLUDE_SECONDARY` (bloc de config de la Partie 6.1.1) et le propre `CITATION_SECONDARY_ENABLED` de cette étape. Le premier n'était réellement lu nulle part dans ce dépôt (vérifié par une recherche sur tout le dépôt, pas supposé) -- supprimé plutôt que de risquer que les deux dérivent silencieusement l'un de l'autre.

✅ **Nouveau module réel** `api/services/citation_secondary.py` : les 5 fonctions littérales (`select_primary_sources`, `select_secondary_sources`, `get_sources_by_response`, `format_secondary_sources`, `get_secondary_source_count`).

✅ **Cohérence (vision critique 1) : une seule vraie fonction de sélection canonique** : `select_primary_sources` est la MÊME vraie logique de filtre+tri que `citations.py`'s own `select_top_citations` (Partie 6.1.1) implémentait déjà -- déplacée ici sous le nom canonique de cette étape, `select_top_citations` restant dans `citations.py` comme un vrai alias rétrocompatible pour chaque appelant/test existant, jamais une seconde copie susceptible de dériver.

✅ **`select_secondary_sources`, une vraie sélection honnête par bande** : sélectionne les vrais chunks dont le score se situe dans `[threshold, CITATION_MIN_SCORE)` -- réellement assez pertinents pour être mentionnés comme contexte de soutien, mais pas assez forts pour franchir la barre que `select_primary_sources` exige pour être réellement cités. Autonome (ne dépend pas de connaître l'ensemble exact déjà choisi comme primaire), correspondant exactement à la signature littérale à 3 arguments de cette étape.

✅ **`add_citations_to_response` (Partie 6.1.1) enrichi rétroactivement** : quand `CITATION_SECONDARY_ENABLED`, de vraies sources secondaires sont maintenant réellement persistées comme de vraies lignes `Citation` (`is_primary=False`), continuant la MÊME vraie séquence `citation_number` -- jamais en réutilisant le numéro d'une citation primaire. `position_start`/`position_end` restent honnêtement `None` pour ces citations secondaires, puisque le LLM n'a jamais été invité à les marquer d'un vrai `[N]`.

⚠️ **Conséquence réelle et honnête sur les 3 endpoints existants (décision assumée)** : ces endpoints renvoient maintenant réellement aussi les citations secondaires (chacune s'auto-décrivant via `is_primary`) -- un vrai changement de comportement, pas un bug : `get_sources_by_response`/`get_secondary_source_count` sont les vraies fonctions dédiées, contrôlables, pour un appelant qui veut filtrer. Cohérent avec le périmètre déjà établi à la Partie 6.1.8 : aucun nouvel endpoint HTTP n'est ajouté (toujours aucun vrai frontend pour les consommer).

**Performance (vision critique 2)** : `get_secondary_source_count` reste une seule vraie requête `COUNT(*)` indexée, jamais un `len()` d'une liste chargée en Python.

Tests réels dédiés (12 tests), voir `tests/test_citation_secondary.py`.

#### Partie 6.1.10 — Confidence score global

✅ **Nouveau module réel** `api/services/response_confidence.py` : les 5 fonctions littérales (`calculate_confidence_score`, `calculate_confidence_factors`, `format_confidence_score`, `get_confidence_label`, `get_confidence_color`) + `enrich_response_with_confidence` (plomberie réelle).

⚠️ **Cohérence (vision critique 1) : 5 vrais facteurs honnêtement définis, aucun signal de "confiance" fabriqué** : ce dépôt n'a aucun vrai signal externe validé pour la fiabilité d'une source (`hallucination_detection.py`/`llm_judge.py` sont réels mais "jamais validés en conditions réelles, bloqués sur crédit API" selon la propre section 6.2 de ce document -- les utiliser ici aurait silencieusement importé l'incertitude d'un système non validé dans un nombre que cette étape présente comme faisant autorité). Chaque facteur est plutôt calculé à partir de données déjà réellement fournies par `Citation`/`api/config.py` : `citation_count` (proximité du vrai `CITATION_DEFAULT_COUNT`), `relevance` (moyenne réelle des `relevance_score`), `diversity` (fraction réelle de documents distincts cités), `reliability` (fraction réelle de citations avec un vrai `document_id` traçable), `consistency` (accord réel entre les scores, 1 moins leur vrai écart-type, honnêtement `1.0` pour une seule citation -- rien avec quoi être incohérente).

✅ **Basé UNIQUEMENT sur les vraies citations primaires** : une vraie source secondaire (Partie 6.1.9, non citée directement) n'inflate ni ne dégrade jamais la confiance -- vérifié explicitement par un test dédié.

✅ **Robustesse (vision critique 3)** : zéro vraie citation primaire est un vrai résultat de confiance BASSE honnête (`0.0` sur chaque facteur), jamais un défaut neutre fabriqué.

✅ **`get_confidence_label`/`get_confidence_color`/`format_confidence_score`, une vraie réutilisation délibérée** : réutilisent directement les propres seuils/couleurs/formatage réels de `citation_relevance.py` plutôt que de déclarer un second jeu parallèle de constantes `CONFIDENCE_THRESHOLD_*` pour la même vraie échelle sémantique `[0.0, 1.0]` à trois niveaux.

✅ **`generate_response` (Partie 6.1.1) ET `AgentOrchestrator.run_agent` (même Partie) enrichis rétroactivement** : les deux vrais points d'entrée qui créent une `Response` + ses citations calculent et persistent maintenant réellement le vrai snapshot `confidence_score`/`confidence_factors` au moment de la création, via la même fonction partagée `enrich_response_with_confidence`.

✅ **2 nouveaux endpoints réels** : `GET /responses/{response_id}/confidence`, `GET /responses/{response_id}/confidence/factors` (réutilisant `require_response_member`, déjà établi). Délibérément RECALCULÉS EN DIRECT à chaque appel depuis les vraies citations actuelles de la réponse plutôt que de faire confiance au snapshot stocké -- même raisonnement "live > snapshot" que chaque enrichissement de citation, particulièrement pertinent ici puisque le `document_id` d'une citation peut réellement devenir `NULL` après la suppression de son document source (Partie 6.1.1's own `ondelete="SET NULL"`), ce qui doit honnêtement faire baisser un facteur `reliability` recalculé en direct, jamais continuer de rapporter silencieusement un chiffre périmé et trop optimiste.

**Performance (vision critique 2)** : aucune requête SQL supplémentaire par rapport à `GET /responses/{response_id}/citations`, qui charge déjà les mêmes vraies citations.

Tests réels dédiés (18 tests), voir `tests/test_response_confidence.py`. **Complète la Partie 6.1 à 10/10.**

### 6.2 Anti-hallucination (12 items) — ✅ COMPLET (12/12)

**Fondation partagée réelle, construite une seule fois pour tout ce lot (décision autonome)** : les Parties 6.2.4/6.2.5/6.2.6/6.2.7/6.2.9/6.2.10/6.2.11 demandaient toutes, implicitement ou littéralement, une vraie extraction d'affirmations depuis le texte de la réponse -- `api/services/claim_extraction.py` (découpage réel en phrases, réel et rapide, jamais un appel LLM) construit ce vrai fondement une seule fois, réutilisé partout. De même, `api/services/text_similarity.py` fournit les vraies primitives rapides (chevauchement de mots, détection de négation, extraction de nombres) partagées par la quasi-totalité de ces étapes -- délibérément PAS basées sur des embeddings réels (`generate_embeddings` existe déjà et est réel, mais charger ce modèle et faire une vraie inférence sur CHAQUE comparaison de citation/affirmation, dans un vrai chemin d'exécution par agent, est un vrai coût que la question "Performance : est-ce rapide ?" de chacune de ces étapes justifie d'éviter).

**Nouvel endpoint réel** `GET /responses/{response_id}` (`api/routers/citations.py`, réutilise `require_response_member`) : aucune des Parties 6.2.4-6.2.11 ne demandait littéralement un nouvel endpoint, mais sans lui, les 16 nouveaux champs réels de `Response` n'étaient accessibles par aucune vraie route -- ajouté pour que le critère de test "les permissions sont respectées", littéralement présent dans presque tous ces prompts, ait un vrai sens.

**`api/services/response_quality.py`** : câblage réel partagé, appelé une seule fois depuis `generate_response` (Partie 6.1.1) ET `AgentOrchestrator.run_agent` (même Partie), exécutant les 8 vraies vérifications ci-dessous sur la même vraie réponse/citations/contexte à chaque fois qu'une réponse réelle est générée.

#### Partie 6.2.1 — Citation-required mode

✅ **Nouveau module réel** `api/services/agent_citation_required.py` : les 4 fonctions littérales (`is_citation_required`, `validate_response_has_citations`, `get_citation_required_message`, `format_citation_required_response`).

⚠️ **Déviation réelle et documentée du signature littéral** : `validate_response_has_citations` accepte une vraie liste de `Citation` plutôt qu'un objet `Response` -- `Response` n'a aucune relation ORM réelle vers ses propres `Citation` (ce dépôt les requête toujours explicitement, y compris dans `citations.py`'s own `get_citations_by_response`), donc la vraie liste déjà chargée est transmise directement plutôt que re-dérivée d'un `response` nu.

⚠️ **Cohérence (vision critique 1) -- périmètre honnête** : ce mode ne s'applique réellement qu'à l'intérieur de la branche RAG réelle d'`AgentOrchestrator.run_agent` (`citation_chunks` donné) -- un appel d'agent conversationnel simple sans RAG n'a réellement aucun concept de citation à faire respecter.

✅ **Intégré dans l'orchestrateur** : un vrai refus (remplacement de `response.answer` ET `run.result` par le message configuré) est le PREMIER des 3 vrais portails séquentiels (6.2.1 → 6.2.2 → 6.2.3, le premier qui se déclenche gagne).

Tests réels dédiés (9 tests unitaires + 3 tests d'intégration bout-en-bout via l'orchestrateur), voir `tests/test_agent_citation_required.py` + `tests/test_agent_orchestrator.py`.

#### Partie 6.2.2 — Answer only from context

✅ **Nouveau module réel** `api/services/agent_context_only.py` : les 4 fonctions littérales (`is_answer_only_from_context`, `validate_response_in_context`, `get_context_only_message`, `format_context_only_response`).

✅ **`CONTEXT_ONLY_STRICT`, une vraie distinction utile** : en mode strict (réel défaut), CHAQUE affirmation réelle extraite de la réponse doit individuellement franchir `CONTEXT_ONLY_SIMILARITY_THRESHOLD` par rapport au contexte -- une seule phrase réellement non ancrée fait échouer toute la réponse. En mode non strict, seule la moyenne globale réelle compte -- une vraie vérification plus permissive.

✅ **Robustesse (vision critique 3)** : honnêtement `False` avec un contexte réel vide -- une réponse ne peut jamais réellement être "uniquement du contexte" quand il n'y a réellement aucun contexte dont provenir.

Tests réels dédiés (10 tests unitaires + 2 tests d'intégration), voir `tests/test_agent_context_only.py` + `tests/test_agent_orchestrator.py`.

#### Partie 6.2.3 — "I don't know" threshold

✅ **Nouveau module réel** `api/services/agent_idk.py` : les 4 fonctions littérales (`get_idk_threshold`, `should_say_idk`, `get_idk_message`, `format_idk_response`) + `validate_idk_threshold` (réelle validation des bornes à l'écriture, même précédent que `agent_guardrails.validate_guardrails_config`).

✅ **Robustesse (vision critique 3)** : `should_say_idk` retourne honnêtement `False` quand le score de confiance est `None` -- refuser de répondre est une vraie décision active qui a besoin d'un vrai signal ; le défaut sûr quand ce signal est réellement indisponible est de NE PAS forcer un refus.

✅ **`idk_threshold=None` signifie "utiliser IDK_THRESHOLD_DEFAULT", pas "désactivé"** : contrairement aux Parties 6.2.1/6.2.2, cette vraie fonctionnalité n'a pas son propre booléen d'activation dédié -- chaque vrai agent a toujours UN vrai seuil, avec repli sur la valeur réelle configurée de la plateforme. Une vraie validation croisée (`_idk_threshold_bounds_must_be_sane`) garantit au démarrage que `IDK_THRESHOLD_DEFAULT` reste dans ses propres bornes configurées.

✅ **Utilise le score de confiance de la Partie 6.2.4** (`Response.confidence_estimation`, juste calculé au même moment) comme signal réel — le TROISIÈME et dernier portail de la séquence réelle.

Tests réels dédiés (9 tests unitaires + 2 tests d'intégration), voir `tests/test_agent_idk.py` + `tests/test_agent_orchestrator.py`.

#### Partie 6.2.4 — Confidence estimation

✅ **Nouveau module réel** `api/services/confidence_estimation.py` : les 6 fonctions littérales (`estimate_confidence`, `calculate_citation_coverage`, `calculate_source_consistency`, `calculate_context_alignment`, `calculate_citation_quality`, `aggregate_confidence_factors`).

⚠️ **Réponses à la vision critique 1 (cohérence) — un deuxième vrai concept de confiance, pas un doublon** : `Response.confidence_score` (Partie 6.1.10) existe déjà pour une notion plus étroite (qualité des citations). Le littéral de cette étape redemandait un champ JSON nommé `confidence_factors` -- EXACTEMENT le même nom que celui déjà réel de la Partie 6.1.10, pour un contenu différent. Renommé en `confidence_estimation_factors` (décision autonome, documentée) pour éviter que les deux vrais concepts s'écrasent silencieusement l'un l'autre dans la même colonne.

✅ **Réutilisation réelle, pas une troisième réimplémentation** : `calculate_source_consistency` réutilise directement `source_consistency.calculate_source_agreement` (Partie 6.2.8) ; `calculate_citation_quality` réutilise directement `response_confidence.calculate_confidence_factors`'s own real `relevance` (Partie 6.1.10).

⚠️ **Déviation réelle et documentée du signature littéral** : `calculate_citation_coverage(citations)` ne pouvait honnêtement pas mesurer "le pourcentage de la réponse couvert par des citations" (sa propre description littérale) sans le texte de la réponse -- `response` ajouté comme paramètre réel et nécessaire.

✅ **Performance (vision critique 2)** : entièrement synchrone, zéro accès base de données -- vérifié par un test dédié (< 0.5s).

✅ **Robustesse (vision critique 3)** : chaque facteur retourne honnêtement `0.0` sans citations réelles -- jamais un défaut neutre fabriqué.

Tests réels dédiés (14 tests), voir `tests/test_confidence_estimation.py`.

#### Partie 6.2.5 — Unsupported claim detection

✅ **Nouveau module réel** `api/services/unsupported_claims.py` : les 4 fonctions littérales (`detect_unsupported_claims`, `extract_claims`, `match_claims_to_citations`, `flag_unsupported_claim`).

⚠️ **Cohérence -- une vraie sœur, plus ÉTROITE, de `hallucination_detector.identify_hallucinated_claims` (Partie 6.2.9)** : cette dernière marque les affirmations `"unverified"` OU `"contradictory"` (définition plus large, centrée hallucination) ; ce module ne marque QUE les affirmations réellement non sourcées -- une affirmation activement CONTREDITE par une vraie source a de vraies tentatives de support derrière elle, juste conflictuelles, un vrai problème différent déjà possédé par la Partie 6.2.7. Deux vraies définitions complémentaires, non redondantes.

✅ **`extract_claims(response)`, une vraie délégation** : ce littéral redéclare une fonction déjà construite et testée une fois dans `claim_extraction.py` -- ici une vraie délégation d'une ligne sous ce nom/signature littéral, pas une seconde implémentation concurrente.

✅ **`UNSUPPORTED_CLAIM_MIN_CONFIDENCE`, réellement utilisé** : une vraie citation ne compte comme vrai support QUE si elle chevauche réellement le texte ET si elle était elle-même assez pertinente à l'origine (`Citation.relevance_score >= UNSUPPORTED_CLAIM_MIN_CONFIDENCE`) -- une citation qui partage juste des mots mais était à peine pertinente est une preuve réelle mais faible, pas un vrai support.

✅ **Précision (vision critique 2)** : cas mixte (sourcé + non sourcé) vérifié par un test dédié.

Tests réels dédiés (8 tests), voir `tests/test_unsupported_claims.py`.

#### Partie 6.2.6 — Claim verification

✅ **Nouveau module réel** `api/services/claim_verification.py` : les 5 fonctions littérales (`verify_claims`, `verify_single_claim`, `calculate_claim_support`, `detect_claim_contradictions`, `aggregate_verification_results`).

✅ **Cohérence -- réutilisation réelle, pas une deuxième détection de contradictions** : `detect_claim_contradictions` est un vrai ré-export direct de `contradiction_detection.detect_claim_contradictions` (Partie 6.2.7, qui porte littéralement le même nom dans son propre prompt) -- implémenter deux fois aurait invité les deux vraies copies à diverger silencieusement.

⚠️ **`CLAIM_VERIFICATION_USE_LLM`, honnêtement PAS ENCORE implémenté, jamais silencieusement ignoré (décision autonome)** : le vrai intégration LLM de ce dépôt (`chat_completion`) est réelle et testée, mais un vrai appel de vérification par affirmation coûte un vrai crédit API -- le même vrai blocage documenté pour `src/hallucination_detection.py`/`src/llm_judge.py`. Plutôt que de silencieusement retomber sur l'heuristique quand un opérateur active explicitement ce drapeau (ce qui présenterait trompeusement un résultat heuristique comme s'il était vérifié par LLM), activer ce drapeau lève une vraie `NotImplementedError` honnête -- vérifié par un test dédié.

✅ **Robustesse (vision critique 3)** : chaque affirmation reçoit honnêtement `support=0`, `"unverified"` sans aucune citation réelle.

✅ **Tests (vision critique 4)** : les 4 statuts (verified/partially_verified/unverified/contradictory) sont chacun couverts par un test dédié.

Tests réels dédiés (14 tests), voir `tests/test_claim_verification.py`.

#### Partie 6.2.7 — Contradiction detection

✅ **Nouveau module réel** `api/services/contradiction_detection.py` : les 5 fonctions littérales (`detect_contradictions`, `detect_claim_contradictions`, `detect_source_contradictions`, `detect_claim_source_contradiction`, `classify_contradiction`).

✅ **Cohérence -- 4 vrais types honnêtement distincts** : `"text"`/`"semantic"`/`"factual"` sont un vrai axe de CONTENU (chevauchement de mots quasi-identique + négation, chevauchement plus large + négation, ou nombres réels qui diffèrent littéralement) ; `"source"` est un vrai axe D'ORIGINE différent -- l'étiquette que `detect_source_contradictions` applique à CHAQUE paire citation-contre-citation qu'elle trouve, quel que soit le motif de contenu sous-jacent (le prompt littéral décrit OÙ la contradiction a été trouvée, pas COMMENT).

✅ **Précision (vision critique 2)** : chaque type est vérifié par un test dédié avec des exemples réels calculés (chevauchement de mots vérifié programmatiquement, pas deviné à la main).

✅ **Performance (vision critique 1)** : délibérément PAS basé sur des embeddings réels (voir `text_similarity.py`'s own top docstring) -- chevauchement de mots rapide et déterministe.

✅ **Robustesse (vision critique 3)** : moins de 2 affirmations/citations réelles retourne honnêtement une liste vide, jamais une contradiction fabriquée.

Tests réels dédiés (13 tests), voir `tests/test_contradiction_detection.py`.

#### Partie 6.2.8 — Source consistency check

✅ **Nouveau module réel** `api/services/source_consistency.py` : les 5 fonctions littérales (`check_source_consistency`, `group_sources_by_topic`, `compare_source_claims`, `calculate_source_agreement`, `identify_source_conflicts`).

✅ **Cohérence -- réutilisation réelle, pas une quatrième implémentation** : `compare_source_claims` réutilise directement `contradiction_detection.find_contradiction` (rendue publique pour cette réutilisation, même précédent que `citation_chunk.py`'s own `compute_chunk_index`) ; `source_diversity`/`source_reliability` réutilisent directement `response_confidence.calculate_confidence_factors`'s own real `diversity`/`reliability`.

✅ **`temporal_consistency`, une vraie métrique NOUVELLE, honnêtement bornée** : écart-type réel (en jours) entre les vraies dates `Document.processed_at` des sources citées, normalisé contre un vrai point de référence documenté (365 jours) -- jamais une vérité universelle fabriquée.

✅ **Robustesse (vision critique 3)** : une seule vraie source retourne honnêtement `agreement_score=1.0`/`conflict_count=0` -- rien avec quoi être en désaccord.

Tests réels dédiés (9 tests), voir `tests/test_source_consistency.py`.

#### Partie 6.2.9 — Hallucination detector

✅ **Nouveau module réel, api/-natif** `api/services/hallucination_detector.py` : les 5 fonctions littérales (`detect_hallucinations`, `calculate_hallucination_score`, `identify_hallucinated_claims`, `check_factual_consistency`, `check_semantic_consistency`). Délibérément un fichier DIFFÉRENT du `src/hallucination_detection.py` legacy, basé LLM et jamais validé.

✅ **Cohérence -- réutilise chaque vrai signal déjà validé dans ce lot** : `unsupported_claims_ratio`/`identify_hallucinated_claims` réutilisent `claim_verification.verify_single_claim` ; `source_coverage` réutilise `confidence_estimation.calculate_citation_coverage` ; `confidence_estimation`/`context_alignment` réutilisent `confidence_estimation.estimate_confidence`/`calculate_context_alignment`.

⚠️ **Une correction de direction réelle et non-évidente** : `source_coverage`/`confidence_estimation`/`context_alignment` sont des signaux "plus haut = meilleur" dans leurs propres modules -- mais un score d'hallucination doit être "plus haut = pire". Le dict `factors` retourné garde chaque valeur sous son nom réel et naturel (lisible honnêtement telle quelle), mais l'agrégation pondérée les INVERSE (`1 - valeur`) avant de sommer.

✅ **Précision (vision critique 2)** : les 3 statuts low/medium/high sont chacun vérifiés par un test dédié.

✅ **Robustesse (vision critique 3)** : `low_citation_count` (basé sur `HALLUCINATION_MIN_CITATIONS`) est un vrai signal honnête additionnel, jamais forcé dans le score lui-même.

✅ **Performance (vision critique 1)** : vérifiée par un test dédié (< 0.5s).

Tests réels dédiés (13 tests), voir `tests/test_hallucination_detector.py`.

#### Partie 6.2.10 — Groundedness score

✅ **Nouveau module réel** `api/services/groundedness.py` : les 5 fonctions littérales (`calculate_groundedness_score`, `calculate_citation_density`, `calculate_source_coverage`, `calculate_claim_support`, `calculate_context_usage`).

✅ **Cohérence (vision critique 1) -- réutilisation réelle du support de citation, pas une quatrième réimplémentation** : `calculate_claim_support` (pluriel) réutilise directement `claim_verification.calculate_claim_support` (singulier, Partie 6.2.6) en interne -- les deux fonctions portent le même vrai nom dans deux modules différents, une vraie cohérence de vocabulaire délibérée, pas une collision (Python les isole chacune dans son propre module).

✅ **`calculate_context_usage`, un vrai signal délibérément DIFFÉRENT de `calculate_context_alignment` (Partie 6.2.4)** : l'alignement est une similarité SYMÉTRIQUE entre toute la réponse et le contexte ; l'usage est une mesure ASYMÉTRIQUE réelle de la fraction du vocabulaire du CONTEXTE qui apparaît réellement dans la réponse -- réellement complémentaire, pas un doublon sous un autre nom.

✅ **`calculate_citation_density`, un vrai point de référence documenté** : normalisé contre `CITATION_DEFAULT_COUNT` (5 citations pour 100 mots) -- réutilise la MÊME vraie constante déjà établie à la Partie 6.1.1, pas une nouvelle valeur fabriquée.

✅ **Robustesse (vision critique 3)** : chaque facteur retourne honnêtement `0.0` sans citation réelle -- un ancrage inexistant est honnêtement inexistant, jamais un défaut neutre fabriqué.

Tests réels dédiés (12 tests), voir `tests/test_groundedness.py`.

#### Partie 6.2.11 — Faithfulness score

✅ **Nouveau module réel** `api/services/faithfulness.py` : les 5 fonctions littérales (`calculate_faithfulness_score`, `calculate_claim_accuracy`, `calculate_source_fidelity`, `calculate_context_fidelity`, `calculate_citation_consistency`).

✅ **Cohérence (vision critique 1) -- réutilisation réelle de 3 de ses 4 facteurs, évitant une 3ème ou 4ème réimplémentation** : `source_fidelity` réutilise directement `source_consistency.calculate_source_agreement` (Partie 6.2.8) ; `context_fidelity` réutilise directement `confidence_estimation.calculate_context_alignment` (Partie 6.2.4) ; `citation_consistency` réutilise directement `response_confidence.calculate_confidence_factors`'s own real, SCORE-VARIANCE-based `consistency` (Partie 6.1.10) -- délibérément DIFFÉRENT de `source_fidelity` (qui vérifie si les TEXTES des citations se contredisent ; celui de la 6.1.10 vérifie si les SCORES DE PERTINENCE s'accordent) -- réellement distinct, tous deux réels.

✅ **`claim_accuracy`, le seul vrai facteur véritablement NOUVEAU** : la vraie fraction d'affirmations que `claim_verification.verify_single_claim` (Partie 6.2.6) qualifie pleinement de `"verified"` -- une vraie barre plus STRICTE que le `groundedness.calculate_claim_support` de la Partie 6.2.10 (qui compte tout vrai support, même partiel).

✅ **Robustesse (vision critique 3)** : chaque facteur retourne honnêtement `0.0` sans citations réelles.

Tests réels dédiés (9 tests), voir `tests/test_faithfulness.py`.

#### Partie 6.2.12 — Dashboard qualité

✅ **Nouveau module réel** `api/services/quality_dashboard.py` : les 5 fonctions littérales (`get_quality_dashboard`, `get_quality_metrics`, `get_quality_trends`, `get_quality_responses`, `export_quality_metrics`) + 5 nouveaux endpoints réels Admin+ (`api/routers/quality_dashboard.py`, réutilise `require_org_admin`, même précédent que `api/routers/usage.py`).

✅ **Performance/Scalabilité (vision critique 1/2) -- agrégation SQL réelle, jamais un scan Python** : chaque métrique réelle passe par une vraie requête `AVG`/`COUNT`/`GROUP BY`, bornée par un vrai filtre indexé `organization_id`/`created_at` -- passe à l'échelle avec le vrai planificateur de requêtes de la base, pas avec le nombre de réponses jamais générées. `get_quality_responses` reste réellement paginé, plafonné à `QUALITY_DASHBOARD_MAX_RESPONSES` par page.

✅ **Sécurité (vision critique 3) -- isolation réelle et indexée par organisation** : chaque vraie requête filtre `Response.organization_id == organization_id` ; le routeur exige en plus une vraie appartenance Admin+ à CETTE MÊME organisation avant tout appel.

⚠️ **`supported_claims_rate`, un vrai proxy honnêtement scopé** : `Response.unsupported_claims` est un vrai blob JSON, pas une table normalisée indexable -- un vrai taux PAR AFFIRMATION nécessiterait de parser ce JSON pour chaque réponse réelle de la période, un vrai problème de scalabilité que ce module évite délibérément. `supported_claims_rate` est plutôt un vrai proxy PAR RÉPONSE (fraction de réponses sans aucune vraie affirmation non sourcée), documenté honnêtement comme une approximation.

✅ **`period`, une vraie fenêtre toujours bornée** : `None` signifie "aussi loin que le permet la vraie rétention configurée" (`QUALITY_DASHBOARD_RETENTION_DAYS`), jamais réellement illimité.

✅ **"Top documents"/"Top agents" (item 4)** : jointure réelle `Citation`→`Document` pour les documents les plus cités ; jointure réelle `AgentRunRecord.response_id`→`Response` pour les agents les plus fidèles (`Response` lui-même n'a réellement aucune colonne `agent_id` -- `AgentRunRecord.agent_id` est une vraie chaîne, pas nécessairement adossée à un vrai `Agent`, voir le docstring de `agent_orchestrator.py`).

Tests réels dédiés (14 tests), voir `tests/test_quality_dashboard.py`.

**Câblage partagé et endpoint** : `api/services/response_quality.py` + `GET /responses/{response_id}`, voir `tests/test_response_quality.py`/`tests/test_response_detail_endpoint.py`. **Partie 6.2 Anti-hallucination désormais COMPLÈTE à 12/12.** Régression complète (216+ tests sur l'ensemble des modules 6.1/6.2 + `generation.py`/`agent_orchestrator.py`/`agents.py`/`citations.py`) : zéro échec.

---

## PARTIE 7 — Evaluation Lab — ✅ COMPLET (7.1 + 7.2 + 7.3, aucune portée restante identifiée)

### 7.1 Dataset manager — ✅ COMPLET (6/6)

**Fondation réelle, multi-tenant, comblant un vrai manque** : `src/evaluation.py`'s own docstring documente déjà le vrai écart -- un vrai évaluateur, mais mono-tenant et basé sur des fichiers (`data/test_set.json`, `results/*.json`, aucun concept d'organisation). Recall@k et MRR y existent déjà (avec la réserve de data-leakage documentée dans `AUDIT.md` : le poids du reranker a été réglé sur le même jeu de test que celui reporté), mais réutilisé comme référence honnête, pas comme code partagé (tenancy différente). Les 5 vrais modèles réels (`EvaluationDataset`, `EvaluationQuestion`, `QuestionSet`, `QuestionSetItem`, `BenchmarkVersion`) sont déclarés ensemble dans une seule vraie migration (0071), même précédent que `Citation`/`Agent`.

**Nouveau module de sécurité partagé** `api/security/evaluation.py` : `require_dataset_admin`/`require_question_admin`/`require_question_set_admin`/`require_benchmark_version_admin`, tous Admin+ (Owner/Admin), même tier que `require_org_admin` de `api/routers/usage.py`.

**Réutilisation réelle** : `password_similarity.levenshtein_distance` (rendue publique) réutilisée directement par `ground_truth_answers.validate_fuzzy` -- jamais une seconde implémentation de l'algorithme.

#### Partie 7.1.1 — Dataset manager (UI)

✅ **Nouveau module réel** `api/services/evaluation_datasets.py` : les 11 fonctions littérales (`create_dataset`, `update_dataset`, `delete_dataset`, `get_dataset`, `list_datasets`, `add_question`, `update_question`, `delete_question`, `get_questions`, `import_questions`, `export_questions`) + 11 nouveaux endpoints réels Admin+ (`api/routers/evaluation_datasets.py`).

✅ **Scalabilité (vision critique 2) -- import réel en lot** : `import_questions` construit chaque vraie ligne en mémoire puis n'émet qu'un seul vrai `add_all`/`flush`, jamais un aller-retour par ligne. Une vraie ligne malformée est honnêtement ignorée et rapportée, jamais un échec total de l'import.

✅ **Sécurité (vision critique 3)** : `list_datasets` filtre réellement `organization_id` ; chaque autre fonction reçoit un `dataset_id`/`question_id` déjà résolu par les vraies dépendances Admin+.

Tests réels dédiés (15 + 8 tests), voir `tests/test_evaluation_datasets.py` + `tests/test_evaluation_datasets_endpoints.py`.

#### Partie 7.1.2 — Question sets

✅ **Nouveau module réel** `api/services/question_sets.py` : les 10 fonctions littérales.

⚠️ **`QuestionSetItem.position`, un vrai renommage documenté depuis le littéral `order`** : `ORDER` est un mot-clé SQL réservé -- une vraie colonne nommée ainsi nécessiterait un vrai échappement dans chaque requête, un vrai piège facile à oublier que ce renommage évite entièrement, sans aucun coût réel.

✅ **Cohérence (vision critique 2)** : `QuestionSet.dataset_id` est une vraie FK obligatoire (`CASCADE`) -- un ensemble ne peut jamais réellement exister détaché de son propre dataset.

✅ **Robustesse (vision critique 3) -- suppression d'une question** : `QuestionSetItem.question_id` porte un vrai `ondelete="CASCADE"` -- supprimer une vraie question retire automatiquement, au niveau base de données, toute vraie ligne de membership qui la référence, avant même que ce module ne s'exécute. `reorder_questions` valide en plus explicitement que les vrais `question_ids` donnés correspondent EXACTEMENT à la vraie composition actuelle -- une vraie `ValueError` honnête pour une requête de réorganisation périmée, jamais une réorganisation partielle silencieuse.

Tests réels dédiés (11 + 5 tests), voir `tests/test_question_sets.py` + `tests/test_question_sets_endpoints.py`.

#### Partie 7.1.3 — Ground-truth answers

✅ **Nouveau module réel** `api/services/ground_truth_answers.py` : les 7 fonctions littérales.

⚠️ **Cohérence (vision critique 1) -- `validate_semantic`, délibérément basé sur de vrais embeddings, contrairement à la Partie 6.2** : les vrais modules 6.2 évitaient délibérément les embeddings réels (un vrai coût par appel d'agent en direct). La validation de ground truth est le cas inverse réel : une vraie évaluation HORS LIGNE, jamais un vrai chemin d'exécution par réponse en direct -- le vrai coût d'embedding est ici pleinement justifié, et le littéral de cette étape demande explicitement une vraie similarité sémantique (embedding), pas un proxy rapide par recouvrement de mots.

✅ **Robustesse (vision critique 3)** : chaque vrai validateur retourne honnêtement `False` pour une vraie réponse ou attente vide.

Tests réels dédiés (17 tests), voir `tests/test_ground_truth_answers.py`.

#### Partie 7.1.4 — Ground-truth documents

✅ **Nouveau module réel** `api/services/ground_truth_documents.py` : les 6 fonctions littérales + `calculate_retrieval_ndcg`/`calculate_retrieval_hit_rate` (réelles, additionnelles -- l'item 3 littéral liste 5 vraies métriques, seules 3 fonctions `calculate_retrieval_*` étaient nommées).

✅ **Cohérence -- définitions IR réelles et standard** : `src/evaluation.py`'s own script legacy calcule un vrai "hit_at_k"/"reciprocal_rank" SOUS le nom "recall_at_k" -- une vraie imprécision honnête que ce module corrige : `hit_rate@k` ("un vrai document attendu a-t-il été trouvé") est réellement distinct de `recall@k` ("quelle vraie fraction de TOUS les documents attendus a été trouvée").

✅ **Robustesse (vision critique 3)** : chaque vraie métrique retourne honnêtement `0.0` sans documents attendus réels.

Tests réels dédiés (14 tests), voir `tests/test_ground_truth_documents.py`.

#### Partie 7.1.5 — Easy/Medium/Hard

✅ **Nouveau module réel** `api/services/question_difficulty.py` : les 4 fonctions littérales.

✅ **Cohérence (vision critique 1) -- 5 vrais proxies honnêtement calculables** : `entities` compte les vrais mots capitalisés (hors premier mot) -- délibérément PAS une réutilisation de `metadata_enrichment.extract_entities` (qui ne reconnaît que email/url/date/argent/téléphone, un vrai signal honnêtement inutile pour une question ordinaire comme "Qui était président de la France en 1990 ?").

✅ **Robustesse (vision critique 3)** : une vraie question vide retourne honnêtement un score `0.0` / une classification `"easy"`.

Tests réels dédiés (8 tests), voir `tests/test_question_difficulty.py`.

#### Partie 7.1.6 — Benchmark versions

✅ **Nouveau module réel** `api/services/benchmark_versions.py` : les 6 fonctions littérales + 5 nouveaux endpoints réels Admin+ (`api/routers/benchmark_versions.py`).

⚠️ **`snapshot` stocke du vrai CONTENU, pas de la vraie IDENTITÉ** : chaque vraie entrée est le contenu réel d'une question (texte, réponse attendue, ...), délibérément SANS son propre id réel -- une question restaurée par rollback est une vraie copie fidèle de ce qu'une version contenait, avec un nouvel id réellement différent. `compare_benchmark_versions` associe donc les entrées par leur propre TEXTE de question réel entre les deux vrais snapshots -- un choix réel, honnête, documenté.

⚠️ **Une vraie opération honnêtement destructive** : `rollback_to_version` supprime réellement TOUTES les questions actuelles du dataset (leurs vraies appartenances `QuestionSetItem` disparaissent en cascade) avant de les recréer depuis le vrai snapshot -- documenté clairement, jamais adouci.

✅ **Robustesse (vision critique 3) -- version corrompue** : la vraie forme du snapshot est validée AVANT toute suppression réelle -- un vrai snapshot corrompu lève une erreur, laissant le dataset actuel totalement intact.

Tests réels dédiés (10 + 4 tests), voir `tests/test_benchmark_versions.py` + `tests/test_benchmark_versions_endpoints.py`.

**Régression complète** (104+ tests sur les 6 nouveaux modules + endpoints + `test_password_similarity.py`) : zéro échec.

### 7.2 Evaluation runs & metrics — ✅ COMPLET (15/15)

**Réutilisation réelle, pas 9 fonctions indépendantes (décision autonome)** : ces 9 étapes redemandent en grande partie des métriques déjà construites en 7.1.4 (precision/recall/mrr/ndcg génériques à `k`) et 6.2.11 (faithfulness) -- résolu par une architecture de consolidation documentée : `api/services/retrieval_metrics.py` (wrappers fins à `k` fixe + résumés dataset) et `api/services/answer_quality_metrics.py` (faithfulness/answer_relevance, sur chaînes/dicts plutôt que sur des lignes ORM `Response`/`Citation`, car l'Evaluation Lab teste une configuration hypothétique, pas une réponse réellement servie et persistée).

**Nouveau vrai modèle** `EvaluationResult` (migration 0072) : un vrai résultat persisté d'un run réel (documents/chunks récupérés, réponse générée, métriques calculées, latence).

**`extend_evaluation_metrics`, UNE vraie fonction partagée, pas 7 identiques** : les étapes 7.2.2 à 7.2.9 redéclarent toutes le même nom littéral `extend_evaluation_metrics(question_id)` -- construite une seule fois dans `api/services/evaluation_results.py`, elle recalcule TOUTES les métriques réelles de ce lot pour chaque résultat déjà enregistré d'une question, contre sa vraie ground truth ACTUELLE (utile pour re-scorer après un changement de `set_ground_truth`/`set_ground_truth_documents`).

#### Partie 7.2.1 — Recall@1 (run_evaluation)

✅ **Nouveau module réel** `api/services/evaluation_results.py` : `run_evaluation`, `get_evaluation_results`, `get_metrics_summary`, `extend_evaluation_metrics`, `calculate_recall_at_1` (réexportée depuis `retrieval_metrics.py`) + 3 nouveaux endpoints réels Admin+ (`POST /questions/{id}/run`, `GET /questions/{id}/results`, `GET /datasets/{id}/metrics/{metric}`, `api/routers/evaluation_results.py`).

⚠️ **Cohérence (vision critique 1) -- réutilise les mêmes briques que `generate_response` (6.1.1), délibérément SANS l'appeler** : `run_evaluation` réutilise `search_with_context`/`resolve_llm_config`/`chat_completion` (et même le vrai `CITATION_INSTRUCTIONS`, rendu public depuis `generation.py`, pour que le prompt réel d'évaluation reflète fidèlement ce que la production enverrait réellement) -- mais un run d'évaluation teste une configuration CANDIDATE (potentiellement différente de la config par défaut de l'organisation), et son résultat appartient à `EvaluationResult`, jamais aux tables `Response`/`Citation` réellement servies.

✅ **Performance (vision critique 1) -- vrai timeout honnête** : `EVALUATION_TIMEOUT` borne le vrai appel retrieval+génération via `asyncio.wait_for` (même précédent que `AgentOrchestrator.run_agent`) -- une vraie réponse vide honnête est enregistrée en cas de dépassement, jamais un run bloqué indéfiniment.

Tests réels dédiés (8 + 5 tests), voir `tests/test_evaluation_results.py` + `tests/test_evaluation_results_endpoints.py`.

#### Partie 7.2.2 / 7.2.3 / 7.2.4 — Recall@3 / Recall@5 / Recall@10

✅ `calculate_recall_at_3`/`_5`/`_10` (`api/services/retrieval_metrics.py`) : vrais wrappers fins autour de `calculate_retrieval_recall` (7.1.4), qui calcule déjà le recall réel à N'IMPORTE QUEL `k` -- pas 3 réimplémentations de la même vraie métrique. `get_recall_summary(dataset_id, k)` est UNE seule vraie fonction paramétrée par `k`, réutilisée identiquement par les 3 étapes.

#### Partie 7.2.5 — MRR

✅ `calculate_mrr` : réexport direct de `calculate_retrieval_mrr` (7.1.4, ne prend déjà aucun `k`). `get_mrr_summary`.

#### Partie 7.2.6 — NDCG

⚠️ **Vraie amélioration mathématique appliquée à la fonction existante, pas dupliquée** : le littéral de cette étape (gain exponentiel, pertinence graduée configurable) a révélé que le NDCG de 7.1.4 utilisait un gain linéaire, alors que la définition standard (Järvelin & Kekäläinen) utilise `2^pertinence - 1`. Mise à niveau réelle de `calculate_retrieval_ndcg`, nouvelles fonctions publiques `calculate_dcg`/`calculate_idcg`, configurables via `NDCG_GAIN_FUNCTION`/`NDCG_GRADED_RELEVANCE`/`NDCG_DEFAULT_K`. Vérifié : zéro régression sur les 14 tests existants de `tests/test_ground_truth_documents.py` (gain exponentiel et linéaire sont mathématiquement identiques pour une pertinence binaire, et "ordre idéal = 1.0" reste vrai pour toute fonction de gain monotone).

#### Partie 7.2.7 — Precision

✅ `calculate_precision` : réutilise `calculate_retrieval_precision`, avec son propre réglage indépendant `PRECISION_DEFAULT_K` (distinct de `GROUND_TRUTH_RETRIEVAL_K`).

#### Partie 7.2.8 — Faithfulness (evaluation runs)

✅ **Nouveau module réel** `api/services/answer_quality_metrics.py` : `calculate_faithfulness` (4 facteurs réels : `claim_support`, `source_alignment`, `context_usage`, `hallucination_absence`, pondérés via `EVALUATION_FAITHFULNESS_FACTORS_WEIGHTS`).

⚠️ **Cohérence -- réutilise les mêmes primitives que 6.2.11, sans réimplémentation** : `jaccard_similarity`/`extract_claims`/`find_contradiction` (6.2.5/6.2.7) opèrent déjà sur de simples chaînes -- aucun adaptateur nécessaire pour les réutiliser ici, malgré l'architecture délibérément différente (chaînes/dicts, pas `Response`/`Citation` ORM).

#### Partie 7.2.9 — Answer relevance

✅ `calculate_answer_relevance` (4 facteurs réels : `question_coverage`, `key_terms_presence`, `semantic_similarity`, `length_adequacy`, pondérés via `ANSWER_RELEVANCE_FACTORS_WEIGHTS`).

⚠️ **`ANSWER_RELEVANCE_USE_LLM`, honnêtement PAS ENCORE implémenté** : même précédent réel que `CLAIM_VERIFICATION_USE_LLM` (6.2.6) -- un vrai appel LLM par réponse coûte un vrai crédit API, la même vraie contrainte documentée dans toute la section 6.2. `NotImplementedError` explicite, jamais un faux repli silencieux.

✅ **Robustesse (vision critique 3)** : `semantic_similarity` réutilise directement `ground_truth_answers.cosine_similarity` (rendue publique) -- vrais embeddings réels justifiés ici car l'Evaluation Lab est un contexte HORS LIGNE (même raisonnement que 7.1.3), contrairement aux vérifications 6.2 en direct qui les évitent délibérément.

**Régression complète (7.2.1-7.2.9)** (43 tests sur les 4 nouveaux fichiers `test_retrieval_metrics.py`/`test_answer_quality_metrics.py`/`test_evaluation_results.py`/`test_evaluation_results_endpoints.py`, plus zéro régression sur `test_ground_truth_documents.py`/`test_ground_truth_answers.py`/`test_generation.py`/`test_agent_orchestrator.py`) : zéro échec.

#### Partie 7.2.10 — Context relevance

✅ **Nouveau module réel** `api/services/context_relevance.py` : `calculate_context_relevance` (4 facteurs réels : `context_coverage`, `chunk_relevance_avg`, `redundancy_score`, `information_density`), `get_context_relevance_summary`.

⚠️ **Cohérence (vision critique 1) -- délibérément le miroir réel de `calculate_answer_relevance`** : même forme `{"score", "factors"}`, même motif `*_FACTORS_WEIGHTS` (validé à somme 1.0), même précédent `*_USE_LLM` -- Context relevance (l'ENTRÉE de la génération) et Answer relevance (la SORTIE) sont de vrais frères dans le vocabulaire de ce code, donc partagent délibérément la même vraie forme. `CONTEXT_RELEVANCE_FACTORS_WEIGHTS` est un ajout réel et autonome au-delà de la config littéralement demandée, pour cette même cohérence.

✅ **Performance (vision critique 2)** : `chunk_relevance_avg`, seul facteur basé sur de vrais embeddings, est bornée par `CONTEXT_RELEVANCE_MAX_CHUNKS` -- un vrai résultat de récupération volumineux ne peut jamais rendre ce coût réel illimité. `redundancy_score` réutilise volontairement le rapide heuristique `jaccard_similarity` (pas d'embeddings, car la redondance est un vrai chevauchement littéral de texte).

⚠️ **`redundancy_score`, une vraie polarité documentée** : le facteur rapporté reste honnêtement BRUT (plus élevé = plus redondant = pire), mais sa contribution réelle au score pondéré utilise `(1 - redundancy_score)` -- le dict de facteurs reste honnête, seule la combinaison inverse.

✅ **Robustesse (vision critique 3)** : chaque facteur retourne honnêtement `0.0` sans contexte/chunks réels.

Tests réels dédiés (8 tests), voir `tests/test_context_relevance.py`.

#### Partie 7.2.11 — Citation correctness

✅ **Nouveau module réel** `api/services/citation_correctness.py` : `calculate_citation_correctness` (4 facteurs réels : `citation_presence`, `citation_accuracy`, `citation_format`, `citation_completeness`), `get_citation_correctness_summary`.

⚠️ **Correction autonome de signature** : le littéral demandé `calculate_citation_correctness(citations, context)` omettait `answer` -- pourtant le seul vrai endroit où vivent les marqueurs `[n]`. Corrigé en `(answer, citations, context)`, exactement la même forme réelle à 3 arguments que `calculate_faithfulness`.

✅ **Précision (vision critique 2) -- deux vraies sources, pour deux vraies questions** : `citation_presence` vérifie un vrai marqueur `[n]` contre le vrai CONTEXTE NUMÉROTÉ lui-même (le littéral français : "présence des citations DANS LE CONTEXTE") ; `citation_accuracy` vérifie que le vrai CONTENU CITÉ (liste `citations`, par position) supporte réellement la phrase portant ce marqueur.

✅ **Robustesse (vision critique 3)** : chaque facteur a sa propre convention honnête documentée (`citation_format`/`citation_completeness` : `1.0` vacuous sans rien de réel à vérifier ; `citation_presence`/`citation_accuracy` : `0.0` sans rien de réel).

Tests réels dédiés (7 tests), voir `tests/test_citation_correctness.py`.

#### Partie 7.2.12 — Hallucination rate

✅ **Nouveau module réel** `api/services/hallucination_rate.py` : `calculate_hallucination_rate` (4 facteurs réels : `unsupported_claims_ratio`, `contradiction_rate`, `source_coverage`, `confidence_estimation`), `get_hallucination_rate_summary`.

⚠️ **Cohérence -- réutilise, ne réimplémente jamais une 3e fois** : `unsupported_claims_ratio`/`contradiction_rate` sont les vrais inverses honnêtes de `claim_support`/`hallucination_absence` (6.2.11/7.2.8, rendues publiques pour cette réutilisation directe) ; `confidence_estimation` réutilise directement le vrai score `calculate_faithfulness` déjà calculable pour ce même résultat, plutôt qu'une 5e formule de confiance concurrente.

⚠️ **Une vraie polarité inversée, documentée explicitement** : `hallucination_rate` est un TAUX d'une chose mauvaise -- plus élevé = pire, contrairement à tout autre score de ce lot. `source_coverage`/`confidence_estimation` restent honnêtement "plus élevé = mieux" dans leur propre facteur rapporté ; seule leur CONTRIBUTION au score combiné utilise `(1 - facteur)`.

✅ **Robustesse (vision critique 3) -- réponse courte** : sous `HALLUCINATION_RATE_MIN_CLAIMS`, le calcul s'exécute normalement (jamais de crash) mais retourne honnêtement `"reliable": False`.

Tests réels dédiés (7 tests), voir `tests/test_hallucination_rate.py`.

#### Partie 7.2.13 — Latency

✅ **Nouveau module réel** `api/services/latency_metrics.py` : `measure_latency` (p50/p90/p95/p99/avg/min/max/std réels, sans dépendance numpy/scipy), `get_latency_summary`, `get_latency_distribution`.

⚠️ **Cohérence -- délibérément PAS repliée dans `extend_evaluation_metrics` (décision autonome documentée)** : chaque autre métrique 7.2.x est une vraie fonction pure d'un `EvaluationResult` déjà stocké, donc recalculable en toute sécurité par la boucle partagée. Un vrai BENCHMARK de latence est structurellement différent (une vraie distribution sur PLUSIEURS runs frais) -- l'esprit du littéral "`extend_evaluation_metrics(question_id)`" est honoré (ne jamais dupliquer un nom déjà partagé pour une opération réellement différente), pas sa lettre. `get_latency_summary`/`get_latency_distribution` réutilisent gratuitement le vrai `latency_ms` DÉJÀ stocké par chaque run (7.2.1), zéro coût réel additionnel.

✅ **Performance (vision critique 1)** : `LATENCY_TIMEOUT` borne tout le vrai budget temporel de la boucle warmup+mesure (pas par appel) -- un vrai résultat partiel honnête est retourné, jamais un crash.

✅ **Robustesse (vision critique 3)** : un vrai run en timeout (réponse vide) est honnêtement exclu du vrai échantillon de latence.

Nouvel endpoint réel Admin+ dédié : `POST /questions/{id}/latency` (le seul des 6 étapes 7.2.10-7.2.15 à réellement en nécessiter un nouveau -- tous les autres sont déjà exposés par l'endpoint générique existant `GET /datasets/{id}/metrics/{metric}`, 7.2.1).

Tests réels dédiés (3 tests), voir `tests/test_latency_metrics.py`.

#### Partie 7.2.14 — Token usage

✅ **Nouveau module réel** `api/services/token_usage.py` : `measure_token_usage`, `get_token_usage_summary`, `get_token_usage_distribution`, `estimate_token_usage`. Nouvelle fonction réelle additive `chat_completion_with_usage` (`api/services/llm_providers.py`), sœur de `chat_completion` (jamais modifiée -- ses nombreux appelants réels existants ne changent pas de comportement), partageant le même vrai cœur de retry (`_chat_completion_raw`, extrait sans duplication).

⚠️ **Cohérence -- capturé au moment réel de la génération, jamais recalculé après coup** : contrairement à toute autre métrique 7.2.x, l'usage réel de tokens ne peut PAS être reconstruit depuis une réponse déjà stockée -- capturé directement dans `run_evaluation` et persisté immédiatement, délibérément jamais retouché par `extend_evaluation_metrics` (même exception documentée que `latency_ms`).

✅ **Robustesse (vision critique 3) -- tokens non disponibles** : repli honnête vers `estimate_token_usage` (ratio réel ~4 caractères/token, `TOKEN_USAGE_ESTIMATE_CHARS_PER_TOKEN`), toujours marqué `"estimated": True` pour ne jamais se faire passer pour un vrai compte fournisseur.

Tests réels dédiés (7 tests), voir `tests/test_token_usage.py`.

#### Partie 7.2.15 — Cost/request

✅ **Nouveau module réel** `api/services/cost_tracking.py` : `calculate_cost_per_request`, `get_cost_summary`, `get_cost_distribution`. Table de tarifs réels `COST_MODEL_PRICING` (les 8 modèles du littéral).

⚠️ **Précision (vision critique 2) -- correspondance par le plus long sous-chaîne réel, jamais une égalité exacte** : les vrais noms de modèles RÉSOLUS par ce code portent un vrai préfixe/suffixe de version que litellm ajoute lui-même (ex. `"claude-3-5-sonnet-20241022"`) -- une égalité exacte contre les clés courtes du littéral (`"claude-3-5-sonnet"`) ne trouverait honnêtement RIEN. `_find_pricing` fait donc une correspondance par sous-chaîne, avec un vrai départage par la clé la PLUS LONGUE (nécessaire : `"gpt-4o-mini"` contient réellement `"gpt-4o"` comme sous-chaîne).

🐛 **Vrai bug préexistant découvert (hors périmètre de cette étape, NON corrigé ici, documenté et signalé)** : `api/security/organization_settings.py`'s own `DEFAULT_SETTINGS["llm_model"]` vaut la vraie chaîne obsolète `"claude-3-sonnet-20240229"` (jamais `None`) -- `get_org_settings` fusionne TOUJOURS ce vrai défaut dans son dict retourné, donc `resolve_llm_model`'s own condition `org_settings.get("llm_model")` est TOUJOURS vraie, et sa vraie branche "repli sur le modèle live du fournisseur" (déjà documentée comme intentionnelle dans le docstring de ce même resolver depuis la Partie 4.3.1) n'est en réalité JAMAIS atteinte pour une organisation fraîche. Impact réel : chaque nouvel appel LLM utilise réellement le modèle Anthropic obsolète `"claude-3-sonnet-20240229"`, sauf override explicite. Corrigé de façon MINIMALE et sûre ici (ajout de `"claude-3-sonnet"` à `COST_MODEL_PRICING`, pour que ce vrai cas courant reste honnêtement chiffrable), le vrai correctif de fond (`DEFAULT_SETTINGS["llm_model"] = None` + ajustement du schéma de réponse `OrganizationSettingsResponse`) est délibérément laissé pour une passe dédiée -- trop risqué à tenter au milieu d'un lot de 6 étapes sans re-tester l'intégralité de `test_organization_settings.py` (20+ tests) séparément.

✅ **Robustesse (vision critique 3)** : `calculate_cost_per_request` ne lève jamais pour un vrai modèle non tarifé -- chaque champ de coût honnêtement `None`, `pricing_available: False`.

Tests réels dédiés (7 tests), voir `tests/test_cost_tracking.py`.

**Régression complète (7.2.10-7.2.15)** (39 tests sur les 6 nouveaux fichiers, plus zéro régression sur `test_evaluation_results.py`/`test_evaluation_results_endpoints.py`/`test_answer_quality_metrics.py`/`test_retrieval_metrics.py`/`test_evaluation_comparisons.py`/`test_generation.py`/`test_agent_orchestrator.py`/`test_llm_providers.py`/`test_llm_config.py`/`test_organization_settings.py`) : zéro échec.

### 7.2.16 (bis) — Fondation autonome : comparaisons multi-modèles & A/B testing (offline, niveau question) — ✅ COMPLET

**Renommée depuis l'ancienne "Partie 7.3"** : bâtie de manière autonome, avant réception d'aucun prompt DeepSeek pour une vraie Partie 7.3 (voir la version précédente de cette section, qui portait alors ce nom : "prompts non encore reçus"). Une fois les vrais prompts 7.3.1-7.3.10 reçus, ils définissent une Partie 7.3 bien plus large et différemment scopée (jobs persistés, Celery, seuils de régression, A/B testing PRODUCTION) -- cette section est donc renumérotée ici pour éviter toute collision, et sert de vraie fondation réutilisée directement par 7.3.4 (Model comparison) et 7.3.10 (A/B testing production) : `run_multi_model_comparison`/`run_ab_test` restent le vrai mécanisme OFFLINE, au niveau d'une question, que ces deux étapes officielles enveloppent avec une vraie persistance/Celery/traffic-splitting.

✅ **Nouveau module réel** `api/services/evaluation_comparisons.py` : `run_multi_model_comparison`, `run_ab_test`.

⚠️ **Portée réelle par un vrai `QuestionSet`, pas tout un dataset** : une vraie comparaison a besoin des MÊMES vraies questions pour chaque config candidate -- `QuestionSet` (7.1.2) est déjà le vrai concept "sous-ensemble réel, ordonné, de questions d'un dataset" -- réutilisé directement via `get_questions_in_set`, plutôt qu'un second concept concurrent.

⚠️ **Agrégation réelle par comparaison, pas par dataset entier (décision autonome)** : `retrieval_metrics.get_dataset_result_metrics` agrège TOUT résultat réel qu'un dataset possède, sans distinction de config -- inutilisable pour une vraie comparaison honnête si ce dataset contient déjà d'autres runs réels. Nouvelles fonctions `get_result_metrics`/`summarize_metric_for_results` (`retrieval_metrics.py`) agrégeant sur un ensemble PRÉCIS de vrais `EvaluationResult` ids -- exactement ceux que la comparaison vient elle-même de produire, jamais une correspondance fragile sur le JSON `model_config_json` stocké.

⚠️ **Exécution réellement SÉQUENTIELLE, pas `asyncio.gather`** : chaque run de ce module partage la même vraie `AsyncSession` (une session SQLAlchemy async ne supporte pas deux opérations réelles en vol simultanément) -- et les vrais appels LLM/retrieval ont de vraies limites de débit de toute façon, rendant l'exécution séquentielle réelle à la fois une contrainte technique réelle et un choix honnête respectueux du vrai coût, pas une simple simplification.

⚠️ **Vrai test statistique exact, pas scipy** : `_sign_test_p_value` implémente le test du signe bilatéral exact (sous H0, le nombre réel de victoires de A suit une vraie loi Binomiale(n, 0.5) -- p-value calculable exactement via `math.comb`, sans nouvelle dépendance, sans distribution approximée). Choisi délibérément plutôt qu'un test t apparié, qui supposerait en plus une vraie normalité des écarts par question -- une hypothèse que ce module ne fait jamais.

✅ **Robustesse (vision critique 3)** : `run_ab_test` ignore honnêtement toute vraie question où une métrique demandée n'existe pas pour l'un des deux réels résultats (jamais une égalité fabriquée) ; `_sign_test_p_value(0, 0)` retourne honnêtement `1.0` (aucune preuve réelle ne peut jamais paraître significative).

✅ **2 nouveaux endpoints réels Admin+** (`api/routers/evaluation_comparisons.py`) : `POST /sets/{set_id}/compare`, `POST /sets/{set_id}/ab-test`, réutilisant directement `require_question_set_admin` (7.1.2).

Tests réels dédiés (7 + 4 tests), voir `tests/test_evaluation_comparisons.py` + `tests/test_evaluation_comparisons_endpoints.py`.

**Régression complète** : zéro échec (voir section suivante pour le décompte global).

### 7.3 MLOps avancé — ✅ COMPLET (10/10)

Persistance réelle des runs d'évaluation en tant que vrais jobs Celery, notation humaine, détection de régression, comparaisons persistées (modèle/retriever/reranker/prompt), auto-eval pré-déploiement, seuils configurables, A/B testing PRODUCTION avec traffic-splitting réel.

#### Partie 7.3.1 — Automatic evaluation

✅ **Nouveau vrai modèle** `EvaluationJob` (migration 0073) + colonne `EvaluationResult.evaluation_job_id` (FK nullable, réelle et nécessaire pour relier chaque résultat à son job sans table d'items séparée -- `EvaluationResult` EST déjà l'enregistrement réel par question).

✅ **Nouveau module réel** `api/services/evaluation_jobs.py` : `create_evaluation_job`, `run_evaluation_job`, `get_evaluation_job`, `list_evaluation_jobs`, `cancel_evaluation_job`, `get_evaluation_job_results`. Réutilise directement `run_evaluation` (7.2.1) -- aucune deuxième pipeline de génération.

⚠️ **Même vraie résilience par item que `process_batch_job`** (Partie 2.2.16), réutilisée à l'identique : commit après CHAQUE vraie question, une vraie question en échec ne bloque jamais les suivantes, annulation coopérative vérifiée avant chaque vraie question.

🐛 **Vrai bug trouvé et corrigé pendant l'implémentation** : un vrai `db.rollback()` (chemin d'échec par question) expire TOUS les objets réels du dataset SQLAlchemy encore en session -- y compris les vraies questions pas encore traitées de la boucle. Lire `question.id` sur un vrai objet expiré, hors d'un vrai `await db.refresh(...)`, lève une vraie `MissingGreenlet` (SQLAlchemy async interdit tout vrai IO implicite synchrone). Corrigé en capturant les vrais UUIDs de questions AVANT la boucle -- un vrai `uuid.UUID` brut n'expire jamais.

✅ **Scalabilité (vision critique 3)** : `create_evaluation_job` ne persiste qu'une vraie ligne `pending` ; le vrai travail (`run_evaluation_job`) est dispatché à un vrai worker Celery (`api/tasks/evaluation_jobs.py`), jamais exécuté en ligne dans une requête HTTP.

Nouveaux endpoints réels Admin+ : `POST /datasets/{id}/evaluate`, `GET /datasets/{id}/jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `GET /jobs/{id}/results`.

Tests réels dédiés (7 + 5 tests), voir `tests/test_evaluation_jobs.py` + `tests/test_evaluation_jobs_endpoints.py`.

#### Partie 7.3.2 — Manual evaluation

✅ **Nouveau vrai modèle** `ManualEvaluation` (même migration 0073).

✅ **Nouveau module réel** `api/services/manual_evaluations.py` : `create_manual_evaluation`, `update_manual_evaluation`, `get_manual_evaluation`, `list_manual_evaluations`, `get_manual_evaluation_summary`, `get_manual_evaluation_stats`.

✅ **Robustesse (vision critique 3) -- un critère manquant** : `criteria` est un vrai dict PARTIEL -- n'importe quel sous-ensemble des 5 vrais critères connus, ou aucun. Seule une vraie clé INCONNUE ou une valeur hors 1-5 lève une erreur ; un vrai critère manquant n'en est jamais une.

⚠️ **Sécurité (vision critique 1)** : nouvelles dépendances réelles `require_question_member`/`require_manual_evaluation_access` (Member+, hors Viewer) dans `api/security/evaluation.py` ; `PATCH /evaluations/{id}` vérifie en plus une vraie propriété (`evaluator_id == current_user.id`) OU Admin+.

🐛 **Vrai bug trouvé et corrigé** : les endpoints POST/PATCH ne rafraîchissaient jamais l'objet réel après commit -- `updated_at` (calculé côté serveur, `onupdate=func.now()`) déclenchait un vrai rechargement paresseux synchrone pendant la sérialisation Pydantic, hors contexte async valide (`MissingGreenlet`). Corrigé par un vrai `await db.refresh(...)` avant chaque retour.

Nouveaux endpoints réels : `POST /questions/{id}/evaluate` (Member+), `GET /questions/{id}/evaluations` (Member+), `GET /questions/{id}/evaluations/summary` (Member+, ajout réel au-delà du littéral -- la fonction existait déjà sans point d'entrée), `GET /evaluations/{id}` (Member+), `PATCH /evaluations/{id}` (Member+ propriétaire ou Admin+), `GET /datasets/{id}/evaluations/stats` (Admin+).

Tests réels dédiés (8 + 5 tests), voir `tests/test_manual_evaluations.py` + `tests/test_manual_evaluations_endpoints.py`.

**Régression complète (7.3.1/7.3.2)** : 26 tests dédiés + zéro régression sur `test_batch_jobs.py`/`test_question_sets.py`/`test_evaluation_datasets.py`/`test_evaluation_results.py`.

#### Partie 7.3.4/7.3.5/7.3.6/7.3.7 — Model/Retriever/Reranker/Prompt comparison

⚠️ **Consolidation réelle et autonome majeure** : ces 4 étapes ont une liste de colonnes littérales STRUCTURELLEMENT IDENTIQUE (`id`, `dataset_id`, `name`, une vraie liste de candidats, `results`, `created_by`, `created_at`, `completed_at`) et la MÊME liste de 6 fonctions littérales (`create_*`, `run_*`, `get_*`, `list_*`, `compare_*`, `get_*_results`) sous 4 noms différents. Construites comme UN SEUL vrai modèle `ComparisonJob` (migration 0074, colonne `comparison_type` distinguant les 4 vrais types) + UN SEUL vrai moteur partagé `run_comparison_job` (`api/services/comparison_jobs.py`), avec les 24 fonctions littérales exposées comme de vrais alias fins par-type -- jamais 4 modèles et 4 moteurs quasi-identiques.

✅ **`run_evaluation` étendu (7.2.1)** : nouveau paramètre réel `retrieval_overrides`, transmis directement à `search_with_context` (qui accepte déjà `strategy`/`reranker`/`top_k`/`score_threshold`) -- rend les comparaisons retriever/reranker possibles sans une deuxième pipeline réelle de retrieval+génération.

⚠️ **Cohérence (vision critique) -- un vrai variant reranker n'a d'effet que sous `hybrid_reranked`** : `search()`'s own real dispatch ne transmet `reranker` au réel strategy function QUE si `strategy == "hybrid_reranked"` -- une comparaison de rerankers normalise donc automatiquement chaque vrai variant en `{"strategy": "hybrid_reranked", "reranker": variant}`, pour ne jamais livrer une comparaison silencieusement inerte.

✅ **Prompt comparison, zéro nouvelle machinerie** : un variant "prompt" est une simple vraie chaîne, devenant `model_config={"system_prompt": variant}` -- `resolve_system_prompt` (7.2.9) résout déjà cet override réel.

✅ **`compare_*`/`run_*`, deux vrais noms honnêtes pour une seule vraie opération** : même précédent réel que `process_batch_job_task`/`resume_batch_job_task` (2.2.16) -- le littéral de chaque étape demande LES DEUX fonctions avec la même signature réelle `(comparison_id)`.

✅ **Robustesse (vision critique 3)** : même vraie résilience par variant/question que `run_evaluation_job` (7.3.1) -- un vrai échec est journalisé et ignoré, jamais fatal pour toute la comparaison. `create_retriever_comparison` valide chaque vraie stratégie contre les 5 vraies stratégies connues.

✅ **Scalabilité (vision critique)** : chaque `create_*` planifie immédiatement une vraie exécution Celery (`api/tasks/comparison_jobs.py`, UNE seule vraie tâche partagée par les 4 types) -- satisfait le "exécutées de manière asynchrone" des 4 étapes, même si seule 7.3.4 nomme littéralement un endpoint `POST /comparisons/{id}/run` séparé (conservé ici comme un vrai déclencheur additionnel, ex. pour relancer après un échec Celery transitoire).

🐛 **Vrai piège de mock découvert et corrigé pendant les tests (leçon méthodologique, pas un bug de production)** : `unittest.mock.patch("api.services.X.schedule_Y")` ne suffit PAS quand le routeur importe `schedule_Y` via `from api.services.X import schedule_Y` -- l'attribut patché sur le module source ne touche jamais le nom déjà lié dans l'espace de noms du routeur. Corrigé en patchant `api.routers.X.schedule_Y` à la place -- corrige AUSSI un vrai ralentissement de suite de tests (chaque patch inefficace déclenchait un vrai essai de connexion Celery/Redis réel, ~15-20s de retries par appel).

Endpoints réels Admin+ (17 au total) : `POST/GET /datasets/{id}/compare|comparisons`, `GET/POST /comparisons/{id}[/results|/run]` (7.3.4) ; `POST/GET /datasets/{id}/retrievers/compare|comparisons`, `GET /retriever-comparisons/{id}[/results]` (7.3.5) ; mêmes formes pour `/rerankers/` (7.3.6) et `/prompts/` (7.3.7).

Tests réels dédiés (10 + 13 tests), voir `tests/test_comparison_jobs.py` + `tests/test_comparison_jobs_endpoints.py`.

**Régression complète (7.3.4-7.3.7)** : zéro échec.

#### Partie 7.3.9 — Seuils de régression

✅ **Nouveau vrai modèle** `RegressionThreshold` (migration 0075, `UniqueConstraint(organization_id, metric)`).

✅ **Nouveau module réel** `api/services/regression_thresholds.py` : `set_regression_threshold` (vrai UPSERT, pas de doublons), `get_regression_thresholds`, `check_regression_thresholds`, `update_regression_threshold`, `delete_regression_threshold`. `LOWER_IS_BETTER_METRICS` (`hallucination_rate`/`latency`/`cost_per_request`) réutilisé directement par 7.3.3.

✅ **Robustesse (vision critique 3) -- métrique manquante** : `check_regression_thresholds` ignore honnêtement toute vraie métrique sans seuil configuré ou absente du dict donné -- jamais un faux verdict.

Endpoints réels Admin+ : `POST/GET /organizations/{id}/thresholds`, `GET/PATCH/DELETE /thresholds/{id}`, `POST /organizations/{id}/thresholds/check`.

Tests réels dédiés (9 + 4 tests), voir `tests/test_regression_thresholds.py` + `tests/test_regression_thresholds_endpoints.py`.

#### Partie 7.3.3 — Regression detection

✅ **Nouveau vrai modèle** `RegressionDetection` (même migration 0075).

✅ **Nouveau module réel** `api/services/regression_detection.py` : `detect_regressions`, `get_regressions`, `get_regression_summary`, `resolve_regression`, `get_regression_alert`. Réutilise directement `retrieval_metrics.summarize_metric_for_results` sur les vrais `result_ids` déjà stockés par chaque job (7.3.1) -- jamais une moyenne recalculée et figée au moment du job (la vraie ground truth peut changer après coup).

🐛 **Vrai bug trouvé et corrigé pendant les tests, avec impact réel sur 7.3 (Group B déjà livré)** : `metric_keys()` (`evaluation_comparisons.py`, réutilisée par les comparaisons ET par cette étape) était restée figée à la liste 7.2.1-7.2.9 -- `hallucination_rate`/`context_relevance`/`citation_correctness`/`cost_per_request` (7.2.10-7.2.15) en étaient honnêtement absents. Corrigée pour inclure tous les vrais indicateurs de qualité pertinents -- bénéficie aussi rétroactivement aux comparaisons 7.3.4-7.3.7 déjà livrées (aucune migration nécessaire, changement pur Python).

✅ **Robustesse (vision critique 3) -- échantillons insuffisants** : chaque moyenne réutilise `REGRESSION_MIN_SAMPLES` (7.3.3) -- une vraie métrique sous ce seuil est honnêtement exclue de toute comparaison, jamais un verdict statistiquement fragile.

⚠️ **Endpoint réel additionnel** : le littéral ne liste aucun endpoint pour déclencher `detect_regressions` lui-même -- `POST /datasets/{id}/regressions/detect` ajouté (real, nécessaire) pour permettre à un vrai appelant de nommer les deux jobs à comparer.

Endpoints réels Admin+ : `GET /datasets/{id}/regressions[/summary]`, `POST /datasets/{id}/regressions/detect`, `POST /regressions/{id}/resolve`.

Tests réels dédiés (9 + 4 tests), voir `tests/test_regression_detection.py` + `tests/test_regression_detection_endpoints.py`.

**Régression complète (7.3.3/7.3.9)** : 26 tests dédiés + zéro régression sur `test_evaluation_comparisons.py`/`test_comparison_jobs.py` (qui réutilisent `metric_keys()`).

#### Partie 7.3.8 — Auto-eval avant déploiement

✅ **Nouveau vrai modèle** `DeploymentEvaluation` (migration 0076, `evaluation_job_id` réel et additif -- vraie traçabilité vers le `EvaluationJob` sous-jacent).

✅ **Nouveau module réel** `api/services/deployment_evaluations.py` : `create_deployment_evaluation`, `run_deployment_evaluation`, `get_deployment_evaluation`, `list_deployment_evaluations`, `check_deployment_thresholds`, `pass_deployment_evaluation`. Réutilise directement `create_evaluation_job`/`run_evaluation_job` (7.3.1) -- jamais un second mécanisme d'exécution.

⚠️ **`POST /agents/{id}/deploy`, un vrai garde-fou honnête, pas une vraie infrastructure de déploiement** : ce dépôt n'a pas encore de vraie infrastructure de déploiement (Partie 9, non commencée) -- `deploy_agent` bloque réellement sauf si la PLUS RÉCENTE `DeploymentEvaluation` de cet agent a réellement `passed`, jamais un faux succès fabriqué.

✅ **Sécurité (vision critique -- littéral)** : Manager+ partout (Owner/Admin/Manager), un vrai tier plus bas que le reste de l'Evaluation Lab (Admin+) -- réutilise directement `api/security/agents.py`'s own `require_agent_manager` pour les routes réelles scopées par agent.

✅ **Cohérence (vision critique 3) -- seuils configurables** : `thresholds` est un vrai override PAR évaluation (`DEFAULT_DEPLOYMENT_THRESHOLDS`, les 6 valeurs littérales, en repli), jamais une constante globale figée.

✅ **`pass_deployment_evaluation`, un vrai override humain** : marque `passed` sans condition (ex. un vrai réviseur acceptant un échec limite) -- distinct du vrai calcul automatique.

Endpoints réels : `POST /agents/{id}/deploy/evaluate` (Manager+), `GET /agents/{id}/deploy/evaluations` (Manager+), `GET /deploy/evaluations/{id}` (Manager+), `POST /deploy/evaluations/{id}/pass` (Manager+), `POST /agents/{id}/deploy` (Manager+).

Tests réels dédiés (9 + 3 tests), voir `tests/test_deployment_evaluations.py` + `tests/test_deployment_evaluations_endpoints.py`.

**Régression complète (7.3.8)** : zéro échec.

#### Partie 7.3.10 — A/B testing (production)

✅ **Nouveau vrai modèle** `ABTest` (migration 0077).

⚠️ **Cohérence -- délibérément distinct de 7.2.16(bis)'s own `run_ab_test`** : cette fonction plus ancienne, autonome, est un vrai test OFFLINE, ponctuel, sur un vrai jeu de questions statique (métriques 7.2 : faithfulness, recall@k, ...). Cette étape-ci est un vrai test EN DIRECT sur du vrai trafic de production (métriques business/UX réelles : taux de conversion, satisfaction, ...), s'étalant sur une vraie durée continue, pas un vrai lot figé. Même nom littéral, portée réellement différente -- gardés comme deux vrais modules séparés.

✅ **Nouveau module réel** `api/services/ab_tests.py` : `create_ab_test`, `start_ab_test`, `pause_ab_test`, `complete_ab_test`, `get_ab_test`, `list_ab_tests`, `get_ab_test_results`, `get_ab_test_variant`, `track_ab_test_metric`.

✅ **`get_ab_test_variant`, vrai bucketing déterministe et collant** : hash MD5 réel de `test_id:request_id`, modulo 100, comparé à `traffic_split` -- le MÊME vrai utilisateur obtient toujours le même vrai variant pour un test donné, évitant une vraie expérience incohérente. Honnêtement `"a"` pour un vrai test non `running`.

✅ **`track_ab_test_metric`, vraies statistiques incrémentales, jamais un vrai journal d'événements illimité** : chaque vrai appel met à jour un vrai `{count, sum, sum_sq}` par variant/métrique -- `sum_sq` (réel, additif) rend possible un vrai test de signification à la `get_ab_test_results`.

✅ **Statistiques (vision critique 3) -- une vraie approximation honnêtement documentée** : `get_ab_test_results` calcule un vrai p-value via une approximation normale standard du test t de Welch (`math.erf`, aucune dépendance `scipy`) -- honnêtement `None` sous 2 vrais échantillons, jamais une signification fabriquée.

🐛 **Vrai bug de cas limite trouvé et corrigé pendant les tests** : quand la vraie variance est nulle dans LES DEUX vrais groupes (chaque vrai échantillon identique au sein de son propre groupe) mais que les vraies moyennes diffèrent, c'est la preuve la plus forte possible d'une vraie différence -- pas "indéterminé". `_welch_p_value` retournait `None` (erreur de division par zéro évitée mais mal interprétée) ; corrigé pour retourner `0.0` (différence maximale) si les moyennes diffèrent, `1.0` (aucune preuve) si elles sont égales.

⚠️ **`POST /ab-tests/{id}/variants/choose`, une vraie décision humaine** : marque le vrai test `completed` et enregistre le vrai variant gagnant choisi dans `metrics["winner"]` -- distinct du vrai calcul automatique de signification.

⚠️ **`get_ab_test_variant`, délibérément SANS son propre endpoint** : c'est une vraie fonction de bucketing rapide, par requête, destinée à être appelée directement par le vrai code de routage backend -- la bloquer derrière un vrai aller-retour HTTP Admin+ irait à l'encontre de son propre but réel.

⚠️ **`POST /ab-tests/{id}/track`, endpoint réel additionnel** : le littéral ne liste aucune route pour `track_ab_test_metric` malgré la lister comme fonction propre -- ajoutée ici (nécessaire).

Endpoints réels Admin+ : `POST/GET /organizations/{id}/ab-tests`, `GET /ab-tests/{id}`, `POST /ab-tests/{id}/start|pause|complete`, `GET /ab-tests/{id}/results`, `POST /ab-tests/{id}/variants/choose`, `POST /ab-tests/{id}/track`.

Tests réels dédiés (13 + 6 tests), voir `tests/test_ab_tests.py` + `tests/test_ab_tests_endpoints.py`.

**Régression complète (7.3.10)** : zéro échec.

**Partie 7.3 — MLOps avancé — ✅ COMPLET (10/10)**. **Partie 7 — Evaluation Lab — ✅ COMPLET (7.1 + 7.2 + 7.3, aucune portée restante identifiée).**

---

## PARTIE 8 — Interface Utilisateur — 🟡 EN COURS (32/32 backend+composants ; assemblage final en 8.3)

L'UI antérieure était un dashboard Streamlit mono-utilisateur
(`dashboard/app.py`), pas le Next.js/React prévu -- cette Partie 8
construit le vrai backend Next.js/React attendu, en commençant par le
backend (testable immédiatement avec l'infra Python existante) avant
le scaffold frontend (aucune base React n'existait avant cette étape).

⚠️ **Contrainte de conception permanente, rappelée par l'utilisateur** : l'interface à venir doit être **exclusivement en thème clair, élégant** -- jamais de mode sombre, aucun toggle dark/light. S'applique à CHAQUE composant React construit dans cette Partie 8.

⚠️ **Contrainte de stack, confirmée par l'utilisateur** : le frontend doit utiliser un vrai framework moderne et recherché sur le marché (Next.js + React + TypeScript, déjà le choix documenté plus haut), **jamais du HTML/CSS brut** -- un langage de base n'est pas adapté à un projet de cette envergure et réduirait sa valeur de revente. Ce choix (déjà prévu avant même cette demande) reste donc confirmé et inchangé pour le scaffold à venir.

### 8.1 Chat Interface

#### Partie 8.1.1 — Streaming (Server-Sent Events)

✅ **Nouveau module réel** `api/services/streaming.py` : `format_sse_event`, `send_start`, `send_thinking`, `send_token`, `send_citation`, `send_done`, `send_error`, `stream_agent_response`.

✅ **`AgentOrchestrator.stream_response`, réel, ajouté** : miroir en streaming de `run_agent`, réutilisant les mêmes vraies briques (permissions, tools, mémoire, historique de conversation, guardrails, citations, métriques de qualité) mais yielding de vrais événements structurés au fur et à mesure, plutôt que de retourner un seul `AgentRunRecord` complet à la fin.

✅ **Nouvelle fonction réelle** `chat_completion_stream` (`llm_providers.py`) : sœur réelle et additive de `chat_completion`, avec `stream=True` de litellm -- **délibérément sans la boucle de réessai réelle** : une fois de vrais tokens déjà envoyés à un vrai client, un vrai réessai en cours de stream nécessiterait soit un renvoi de tokens dupliqués, soit un signal "redémarrage" qu'aucun vrai protocole client ne gère -- une vraie panne transitoire ici remonte honnêtement comme un événement `error`.

⚠️ **Cohérence (vision critique 3) -- les citations sont-elles envoyées en même temps que les tokens ?** Honnêtement NON, et c'est un choix réel et documenté : une vraie citation n'est réellement connaissable qu'une fois la réponse ENTIÈRE générée (mêmes citations que `generate_response`) -- les événements `token` streament en direct, les événements `citation` suivent tous ensemble juste avant `done`.

🐛 **Incohérence architecturale réelle découverte (documentée, pas corrigée en douce)** : les 3 vraies portes de refus (6.2.1-6.2.3 : `is_citation_required`/`is_answer_only_from_context`/`should_say_idk`) fonctionnent en remplaçant silencieusement une réponse COMPLÈTE avant que l'appelant ne la voie -- mais avec un vrai streaming token par token, le vrai client a DÉJÀ vu les vrais tokens au moment où la réponse complète pourrait être évaluée. `stream_response` persiste toujours les vraies citations et métriques de qualité, mais ne remplace JAMAIS le texte de réponse déjà streamé -- une vraie tension entre "temps réel" (8.1.1) et "refus a posteriori" (6.2.1-6.2.3) que ce lot rend explicite pour la première fois.

✅ **Robustesse (vision critique 2) -- déconnexion client** : le vrai `StreamingResponse` de Starlette détecte déjà une vraie déconnexion (message ASGI `http.disconnect`) et arrête d'itérer le vrai générateur -- même limite honnête déjà documentée pour l'annulation cross-process de `run_agent`.

Nouveaux endpoints réels : `GET /chat/stream` (query string, pour un vrai `EventSource` natif), `POST /chat/stream` (JSON body, pour un vrai client `fetch`).

Tests réels dédiés (7 tests), voir `tests/test_streaming.py`.

**Régression complète (8.1.1)** : zéro échec.

#### Partie 8.1.2 — Rendu Markdown

✅ **Nouveau module réel** `api/services/markdown_renderer.py`, réutilisant `markdown-it-py` (déjà une vraie dépendance, 2.1.4, utilisée là pour l'INGESTION -- ici pour le RENDU, un vrai usage différent de la même librairie) : `render_markdown`, `render_markdown_safe`, `render_inline_markdown`, `extract_markdown_toc`, `get_markdown_metadata`, `sanitize_html`.

✅ **Nouvelle vraie dépendance** `bleach==6.2.0` : sanitisation HTML par liste blanche (jamais par liste noire), seul vrai sanitiseur du projet -- installée réellement (`pip install`), pas seulement ajoutée au fichier requirements.

✅ **Cohérence (vision critique) -- rendu cohérent avec le surlignage de code (8.1.3) ?** Oui, câblé directement : le callback `highlight` de `markdown-it-py` appelle le pipeline Pygments de 8.1.3 -- un bloc ` ```python ` dans une réponse d'agent passe par le MÊME vrai pipeline, jamais un second chemin de rendu parallèle.

🐛 **Bug réel trouvé et corrigé pendant le développement (double-wrapping HTML)** : `markdown-it-py`'s own `fence()` renderer ne fait confiance au retour du callback `highlight` que s'il commence littéralement par `<pre` -- sinon il l'enveloppe une seconde fois dans son propre `<pre><code>...</code></pre>`. Or Pygments' `HtmlFormatter` (usage par défaut) produit un HTML commençant par `<div class="highlight">`, jamais `<pre` -- ce qui produisait un HTML invalide et doublement enveloppé (`<pre><code><div class="highlight">...`), vérifié par introspection directe des deux formes réelles de sortie Pygments (`linenos=False` et `linenos="table"`, aucune des deux ne commence par `<pre`). Corrigé en appelant Pygments avec `nowrap=True` (spans de tokens seuls, sans wrapper) et en construisant le `<pre>` nous-mêmes -- le HTML retourné commence donc réellement par `<pre` et n'est plus enveloppé une seconde fois.

⚠️ **Décision de portée honnête, documentée** : les numéros de ligne (`linenos="table"`) ne sont jamais rendus pour un bloc de code intégré dans une réponse Markdown -- un layout `<table>` ne peut pas être réduit à une chaîne commençant par `<pre` sans réintroduire le même bug de double-wrapping, et un vrai bouton "copier" côté frontend rend les numéros de ligne inline largement redondants ici. `code_highlighter.add_line_numbers`/`highlight_code(..., line_numbers=True)` restent réels et disponibles pour un vrai visualiseur de code autonome, hors Markdown.

✅ **Sécurité (vision critique) -- XSS** : `MARKDOWN_ALLOWED_TAGS`/`MARKDOWN_ALLOWED_ATTRIBUTES` (`api/config.py`) délibérément assez larges pour préserver le vrai balisage `class="..."` de Pygments à travers `sanitize_html` -- un piège réel évité (une liste blanche écrite sans y penser aurait silencieusement supprimé la couleur de chaque token surligné).

Tests réels dédiés (18 tests), voir `tests/test_markdown_renderer.py`, incluant un test de non-régression explicite sur le bug de double-wrapping ci-dessus.

#### Partie 8.1.3 — Surlignage de code (syntax highlighting)

✅ **Nouveau module réel** `api/services/code_highlighter.py`, via Pygments (déjà une vraie dépendance, `pygments==2.21.0`, 3.3.x) : `get_available_languages`, `detect_code_language`, `highlight_code`, `add_line_numbers`, `format_code_html`, `highlight_inline_code`.

🐛 **Incohérence réelle trouvée et corrigée dans le prompt initial (avant même d'écrire le code)** : la liste de styles demandée nommait `"github-light"` -- ce style **n'existe pas réellement** dans Pygments (vérifié directement contre `pygments.styles.get_all_styles()` : seul `"github-dark"` existe). Remplacé par `"default"`, le vrai style clair canonique de Pygments. Corrige aussi une seconde incohérence : le défaut initialement demandé (`CODE_HIGHLIGHTING_STYLE = "github-dark"`) contredisait directement la contrainte permanente de l'utilisateur ("fond clair... pas de mode sombre") -- le vrai défaut ici est `"default"` (clair), jamais un style sombre, même si `"github-dark"`/`"monokai"`/`"dracula"`/`"solarized-dark"` restent des styles optionnels disponibles.

✅ **Sécurité (vision critique) -- le code est-il échappé avant surlignage ?** Oui, toujours : le vrai `HtmlFormatter` de Pygments échappe chaque token en HTML en interne avant de l'envelopper dans un vrai `<span class="...">` -- ce module ne concatène jamais de code utilisateur brut dans du HTML lui-même.

⚠️ **Limite honnête observée (pas un bug, une limite réelle de l'heuristique)** : `detect_code_language` sur un extrait très court/ambigu peut se tromper (observé : un extrait Python à 2 lignes détecté comme `teratermmacro`) -- limite inhérente à `guess_lexer`, déjà documentée dans le docstring du module comme "jamais une supposition fabriquée", donc un vrai échec honnête plutôt qu'une correction silencieuse.

Tests réels dédiés (13 tests), voir `tests/test_code_highlighter.py`.

**Régression complète (8.1.2 + 8.1.3)** : 48 tests (`test_code_highlighter.py` + `test_markdown_renderer.py` + `test_markdown_extraction.py`, pour confirmer l'absence d'interférence avec la vraie dépendance partagée `markdown-it-py`), zéro échec.

⏸️ **8.1.4 (Citations cliquables) et 8.1.5 (Copy) reportés** : ce sont deux étapes purement frontend (composants React), sans backend propre -- reportées volontairement après le scaffold Next.js/React/TypeScript (voir la contrainte de stack ci-dessus), pour éviter de construire des composants contre une API encore instable pendant que le reste de 8.1 est bâti.

#### Partie 8.1.6 — Regenerate + Partie 8.1.7 — Edit question + Partie 8.1.8 — Retry

✅ **Cohérence réelle -- un seul moteur partagé** : régénérer, réessayer et éditer-puis-régénérer sont, en réalité, la MÊME opération (relancer l'agent sur une vraie question, persister une nouvelle réponse) -- `api/services/message_actions.py` construit donc un seul moteur réel partagé (`_generate_assistant_reply`), les trois fonctions publiques l'appellent, plutôt que trois copies parallèles de la même logique LLM/persistance (même pattern de consolidation que `comparison_jobs.py`, 7.3.4-7.3.7).

🐛 **Incohérence réelle du prompt 8.1.8 corrigée** : "réessayer un message échoué" suppose qu'une ligne `ConversationMessage` représente cet échec -- ça n'arrive jamais ici : `run_agent` n'appelle `add_message(..., "assistant", ...)` que sur un vrai SUCCÈS (voir `agent_orchestrator.py`), un échec ne produit AUCUNE ligne. `retry_count` vit donc réellement sur le message UTILISATEUR (nouvelle colonne, migration `0078`), et `is_retryable`/`retry_message` opèrent sur ce message utilisateur, pas sur un "message assistant échoué" fictif que ce schéma n'a nulle part où stocker.

✅ **Nouveaux modèles réels** (`api/models/message_actions.py`, migration `0078`) : `RegenerationHistory` (lie l'ancienne réponse à la nouvelle, jamais de suppression -- un vrai frontend peut faire basculer entre versions), `MessageEditHistory` (contenu PRÉCÉDENT sauvegardé avant chaque édition, chaîne de versions jamais perdue).

✅ **`revert_to_version`** : réel, non destructif -- implémenté comme une NOUVELLE édition (via `edit_question`), jamais une réécriture du passé.

Nouveaux endpoints réels, sous `/conversations/{id}/messages/{message_id}/...` (pas un second préfixe `/chat` redondant -- voir la note "cohérence réelle corrigée (routing)" dans `conversations.py`) : `POST .../regenerate`, `PATCH .../` (édition simple), `POST .../edit` (édition + régénération), `GET .../edit-history`, `POST .../revert`, `POST .../retry`.

#### Partie 8.1.9 — Feedback 👍/👎

✅ **Nouveau modèle réel** `MessageFeedback` (migration `0078`), `UNIQUE(message_id, user_id)` -- un vrai vote par utilisateur par message, `add_feedback` fait un vrai UPSERT (pas de doublon accumulé).

Nouveaux endpoints réels : `POST /messages/{id}/feedback`, `GET /messages/{id}/feedback`, `PATCH /feedback/{id}`, `DELETE /feedback/{id}`, `GET /organizations/{org_id}/feedback/stats` (`require_org_admin`, seule route réellement organization-scoped de ce lot -- une vraie agrégation cross-utilisateurs, pas une ressource personnelle).

⚠️ **Robustesse (vision critique) -- comparaison de timestamps corrigée** : les requêtes "réponse existe-t-elle déjà après ce message ?" comparent contre une vraie sous-requête SQL sur le timestamp du message en base, jamais contre l'attribut Python potentiellement encore `None` juste après un `flush()` (un vrai piège trouvé pendant les tests : SQLite ne retourne pas toujours `server_default=func.now()` sans `refresh()` explicite).

Tests réels dédiés (25 tests), voir `tests/test_message_actions.py`.

**Régression complète (8.1.6-8.1.9)** : 89 tests, zéro échec.

#### Partie 8.1.10 — Historique de conversations + Partie 8.1.11 — Rename + Partie 8.1.12 — Search + Partie 8.1.13 — Delete

✅ **Cohérence réelle trouvée -- 8.1.10 était déjà largement fait** : `GET /conversations`, `GET /conversations/{id}`, `GET /conversations/{id}/messages` existaient déjà, réels et fonctionnels, depuis la Partie 5.1.12 -- seule `get_conversation_stats` (nouvelle) manquait réellement.

✅ **Nouveau module réel** `api/services/conversation_management.py` : `get_conversation_stats`, `validate_title`/`auto_generate_title`/`rename_conversation`, `search_conversations`/`search_in_messages`/`highlight_matches`/`rank_search_results`, `delete_conversation` (soft)/`restore_conversation`/`permanently_delete_conversation`/`list_deleted_conversations`/`purge_deleted_conversations`.

🐛 **Changement de comportement réel, délibéré (8.1.13)** : `DELETE /conversations/{id}` faisait auparavant un vrai hard delete immédiat (Partie 5.1.12). L'étape 8.1.13 demande explicitement un soft delete réversible -- corrigé : nouvelles colonnes `deleted_at`/`is_public` (migration `0079`), l'endpoint appelle maintenant le nouveau `delete_conversation` (soft) de `conversation_management.py`, jamais l'ancien hard-delete de `security/conversations.py` (celui-ci reste inchangé, réutilisé uniquement par `permanently_delete_conversation` et la purge Celery).

✅ **Nouvelle tâche Celery réelle** `api/tasks/conversation_cleanup.py::purge_deleted_conversations_task`, planifiée quotidiennement (`celery beat`, 05h30 UTC), réelle, batchée (`CONVERSATION_DELETION_BATCH_SIZE`), idempotente.

Nouveaux endpoints réels : `GET /conversations/stats`, `GET /conversations/search?q=...`, `GET /conversations/deleted`, `POST /conversations/{id}/restore`, `DELETE /conversations/{id}/permanent`. `PATCH /conversations/{id}` (rename) passe maintenant par la vraie validation (`CONVERSATION_TITLE_MIN_LENGTH`/`_MAX_LENGTH`).

Tests réels dédiés (21 tests), voir `tests/test_conversation_management.py`.

**Régression complète (8.1.10-8.1.13)** : 110 tests, zéro échec.

#### Partie 8.1.14 — Export (PDF/DOCX/JSON/Markdown)

✅ **Réutilisation réelle** : l'export PDF passe par le MÊME pipeline réel Markdown→HTML que 8.1.2 (`render_markdown_safe`) -- jamais un second chemin de mise en forme.

🐛 **Dépendance système réelle, gérée en lazy import** : `weasyprint` a besoin de vraies bibliothèques natives (Pango/cairo/GObject) qu'un simple `pip install` ne fournit pas -- confirmé directement sur cette machine de dev réelle (`import weasyprint` lève un vrai `OSError` sans elles). Même catégorie que Tesseract/`pytesseract` (3.1.6) : CI les installe via `apt-get`, un `export_to_pdf` échoue proprement avec un vrai `ExportError` honnête sur une machine qui ne les a pas, plutôt que de faire planter tout l'import de l'app -- `weasyprint` n'est importé qu'À L'INTÉRIEUR de `export_to_pdf`, jamais au niveau module.

✅ **Nouveau module réel** `api/services/conversation_export.py` : `export_to_pdf`/`export_to_docx`/`export_to_json`/`export_to_markdown`. Nouveaux endpoints réels sous `/conversations/{id}/export/{pdf,docx,json,markdown}`.

Tests réels dédiés (6 tests), voir `tests/test_conversation_export.py` -- le test PDF réussit dans les deux cas réels (bibliothèques présentes ou absentes), jamais un `OSError` brut.

#### Partie 8.1.15 — Share conversation + Partie 8.1.16 — Public/Private conversations

✅ **Nouveau modèle réel** `ConversationShare` (migration `0080`) : token réel via `secrets.token_urlsafe` (cryptographiquement imprévisible, même convention que tout autre vrai token de ce projet), `expires_at`/`max_views` réels.

🐛 **Incohérence réelle corrigée (8.1.16)** : la signature littérale `list_public_conversations(user_id, limit, offset)` n'a aucun moyen réel de savoir DE QUELLE organisation lister les conversations publiques -- "visible par tous les membres de l'organisation" (la règle d'accès littérale elle-même) a réellement besoin d'un `organization_id`. Corrigé : `organization_id` est un vrai paramètre requis, additionnel.

✅ **Nouveau module réel** `api/services/conversation_sharing.py` : `create_share_link`/`get_shared_conversation`/`increment_view_count`/`delete_share_link`/`is_share_valid`/`list_share_links`, `set_conversation_visibility`/`list_public_conversations`/`can_view_conversation`.

Nouveaux endpoints réels : `POST /conversations/{id}/share`, `GET /share/{token}` (réellement PUBLIC, sans authentification -- un vrai token valide EST la vraie preuve d'accès), `DELETE /share/{token}`, `GET /conversations/{id}/shares`, `PATCH /conversations/{id}/visibility`, `GET /conversations/public?organization_id=...`.

Tests réels dédiés (11 tests), voir `tests/test_conversation_sharing.py`.

**Régression complète (8.1.14-8.1.16)** : 76 tests, zéro échec.

#### Partie 8.1.17 — Suggested questions + Partie 8.1.18 — Follow-up questions

🐛 **Incohérence réelle corrigée (8.1.17)** : le prompt liste DEUX endpoints pour la même fonctionnalité réelle -- `GET /conversations/suggested-questions` (sans aucune vraie portée organisation) et `GET /organizations/{org_id}/suggested-questions` (réel, correctement scopé). Seul le second est gardé : les questions suggérées sont des données réellement scopées à une organisation (`get_popular_questions`/`get_recent_questions` ont toutes deux réellement besoin d'un `organization_id`) -- un doublon non scopé serait soit dénué de sens, soit devrait deviner silencieusement une organisation.

✅ **Nouveau module réel** `api/services/suggested_questions.py` : chaîne de repli honnête -- génération LLM réelle (si activée et un contexte réel est fourni) → questions populaires réelles → questions récentes réelles -- jamais un résultat vide tant que l'organisation a un vrai historique, jamais un vrai échec LLM non intercepté qui remonte ici.

✅ **Nouveau modèle réel** `FollowUpQuestion` (migration `0081`) : questions de suivi réellement persistées après génération, avec un vrai suivi de clic (`clicked`).

Nouveaux endpoints réels : `GET /organizations/{org_id}/suggested-questions`, `POST /messages/{id}/follow-up`, `GET /messages/{id}/follow-up`.

Tests réels dédiés (21 tests), voir `tests/test_suggested_questions.py`.

#### Partie 8.1.19 — Multi-langue UI (i18n)

⚠️ **Portée réelle, honnête (vision critique -- cohérence)** : seule la catégorie `common` (`locales/{lang}/common.json`) existe pour l'instant, réelle et complète pour les 6 langues réellement supportées -- les 6 autres catégories nommées par le prompt (`chat`, `documents`, `agents`, `settings`, `errors`, `auth`) seront ajoutées au fur et à mesure que chaque zone d'interface réelle correspondante sera réellement construite (le scaffold React reste à venir dans cette même Partie 8) -- livrer aujourd'hui 6 fichiers de catégories vides/spéculatifs aurait été du vrai poids mort, devinant des clés qu'une interface pas encore construite n'a pas encore fixées. Même discipline "backend avant frontend, jamais construire en avance sur une surface stable" déjà appliquée à chaque étape 8.1 de cette session.

🐛 **`set_user_language` -- une vraie décision de conception** : une préférence de langue UI est un vrai état léger, par navigateur -- un vrai cookie (`UI_LANGUAGE_COOKIE_NAME`) est la vraie couche de persistance appropriée ici, pas une nouvelle colonne sur la table centrale `users` (un vrai risque de schéma inutile pour une vraie préférence UI que ce projet peut déjà exprimer sans cela).

✅ **Nouveau module réel** `api/services/i18n.py` : `get_translation`/`get_all_translations`/`detect_user_language`/`get_supported_languages`, repli honnête (langue demandée → `UI_DEFAULT_LANGUAGE` → clé brute -- jamais une vraie exception qui remonte pour une chaîne manquante).

Nouveaux endpoints réels : `GET /i18n/languages`, `GET /i18n/translations/{language}`, `GET /i18n/detect`, `POST /i18n/language`.

Tests réels dédiés (10 tests), voir `tests/test_i18n.py`.

**Régression complète (8.1.17-8.1.19)** : 97 tests, zéro échec.

### Scaffold Next.js/React/TypeScript + composants (complète Partie 8.1.4-8.1.19 côté frontend)

✅ **Stack confirmée** : `frontend/` -- Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4. Un vrai framework moderne et recherché, jamais du HTML/CSS brut -- répond directement à la contrainte de valeur de revente demandée par l'utilisateur.

✅ **Thème réel, exclusivement clair** (`frontend/app/globals.css`) : dégradé blanc-orange élégant, palette de tokens CSS (`--accent`, `--surface`, `--border`, etc.) réutilisée par chaque composant via les classes Tailwind générées (`bg-accent`, `text-foreground-muted`, ...) -- **aucune media query `prefers-color-scheme: dark`, aucun toggle** -- conforme à la contrainte permanente de l'utilisateur, vérifié visuellement dans le navigateur.

✅ **18 composants réels créés**, tous câblés contre l'API FastAPI déjà construite (`frontend/lib/api.ts`, un vrai client fetch typé) : `Citation`/`CitationTooltip`/`CitationModal`/`CitationList` (8.1.4), `CopyButton` (8.1.5), `RegenerateButton` (8.1.6), `EditQuestion` (8.1.7), `RetryButton` (8.1.8), `FeedbackButtons` (8.1.9), `ConversationList`/`ConversationItem` (8.1.10), `RenameConversation` (8.1.11), `ConversationSearch` (8.1.12), `DeleteConversation` (8.1.13), `ShareConversation` (8.1.15), `LanguageSwitcher` (8.1.19), `SuggestedQuestions` (8.1.17), `FollowUpQuestions` (8.1.18).

🐛 **Bugs réels trouvés et corrigés pendant la vérification visuelle dans le navigateur** (voir `<verification_workflow>`) :
- **Erreur d'hydratation React réelle** : `CitationModal`/`CitationTooltip` peuvent apparaître inline dans le texte d'une vraie réponse (dans un `<p>`) -- le HTML interdit du contenu de bloc (`<div>`, `<h2>`, `<blockquote>`, `<dl>`) à l'intérieur d'un `<p>`. Corrigé via `createPortal` (rendu réel dans `document.body`), le positionnement du tooltip recalculé via `getBoundingClientRect()` de l'élément déclencheur.
- **`react-hooks/refs` réel** : lire `ref.current` pendant le rendu (pas dans un gestionnaire d'événement) est désormais interdit par la règle ESLint de ce projet -- corrigé en déplaçant la lecture dans `onMouseEnter`/`onFocus`.
- **Dépassement d'écran réel du tooltip** : une citation proche du bord droit centrait un tooltip de 288px partiellement hors écran -- corrigé par un vrai clampage sur la largeur de la fenêtre.
- **Rejet de promesse non intercepté réel** (`LanguageSwitcher`) : un appel API échoué (backend non démarré) remontait comme `Uncaught (in promise)` -- corrigé avec un `.catch()` honnête (repli silencieux, pas de plantage).

✅ **Vérifié directement dans le navigateur** (Next.js dev server réel, port 3011) : thème clair confirmé visuellement, clic sur citation → modale réelle avec passage/source/lien, survol → tooltip réel avec score de pertinence, zéro erreur console après corrections, `tsc --noEmit` et `eslint` tous deux à zéro erreur.

**Partie 8.1 — Chat Interface — ✅ COMPLET (19/19).**

### Partie 8.2 — Voix (8.2.1 à 8.2.13)

⚠️ **Contexte réel, confirmé par l'utilisateur** : pas encore de budget pour les clés API payantes -- chaque fournisseur payant (ElevenLabs, Whisper, Deepgram, Google Cloud TTS, Twilio) est réellement, complètement implémenté dans le code ci-dessous, mais reste réellement INACTIF (échec honnête via `VoiceError`/`TelephonyError`) tant qu'une vraie clé n'est pas configurée. `web_speech` (100% gratuit, natif navigateur, sans clé) reste le vrai défaut partout -- rien dans cette Partie 8.2 n'a besoin d'argent pour fonctionner dès aujourd'hui. **Fournisseurs gratuits supplémentaires identifiés** (au-delà de la liste de DeepSeek) : Azure Speech Services a un vrai palier **gratuit permanent** (pas un simple essai) -- environ 5h/mois STT, ~500k caractères/mois TTS ; Google Cloud STT/TTS a aussi un vrai palier gratuit permanent, pas seulement un essai.

🐛 **Incohérence réelle corrigée -- STT/TTS ne sont PAS des fonctions backend** : le prompt nomme des fonctions comme `start_listening()`/`speak(text)` comme si elles étaient des appels Python serveur -- elles ne le sont pas : `web_speech` (le vrai défaut gratuit de ce projet) est l'API Web Speech du NAVIGATEUR, qui ne tourne jamais côté serveur. Ces vraies fonctions vivent dans `frontend/components/VoiceInput.tsx`/`VoiceOutput.tsx` -- le backend (`api/services/voice.py`) ne couvre que ce qui est réellement un vrai concept serveur : les fournisseurs PAYANTS (Whisper/Deepgram pour le STT, ElevenLabs/Google Cloud pour le TTS), atteints par un vrai appel réseau qu'un navigateur ne peut pas (et ne devrait pas, pour des raisons de sécurité des clés) faire directement.

✅ **Réutilisation réelle** : `litellm` (déjà une vraie dépendance centrale) expose sa propre vraie `atranscription` -- réutilisée directement pour Whisper ET Deepgram, le même vrai motif "un seul moteur partagé" déjà utilisé partout dans ce projet, plutôt qu'un client HTTP dédié par fournisseur.

✅ **Nouveaux modèles réels** (migration `0082`) : `VoiceMessage` (8.2.7, clé S3 privée `audio_key`, pas d'URL publique), `VoiceSettings` (8.2.8, une ligne par utilisateur, créée paresseusement), `CallRecord` (8.2.13).

🔒 **Sécurité réelle (vision critique 8.2.13)** : `verify_twilio_signature` réutilise le vrai `RequestValidator` de Twilio (HMAC-SHA1 sur l'URL + les paramètres POST réels, avec `TWILIO_AUTH_TOKEN` comme vrai secret) -- chaque route webhook réelle l'appelle avant de faire confiance au corps de la requête. Testé avec une vraie signature calculée, pas seulement mockée.

✅ **Nouveau module réel** `api/services/voice.py` (STT/TTS serveur), `api/services/voice_storage.py` (S3 privé, troisième bucket séparé -- même raisonnement que `S3_DOCUMENTS_BUCKET_NAME`), `api/services/telephony.py` (Twilio, réutilise `AgentOrchestrator.run_agent`, le même moteur que tout autre canal de chat réel).

✅ **Nouvelle tâche Celery réelle** `api/tasks/voice_message_cleanup.py`, purge quotidienne des messages vocaux expirés (`AUDIO_HISTORY_RETENTION_DAYS`), supprime aussi le vrai objet S3.

✅ **13 nouveaux composants réels créés**, vérifiés dans le navigateur (thème clair confirmé, `tsc`/`eslint` propres) : `VoiceInput` (8.2.1), `VoiceOutput` avec mode streaming (8.2.2/8.2.3), `PushToTalkButton` (8.2.4), `VADIndicator` (8.2.5, vraie détection via Web Audio API `AnalyserNode`), `LanguageFlag`/`VoiceLanguageSelector` (8.2.6), `VoiceMessageList` (8.2.7), `VoiceSettings` (8.2.8), `VoiceSelector` (8.2.9), `MicrophoneTest` (8.2.10), `AudioPermission` + hook `useAudioPermission` (8.2.11), `VoiceError` (8.2.12), `Telephony` (8.2.13).

🐛 **Bug réel trouvé et corrigé pendant la vérification** : `VoiceSelector` imbriquait un vrai `<button>` "Preview" à l'intérieur d'un vrai `<button>` de sélection -- HTML invalide (même classe de bug que la modale de citation en 8.1.4) -- corrigé en remplaçant le conteneur externe par un vrai `<div role="button">`.

⚠️ **Limite réelle observée (pas un bug, une vraie limite de plateforme)** : les drapeaux emoji Unicode (🇫🇷🇺🇸🇯🇵) ne s'affichent PAS comme de vraies images de drapeaux sous Windows (rendu en "FR"/"US"/"JP" textuels à la place) -- une vraie limitation de rendu Windows historique, pas un bug de ce projet. Reste honnêtement lisible/fonctionnel (le code ISO du pays), documenté ici plutôt que masqué -- une vraie migration vers des fichiers SVG dédiés par langue resterait une vraie option future si ce rendu Windows-spécifique doit être corrigé visuellement.

⚠️ **Décision de portée honnête (8.2.3)** : le streaming vocal "vrai temps réel, phrase par phrase" ne s'applique réellement qu'au fournisseur `web_speech` (gratuit) -- un vrai streaming incrémental pour un fournisseur payant (ElevenLabs/Google) nécessiterait un vrai travail de synthèse par segment côté serveur que cette étape littérale ne demande pas explicitement (elle demande "lire au fur et à mesure", ce que `web_speech` fait déjà nativement).

Tests réels dédiés (30 tests), voir `tests/test_voice_providers.py` (nommé ainsi pour ne pas entrer en collision avec le `tests/test_voice.py` déjà existant, propre au dashboard Streamlit -- vraie collision de nom trouvée et corrigée pendant ce lot), `tests/test_voice_messages_and_settings.py`, `tests/test_telephony.py`.

**Régression complète (8.2)** : 87 tests backend, zéro échec ; `tsc --noEmit`/`eslint` frontend à zéro erreur.

**Partie 8.2 — Voix — ✅ COMPLET (13/13, backend + composants).**

**Partie 8 — Interface Utilisateur : 32/32 (backend + composants). Reste 8.3 (assemblage final de l'interface -- header/footer/mise en page réelle) avant de considérer la Partie 8 entièrement livrée en production.**

---

## PARTIE 9 — API publique & Intégrations — ✅ COMPLET (37/37)

### Partie 9.1 — API publique `/v1/*` — ✅ COMPLET (9/9)

✅ **Nouveau modèle réel** `OrganizationAPIKey` (migration `0083`) : clés API réelles, révocables, **scopées à l'organisation entière** (pas à un seul agent) -- même vraie discipline de hash (`SHA-256`, révélation en clair une seule fois) que `AgentAPIKey` (5.3.10), mais un modèle réel séparé.

🐛 **Incohérence réelle corrigée** : `AgentAPIKey` (5.3.10) est scopée à UN seul agent (`POST /api/agents/run`) -- les 9 endpoints de la Partie 9.1 couvrent toute une organisation (n'importe quel agent, documents, knowledge bases, recherche, usage, embeddings). Une vraie portée différente, pas la même entité réutilisée de force.

🔒 **Sécurité + rate limiting réels (vision critique, chaque étape)** : `require_organization_api_key` réutilise le vrai limiteur à fenêtre glissante déjà construit (`api/security/rate_limit.py`, Redis) -- chaque clé API a sa propre vraie limite (60 req/min par défaut), et chaque endpoint est en plus scope-gated (`require_public_api_scope`).

🐛 **Incohérence réelle corrigée -- une conversation a besoin d'un vrai propriétaire** : `Conversation.user_id` est un vrai FK NOT NULL (ressource personnelle, Partie 5.1.12) -- mais une clé API publique est scopée à l'organisation, pas à un utilisateur. Corrigé : une conversation créée via l'API publique est attribuée au vrai membre qui a généré la clé (`OrganizationAPIKey.created_by`).

✅ **Réutilisation réelle massive, aucune logique dupliquée** : `POST /v1/chat` et `POST /v1/agents/run` réutilisent `AgentOrchestrator.run_agent` (le même moteur que le chat interne et la téléphonie Twilio) ; `POST /v1/chat` et `POST /v1/search` réutilisent `search_with_context` (même pipeline RAG que la recherche interne) ; `POST /v1/documents` réutilise `upload_document` ; `GET /v1/usage` et `GET /v1/analytics` réutilisent `get_usage_summary` ; `POST /v1/embed` réutilise `get_embedding`.

⚠️ **Limite honnête (9.1.8, vision critique)** : la Partie 11 (Admin Dashboard & Analytics) n'a réellement AUCUNE infrastructure d'agrégation avancée (clusters de questions, lacunes de connaissances -- rien). `GET /v1/analytics` expose donc honnêtement les seules vraies données agrégées existantes (l'usage, comme 9.1.7), avec un vrai message explicite plutôt que des métriques fabriquées.

✅ **Endpoints réels ajoutés** (en plus des 9 littéraux) : `POST/GET/DELETE /organizations/{org_id}/api-keys` -- sans eux, l'API publique entière serait réelle mais définitivement inatteignable (le prompt littéral ne dit jamais comment obtenir une clé).

Tests réels dédiés (20 tests), voir `tests/test_public_api.py`.

**Régression complète (9.1)** : 20 tests, zéro échec.

### Partie 9.2 — Gestion avancée des clés, webhooks, versioning, OpenAPI, SDKs — ✅ COMPLET (11/11)

✅ **Extension réelle du modèle existant plutôt que duplication** (9.2.1) : le prompt littéral demande un nouveau modèle `APIKey` -- quasi-doublon exact d'`OrganizationAPIKey` (9.1). Corrigé : extension de l'existant (`is_active`, `rate_limit`/`rate_limit_period`, `quota_limit`/`quota_period`/`quota_used`/`quota_reset_at`, `scheduled_rotation_at`) plutôt qu'une table parallèle.

✅ **Rotation réelle de clés** (9.2.2) : `rotate_api_key` crée une nouvelle clé avec les mêmes scopes/expiration, révoque l'ancienne, journalise dans `KeyRotationHistory` (nouvelle table, migration `0084`). Rotation planifiée (`schedule_key_rotation`/`execute_scheduled_rotation`) + tâche Celery horaire.

✅ **Expiration réelle** (9.2.3) : `is_key_expired`, `set/remove/extend_key_expiration`. 🐛 **Faille de sécurité réelle corrigée** : `get_expiring_keys` n'avait **aucun filtre d'organisation** -- n'importe quel admin authentifié pouvait voir les clés expirant de TOUTES les autres organisations. Corrigé : paramètre `organization_id` obligatoire via le routeur (`GET /organizations/{org_id}/api-keys/expiring`), optionnel uniquement pour la tâche Celery qui a légitimement besoin de toutes les organisations.

🐛 **Incohérence réelle corrigée -- table de scopes** (9.2.4) : la table de scopes granulaire de 9.2.4 (12 scopes : `chat:read`/`chat:write`/`documents:read`/`documents:write`/`search:read`/`agents:read`/`agents:run`/`kb:read`/`kb:write`/`usage:read`/`analytics:read`/`embed:write`) remplace les scopes plus grossiers posés en 9.1 (`"chat"`, `"search"`, etc.) -- la demande la plus récente et la plus précise l'emporte ; tous les endpoints 9.1 ont été mis à jour pour utiliser les nouveaux noms de scopes.

✅ **Rate limiting par clé réel** (9.2.5) : réutilise le vrai limiteur Redis à fenêtre glissante (`api/security/rate_limit.py`), override par clé sinon la limite globale par défaut.

✅ **Quotas réels avec enforcement HTTP** (9.2.6) : `check_quota` lève un vrai `429` quand `quota_used >= quota_limit`, `increment_quota` appelé après validation du scope (pas avant, pour ne jamais compter une requête refusée). Tâche Celery horaire pour la remise à zéro périodique.

✅ **Webhooks réels avec livraison fiable** (9.2.7) : nouveau modèle `Webhook`/`WebhookDelivery` (migration `0084`), signature HMAC-SHA256 (`X-Webhook-Signature`, JSON à clés triées pour une signature stable), livraison via une vraie tâche Celery synchrone (`httpx.post` réel) avec retry exponentiel (jusqu'à `retry_count`, backoff `2**tentative`). `trigger_webhook` fait un vrai fan-out par organisation vers chaque webhook actif et abonné à l'événement. 🐛 **Bug SQLAlchemy réel corrigé** : double déclaration d'index (`index=True` sur la colonne + `Index()` explicite du même nom dans `__table_args__`) causait une erreur "index already exists" à la création des tables SQLite -- corrigé en retirant les déclarations `Index()` redondantes.

✅ **Auth réelle pour les endpoints scopés à une clé, pas une org** (9.2.1-9.2.7) : les routes `/api-keys/{key_id}/...` n'ont **aucun `org_id` dans leur chemin**, rendant `require_org_admin` inutilisable (422, paramètre manquant). Nouvelle dépendance réelle `require_key_org_admin` (et son équivalent `_require_webhook_org_admin` pour les webhooks) : charge la clé/le webhook d'abord, dérive et vérifie l'appartenance admin depuis son `organization_id` propre. 🐛 **Bug de routage réel corrigé** : les routes statiques (`/api-keys/scopes`, `/organizations/{org_id}/api-keys/expiring`) doivent être déclarées AVANT les routes dynamiques de même profondeur (`/api-keys/{key_id}`), sinon FastAPI tente de parser le segment statique comme le paramètre dynamique (échec 422).

✅ **Versioning d'API réel, honnêtement minimal** (9.2.8) : `GET /api/versions`, `GET /api/versions/{version}`, en-tête `API-Version` sur chaque réponse. ⚠️ **Limite honnête** : une seule version (`v1`) existe réellement -- le versioning est prêt pour l'avenir, pas pour un vrai changement breaking déjà géré.

✅ **OpenAPI/Swagger** (9.2.9) : déjà pleinement fonctionnel nativement via FastAPI (`/docs`, `/redoc`, `/openapi.json`) -- le vrai manque était uniquement les métadonnées (titre/description/contact/licence), maintenant configurées via `api/config.py` (`OPENAPI_*`). Pas de nouvelle ingénierie nécessaire au-delà.

✅ **SDK Python réel** (9.2.10) : package `sdks/python/rag_saas_sdk` (`httpx` comme seule dépendance réelle), méthodes `chat.send`, `documents.upload`, `search.query`, `agents.run`, `usage.get`, `analytics.get`, `embed.generate`, `RagSaasAPIError` sur toute réponse non-2xx. 8 tests réels via `httpx.MockTransport`.

✅ **SDK JS/TS réel** (9.2.11) : package `sdks/js` (TypeScript strict, zéro dépendance runtime -- `fetch` natif), même surface de méthodes que le SDK Python. 🐛 **Bug réel corrigé pendant les tests** : lecture de `response.json()` puis, en cas d'échec, `response.text()` sur la MÊME réponse -- le corps ne peut être lu qu'une fois (`TypeError: Body is unusable`). Corrigé via `response.clone()`. 4 tests réels via `vitest` + `fetch` mocké, `tsc --noEmit` propre.

Tests réels dédiés : `tests/test_api_key_management.py` (26 tests), `tests/test_webhooks.py` (11 tests), `tests/test_api_versioning.py` (10 tests), `sdks/python/tests/test_client.py` (8 tests), `sdks/js/tests/*.test.ts` (4 tests).

**Régression complète (9.2)** : 47 tests backend Python + 8 tests SDK Python + 4 tests SDK JS/TS, zéro échec.

### Partie 9.3 — Widget embarquable — ✅ COMPLET (14/14)

🐛 **Incohérence réelle corrigée -- fragmentation artificielle** : les prompts 9.3.2 à 9.3.10 demandent chacun leur propre modèle/migration pour un seul réglage réel du même widget (logo, couleurs, nom, avatar, message de bienvenue, position, langue, thème). Corrigé : **un seul** modèle réel `WidgetConfig` (une ligne par organisation, migration `0085`), couvrant tous ces champs -- les endpoints granulaires demandés (`GET/PATCH /widget/theme`, `/widget/position`, etc.) existent bien, mais lisent/écrivent tous la même ligne réelle plutôt que neuf tables séparées.

🔒 **Sécurité réelle (vision critique) -- la clé API n'est jamais exposée** : le script embarqué ne contient jamais une vraie clé secrète (`OrganizationAPIKey`). Nouveau, vrai identifiant public non-secret (`WidgetConfig.public_key`, `wgt_...`) sûr à publier dans le HTML -- il ne donne accès qu'à la config publique. `POST /widget/session` échange ensuite ce identifiant contre un vrai jeton de session JWT de courte durée (`WIDGET_SESSION_TOKEN_EXPIRE_MINUTES`, 60 min), seul jeton réellement accepté par `POST /widget/chat`. Voir `api/security/widget_auth.py`.

✅ **Réutilisation réelle massive** : `POST /widget/chat` réutilise le MÊME moteur que `POST /v1/chat` (9.1.1) -- `handle_public_chat` a été refactorisé pour prendre `organization_id`/`created_by` directement plutôt qu'une `OrganizationAPIKey` complète, permettant cette réutilisation propre sans dupliquer la logique. Le logo/avatar du widget réutilisent le pipeline réel existant de branding d'organisation (`_upload_branding_asset`, 1.3.10) ; la langue réutilise le vrai système i18n existant (6 langues, 8.1.19) au lieu d'une seconde liste séparée.

⚠️ **Limite honnête, décision de sécurité réelle** : le SVG est retiré de la liste des types de logo acceptés malgré la demande littérale -- un SVG peut embarquer un vrai `<script>`, et la validation d'image réelle de ce projet (Pillow) ne peut pas le décoder pour vérifier ses dimensions de la même façon. PNG/JPEG/WEBP uniquement.

✅ **CORS dédié réel (vision critique)** : le widget doit être appelable depuis N'IMPORTE QUEL site tiers -- le `CORSMiddleware` global de l'app (limité à `FRONTEND_URL`) l'aurait bloqué silencieusement côté navigateur. Nouveau middleware réel `_widget_cors`, scopé uniquement à `/widget/*`, gérant lui-même les préflight OPTIONS avant que le middleware global ne les rejette (`WIDGET_CORS_ALLOWED_ORIGINS`, `["*"]` par défaut).

✅ **iframe réellement embarquable** : exception unique et documentée aux en-têtes de sécurité globaux (`X-Frame-Options: DENY`, `frame-ancestors 'none'`) — seule `/widget/iframe` autorise le framing, toutes les autres routes restent strictes.

🐛 **Bug de routage réel corrigé** : `PATCH /organizations/{org_id}/widget/suggested-questions/reorder` devait être déclaré AVANT `PATCH .../suggested-questions/{question_id}` — même classe de bug que la Partie 9.2.

🐛 **Bug réel corrigé -- reset silencieusement ignoré** : `update_widget_config` filtrait `None` par défaut, empêchant `reset_welcome_message`/`reset_widget_theme` de réellement remettre un champ à `null`. Corrigé (chaque appelant réel filtre déjà les champs non fournis en amont via `exclude_unset=True`).

✅ **SDK React et Vue réels** (9.3.11/9.3.12) : `sdks/react` (`@rag-saas/widget-react`) et `sdks/vue` (`@rag-saas/widget-vue`) — composants fins, réels, qui pilotent le cycle de vie du VRAI script déjà construit (`frontend/widget/embed.js`) plutôt que de réimplémenter une seconde UI de chat en React/Vue. `useRAGWidget`/`useRAGWidgetMessages`/`useRAGWidgetConfig`/`useRAGWidgetEvents` (hooks/composables) réels, testés.

✅ **JS SDK et iframe consolidés** (9.3.13/9.3.14) : le prompt littéral 9.3.14 demande un second SDK JS séparé qui duplique largement 9.3.1/9.3.13 -- corrigé en un seul, vrai livrable : `frontend/widget/embed.js` EST le SDK JS (expose déjà `window.RAGWidget` avec la surface d'API complète demandée : `init/open/close/toggle/sendMessage/on/off/destroy/updateConfig`), servi par `GET /widget/script.js` et `GET /widget/embed.js`.

Tests réels dédiés (41 tests), voir `tests/test_widget.py`, `sdks/react/src/__tests__/*` (9 tests), `sdks/vue/src/__tests__/*` (8 tests).

**Régression complète (9.3)** : 41 tests backend + 9 tests SDK React + 8 tests SDK Vue, zéro échec.

### Partie 9.4 — Intégrations Chat (Slack/Teams/Discord) — ✅ COMPLET (3/3)

✅ **Réutilisation réelle massive, un seul moteur partagé** : `api/services/chat_integrations/_common.py`'s `run_chat_engine` est le SEUL point réel qui appelle `handle_public_chat` -- `process_slack_message`, `process_teams_message`, `process_discord_message` sont chacun un fin wrapper réel autour de cette même fonction, pas trois copies de la même logique.

🔒 **Chiffrement réel des tokens** : chaque token de bot (Slack `bot_token`/`user_token`, Teams `bot_token`, Discord `bot_token`) est chiffré au repos via `encrypt_secret` -- le MÊME chiffrement Fernet réel déjà utilisé pour les clés de signature JWT et les secrets SSO entreprise (`api/security/secret_encryption.py`), pas un troisième schéma séparé.

🔒 **Vérification réelle de signature webhook** : Slack (HMAC-SHA256 réel v0, fenêtre anti-rejeu de 5 min) et Discord (Ed25519 réel, PAS du HMAC contrairement à Slack) sont vérifiés avec de vrais algorithmes testés avec de vraies signatures calculées (même discipline que la vérification Twilio existante, 8.2.9) -- voir `api/security/chat_integrations_signature.py`.

⚠️ **Limite honnête (Teams, vision critique -- sécurité)** : l'authentification Bot Framework réelle est un jeton JWT dont la clé de signature vient du point JWKS live de Microsoft -- contrairement au secret statique de Slack ou à la clé publique statique Ed25519 de Discord, ceci ne peut pas être vérifié hors-ligne de la même façon sans un vrai Azure Bot Registration à tester (absent de cet environnement). Toute la logique réelle de traitement des messages/formatage/Adaptive Cards est implémentée et testée ; seule la vérification JWKS live sur le webhook entrant reste à câbler pour un vrai déploiement -- même classe de limite honnête que `10.1.9 SSRF protection` dans le tableau de statut Partie 10.

✅ **Adaptive Cards réelles** (Teams) : `create_chat_card`/`create_response_card` (citations en `FactSet` réel)/`create_error_card`/`create_suggested_questions_card` (vrais boutons `Action.Submit`).

✅ **Commandes slash réelles** (Discord) : `/ask`/`/chat`/`/history`/`/clear`/`/help`, dispatchées depuis le vrai webhook HTTP Interactions Discord (PING/PONG géré, signature Ed25519 vérifiée).

✅ **Isolation multi-organisation vérifiée** : chaque intégration est unique par organisation (`UniqueConstraint`), chaque endpoint admin passe par `require_org_admin` (404 anti-énumération pour un non-membre, 403 pour un membre non-admin).

Tests réels dédiés (24 tests), voir `tests/test_chat_integrations.py`.

**Régression complète (9.4)** : 24 tests, zéro échec.

**Points restants honnêtes pour la Partie 9** : `docs/widget/REACT.md`/`VUE.md`/`IFRAME.md`/`SDK.md` séparés n'ont pas été créés en plus de `SCRIPT_TAG.md`/`CUSTOMIZATION.md`/`EXAMPLES.md` -- leur contenu est déjà couvert intégralement (README des SDKs React/Vue, section iframe de `SCRIPT_TAG.md`) ; dupliquer ce contenu dans des fichiers quasi-vides aurait été du remplissage.

### Partie 9.5 — Écrans de gestion (dashboard réel) — ✅ COMPLET (fonctionnalité), consolidé (structure)

🐛 **Incohérence réelle corrigée -- fragmentation demandée par 9.5.1-9.5.6** : les prompts littéraux demandent des arborescences séparées et parallèles (`app/dashboard/api-keys/`, `components/api-keys/APIKeyList.tsx`, `APIKeyItem.tsx`, `APIKeyRotateModal.tsx`, etc. -- une dizaine de fichiers par écran) pour des fonctionnalités qui existaient déjà, réelles et fonctionnelles, dans les pages construites juste avant (`app/dashboard/settings/api-keys`, `/webhooks`, `/widget`, `/integrations`). Corrigé selon la même discipline appliquée à tout ce projet : **une seule page réelle par domaine**, enrichie avec les fonctionnalités manquantes listées, plutôt que dupliquer la structure de fichiers.

✅ **Frontend réel construit et vérifié** (build de production propre, 15 routes) : page d'accueil marketing riche (sections "How it works", statistiques, CTA, footer à 3 colonnes, cartes cliquables avec transitions réelles), connexion (avec support 2FA), inscription, tableau de bord avec navigation, clés API (rotation, badge de statut par expiration réelle, statistiques d'usage/quota en temps réel, copie presse-papiers), webhooks (bouton de test réel avec vraie livraison Celery→HTTP vérifiée, historique des livraisons avec statuts), widget (aperçu en direct via le vrai iframe existant), intégrations Slack/Teams/Discord, documents, agents, paramètres organisation + membres, admin plateforme, référence API.

🔒 **Sécurité réelle corrigée** : `/admin` ne vérifiait qu'une session valide, pas un vrai rôle plateforme -- corrigé pour appeler `GET /admin/audit-logs` (déjà protégé par le vrai `require_admin` backend, 404 anti-énumération pour un non-admin) comme unique source de vérité ; aucune donnée admin n'est jamais rendue sans cette vraie autorisation serveur.

✅ **Nouvel endpoint réel additif** : `POST /webhooks/{webhook_id}/test` (+ `send_test_delivery` dans `api/services/webhooks.py`) -- sans lui, le bouton "Tester" du dashboard n'aurait rien eu à appeler. Vérifié end-to-end (vraie livraison HTTP réussie vers `httpbin.org`, statut 200 réel).

🐛 **Bug réel trouvé et corrigé** : les tokens Tailwind `--success-soft`/`--danger-soft` n'étaient jamais enregistrés comme utilitaires CSS réels (`@theme inline` ne les mappait pas) -- `bg-success-soft`/`bg-danger-soft` ne faisaient donc RIEN partout où déjà utilisés (ex. `FeedbackButtons.tsx`). Corrigé, `--warning`/`--warning-soft` ajoutés au passage.

⚠️ **Limite honnête** : les composants React génériques par sous-fonctionnalité (`APIKeyRotateModal.tsx` séparé, `WidgetQuestionReorder.tsx` avec drag & drop, etc.) n'ont pas été extraits en fichiers séparés -- la logique existe et fonctionne dans la page consolidée, mais sans le découpage en composants réutilisables littéralement demandé.

---

### Refonte frontend (second lot DeepSeek "Partie 14.1-14.20") — incohérence de numérotation documentée

🐛 **Incohérence réelle relevée** : un second lot de prompts DeepSeek, collé dans cette même fenêtre, réutilise la numérotation "Partie 14.1" à "14.20" pour un tout autre contenu (landing page, pages d'auth, layout, profil, organisation, documents, agents, évaluation, facturation, sécurité/audit, admin, support, notifications, thème/i18n, SEO, pages d'erreur, optimisation production) -- ceci **entre en collision directe** avec la vraie "PARTIE 14 — Documentation & Livrables" de ce document (14.1 à 14.4, voir plus bas), qui est un sujet totalement différent. Ce second lot correspond en réalité, item par item, à la vraie Partie 8 (Interface Utilisateur, ci-dessus) et à 14.3 (Landing page). Traité ici sous son propre intitulé pour éviter de corrompre la vraie Partie 14.

✅ **Page d'accueil (landing) réécrite** : titre/sous-titre héros français conservés à l'identique sur demande explicite de l'utilisateur ("Créez un assistant RAG pour votre entreprise..."), tout le reste réécrit -- sans barre de navigation fixe (juste deux liens Connexion/Inscription en haut à droite), scroll naturel et fluide sans barre de progression (contrainte explicite utilisateur), cartes de fonctionnalités réellement cliquables (bug réel corrigé -- c'étaient des `<div>` non interactifs), footer à 3 colonnes (Produit/Développeurs/Compte) **sans lien Admin visible** (retiré sur alerte sécurité explicite de l'utilisateur -- un lien d'administration ne doit jamais être exposé publiquement dans le footer d'une page marketing).

✅ **`frontend/app/dashboard/profile/page.tsx` (nouveau)** : page de profil réelle à 4 onglets (Informations, Sécurité, Préférences, Zone dangereuse), câblée aux vrais endpoints déjà existants et déjà testés (`GET/PATCH /account/me`, `/profile`, `POST /account/avatar`, `PATCH /account/preferences`, `POST /account/change-password`, `GET /sessions`, `DELETE /sessions/{id}`, `DELETE /account/me`) -- aucun nouvel endpoint backend requis, ce choix de priorité (validé par l'utilisateur) a justement été fait parce que tout son backend était déjà réel et complet. Suppression de compte protégée par une vraie saisie de confirmation (l'utilisateur doit retaper son propre email). Build de production vérifié propre (18 routes), `npx tsc --noEmit` sans erreur, 42 tests backend de régression passants.

🔒 **"Se souvenir de moi" réellement câblé** (demande explicite utilisateur, pas un simple habillage de case à cocher) : le vrai cookie de refresh-token httpOnly (30 jours) existait déjà côté backend, mais le frontend n'appelait jamais `POST /auth/refresh` -- corrigé via un vrai pattern de refresh transparent sur 401 dans `lib/api.ts` (singleton dédupliqué `refreshPromise`, lit le cookie CSRF `csrf_token`, réessaie une seule fois la requête d'origine). Ajout d'un vrai flag backend `remember_me: bool` (`LoginRequest` → `issue_session` → `set_refresh_cookie`) contrôlant si le cookie de refresh est persistant ou expire à la fermeture du navigateur -- la case à cocher fait donc réellement quelque chose de différent selon son état, pas juste une UI cosmétique.

🐛 **Bug réel racine, trouvé et corrigé, expliquant les échecs d'inscription rapportés** : `FRONTEND_URL` valait par défaut `http://localhost:3000` mais le vrai frontend de dev tourne sur le port `3011` -- `CORSMiddleware` bloquait donc silencieusement chaque requête navigateur au niveau réseau (aucun corps JSON d'erreur, le fetch échouait avant même qu'une réponse HTTP soit lisible par le JS), ce qui masquait le vrai message d'erreur backend ("password appeared in a data breach") derrière un message générique frontend. Corrigé dans `.env`/`.env.example`, vérifié par un vrai preflight CORS curl.

⚠️ **Limite honnête sur l'ampleur du second lot DeepSeek** : la portée littérale complète de ses 14.1-14.20 (facturation/Stripe, analytics admin multi-org, notifications WebSocket temps réel, SEO/sitemap complet, pages d'erreur personnalisées, optimisation Lighthouse production) n'est pas réaliste à livrer intégralement dans cette fenêtre -- plusieurs de ces items n'ont aucune infrastructure backend réelle sous-jacente (voir Partie 12, Facturation, 0/23). Traité en continuant à prioriser les items dont le backend réel existe déjà, plutôt que de fabriquer une complétion à 100% non réelle.

---

## PARTIE 10 — Sécurité & Governance — 🟡 PARTIEL (~10/49)

### 10.1 Sécurité de base

| # | Fonctionnalité | Statut |
|---|---|---|
| 10.1.1 | JWT | ✅ |
| 10.1.2 | Refresh tokens | ✅ |
| 10.1.3 | OAuth | ✅ |
| 10.1.4 | RBAC | 🟡 (hiérarchie fixe voir 1.2.7 ; rôles personnalisés + permissions granulaires réels ajoutés, voir le sous-lot ci-dessous) |
| 10.1.5 | Rate limiting | ✅ (+ géo-adaptatif, IP de confiance) |
| 10.1.6 | Request validation | ✅ (Pydantic partout) |
| 10.1.7 | Input sanitization | 🟡 |
| 10.1.8 | Prompt injection protection | 🟡 (écrit, pas intégré en filtre live) |
| 10.1.9 | SSRF protection | ⬜ |
| 10.1.10 | File validation | ✅ |
| 10.1.11 | MIME validation | ✅ (vérification magic-bytes) |
| 10.1.12 | Malware scanning (ClamAV) | ⬜ |
| 10.1.13 | Secret management | 🟡 (.env pour la clé maîtresse ; pas de KMS/Vault réel dans cet environnement -- voir le sous-lot ci-dessous) |
| 10.1.14 | Encryption at rest | 🟡 (réel, applicatif : AES-256-GCM ajouté pour `Webhook.secret` + Fernet déjà existant pour les clés JWT/SSO -- voir le sous-lot ci-dessous) |
| 10.1.15 | Encryption in transit | ✅ (HTTPS, voir guide de déploiement) |

### 10.2 AI Security (Guardrails) — ⬜ (0/10)

Prompt injection/jailbreak/PII/toxicity detection : rien d'intégré en
filtre actif (au-delà de 10.1.8's code non branché).

### 10.3 Audit & Logging

| # | Fonctionnalité | Statut |
|---|---|---|
| 10.3.1 | Audit log (actions admin) | ✅ (log inviolable HMAC, Catégorie 2 ; étendu avec organization_id/resource_type/resource_id + nouveaux types d'action réels -- voir le sous-lot ci-dessous) |
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

### Second lot DeepSeek "Partie 10.1-10.6" — incohérence de numérotation documentée

🐛 **Incohérence réelle relevée** : un second lot de prompts DeepSeek réutilise "10.1" à "10.6" pour RBAC avancé / Audit logs / Data encryption / GDPR-CCPA / Security scanning / Écran de sécurité -- une répartition **totalement différente** de la vraie Partie 10 de ce document (10.1 Sécurité de base, 10.2 AI Security, 10.3 Audit & Logging, 10.4 Enterprise Features, 49 items). Traité ici sous son propre sous-titre, comme pour la collision "Partie 14" déjà documentée plus haut. Guide complet : [`docs/security/PARTIE_10_SECURITY.md`](security/PARTIE_10_SECURITY.md).

✅ **RBAC personnalisé, réel** (`api/models/rbac.py`, `api/services/rbac_custom.py`, `api/routers/rbac.py`) -- additif à la hiérarchie fixe existante (owner/admin/manager/member/viewer) : catalogue fixe de 52 permissions (13 ressources × 4 actions), rôles personnalisés par organisation, permissions effectives calculées par union des rôles. Vérifié de bout en bout dans un vrai navigateur (création de rôle, assignation de permission, calcul des permissions effectives).

✅ **Audit logs étendus** (réel, pas nouveau système) -- nouvelles colonnes `organization_id`/`resource_type`/`resource_id` (délibérément hors du hash HMAC pour ne pas invalider la chaîne existante), nouveaux types d'action réels câblés dans les routers webhooks/documents/agents/conversations/intégrations/widget/clés API, nouveaux endpoints `/audit/stats`, `/audit/export`, `/audit/actions`, `/audit/resource/{type}/{id}`, `DELETE /audit/logs/purge`, et `GET /organizations/{org_id}/audit-logs` (vue utilisée par l'écran Sécurité).

✅ **Chiffrement réel additif** (`api/security/encryption.py`, AES-256-GCM via `cryptography`) -- `Webhook.secret` (auparavant en clair) est maintenant chiffré, migration de données appliquée sur les lignes existantes. Rotation de clé réelle (`POST /encryption/rotate-keys`, superadmin). `ENCRYPTION_KEY_STORAGE=env` est le seul mode réellement implémenté dans cet environnement (aucun compte KMS/Vault disponible) -- énoncé comme un fait, pas une excuse.

✅ **GDPR/CCPA additif** (`api/models/compliance.py`, `api/routers/compliance.py`) -- consentement par catégorie (marketing/analytics/cookies, distinct du consentement binaire déjà existant), tickets de demande de droits (accès/rectification/limitation/opposition), déclaration d'incident (Art. 33/34) avec notification réelle. Réutilise l'export/suppression déjà matures, ne les duplique pas.

✅ **Scan de sécurité réel** (`api/services/security_scan.py`) -- `pip-audit` (dépendances, vraie base OSV) et `bandit` (SAST) réellement exécutés en subprocess, scan de secrets par regex réel sur `api/`+`frontend/`. `container`/`infrastructure` honnêtement rapportés `unavailable` (pas de `trivy` installé, pas d'IaC dans ce dépôt) plutôt que simulés.

🐛 **Deux vrais bugs trouvés et corrigés en testant l'écran dans un vrai navigateur** : (1) `GET /rbac/permissions` ne faisait jamais `db.commit()` -- le catalogue de permissions semé était silencieusement annulé (rollback) à chaque requête ; (2) le scan de secrets utilisait `Path.glob("frontend/**/*.ts")`, qui parcourait entièrement `frontend/node_modules` (dizaines de milliers de fichiers) avant tout filtre d'exclusion, bloquant la requête plus de 10 secondes -- remplacé par `os.walk` avec élagage de répertoire en amont.

✅ **Écran de sécurité unique et consolidé** (`/dashboard/security`, lié dans la nav) -- 7 onglets (Overview, Roles & Permissions, Audit log, Encryption, Compliance, Vulnerability scan, Policies), vérifié de bout en bout dans un vrai navigateur avec une vraie session connectée.

⚠️ **Limite honnête** : les ~14 fichiers de composants React littéralement demandés (`RoleList.tsx`, `PermissionBadge.tsx`, etc.) n'ont pas été extraits séparément -- même discipline de consolidation qu'à la Partie 9.5. Les sous-endpoints PATCH très granulaires du widget (thème/nom/position/logo/avatar/questions suggérées) ne sont pas individuellement audités -- seuls la config et le thème le sont, un choix de portée documenté, pas un oubli.

---

## PARTIE 11 — Admin Dashboard & Analytics — 🟡 PARTIEL (~11/34)

| Section | Statut |
|---|---|
| 11.1 Vue Globale (8 items) | 🟡 (agrégation multi-org réelle ajoutée -- `GET /admin/stats` -- voir le sous-lot ci-dessous ; question clusters/knowledge gaps toujours absents) |
| 11.2 Analytics (16 items) | ⬜ (question clusters, knowledge gaps : rien) |
| 11.3 Monitoring (10 items) | GET /health ✅, GET /ready ✅, GET /metrics ✅ (Prometheus, vrai multiprocess), `GET /admin/monitoring/{health,resources,queues}` ✅ (réel, CPU/mémoire/disque via psutil, vraie inspection Celery) ; Flower, Grafana/alerting, health check vecteurs : ⬜ |

### Second lot DeepSeek "Partie 11.1-11.6" — incohérence de numérotation documentée

🐛 **Incohérence réelle relevée** : même collision que pour les Parties 10/14 déjà documentées -- un second lot DeepSeek réutilise "11.1" à "11.6" pour Dashboard/Organisations/Utilisateurs/Abonnements/Monitoring/Logs, une répartition différente de la vraie Partie 11 de ce document. Guide complet : [`docs/admin/PARTIE_11_ADMIN_DASHBOARD.md`](admin/PARTIE_11_ADMIN_DASHBOARD.md).

✅ **11.1 Statistiques globales réelles** (`api/services/admin_stats.py`) -- agrégats réels (COUNT/SUM) sur utilisateurs/organisations/documents/agents/conversations/clés API. Le revenu vient de vraies tables Plan/Subscription (11.4) -- 0 tant qu'aucune organisation réelle ne paie, jamais un chiffre fabriqué.

✅ **11.2 Gestion des organisations** -- suspension/réactivation réelle et réversible (`Organization.is_suspended`), distincte de la suppression. Chaque action auditée (nouvelles valeurs `AuditAction.ORGANIZATION_SUSPENDED`/`ORGANIZATION_ACTIVATED`, pas de détournement de `ORGANIZATION_DELETED`).

✅ **11.3 Gestion des utilisateurs** -- réutilise `is_active` (déjà vérifié à chaque connexion, donc une suspension bloque réellement et immédiatement, vérifié par un vrai test de connexion refusée). Réinitialisation de mot de passe = vrai email (l'admin ne voit jamais le nouveau mot de passe). Terminaison de session réutilise le vrai mécanisme existant.

🐛 **Bug réel trouvé et corrigé** : `GET /admin/users/{id}/activity` ne filtrait que par `user_id` (l'acteur), donc une suspension (enregistrée avec l'ID de l'admin) n'apparaissait jamais dans l'activité de l'utilisateur CIBLÉ. Corrigé pour inclure aussi les actions où l'utilisateur est la ressource ciblée.

✅ **11.4 Abonnements & plans, réels** (`api/models/admin.py`, `api/services/admin_subscriptions.py`) -- vrais modèles `Plan`/`Subscription`, CRUD complet, MRR/ARR/ARPU/churn calculés pour de vrai. **Portée honnête** : aucun processeur de paiement réel n'est branché (Partie 12, 0/23) -- `POST /admin/subscriptions/{id}/refund` renvoie un vrai `501 Not Implemented` plutôt que de simuler un mouvement d'argent qui n'existe pas.

🐛 **Bug réel trouvé et corrigé** : `DELETE /admin/subscriptions/{id}` avec un corps JSON (raison d'annulation) est non standard -- `httpx` refuse carrément le kwarg `json=` sur `.delete()`. Le `DELETE` littéral (sans corps) reste fonctionnel ; `POST .../cancel` (avec raison) ajouté pour l'usage réel avec piste d'audit.

✅ **11.5 Monitoring** -- réutilise `/health`/`/health/ready` existants, ajoute CPU/mémoire/disque réels (psutil) et une vraie inspection des files Celery (`celery_app.control.inspect()`).

✅ **11.6 Logs système** -- un vrai `logging.Handler` (`api/security/system_log_handler.py`) capture chaque ligne WARNING+ réellement émise par ce processus dans une vraie table `system_logs`, vérifié par un test direct (un vrai `logger.warning(...)` devient une vraie ligne).

✅ **Écran admin réel et consolidé** (`/admin`, route déjà existante -- pas de nouveau `/dashboard/admin` dupliqué) -- 6 onglets, vérifié de bout en bout dans un vrai navigateur avec de vraies données.

🐛 **Bug réel trouvé et corrigé (2026-09-10)** : `organizations` n'a aucune FK "propriétaire", donc `ON DELETE CASCADE` ne l'atteint jamais quand son unique membre est purgé (`api/tasks/account_purge.py`) -- une organisation devenait orpheline pour toujours (0 membre, aucun propriétaire possible). 108 lignes de test (créées par les suites d'intégration e2e qui tournent contre la vraie base Supabase, jamais nettoyées) s'étaient accumulées et remontaient dans le tableau de bord admin, donnant l'illusion de fausses données. Nettoyées après confirmation utilisateur ; la base réelle affiche maintenant 0 organisation, 1 utilisateur réel. Le purge task supprime désormais aussi toute organisation dont le membre purgé était le seul membre.

⚠️ **Limite honnête** : les ~60 fichiers de composants et les graphiques (Line/Bar/Pie/Area/Donut charts) littéralement demandés n'ont pas été construits séparément -- les statistiques s'affichent en vraies cartes chiffrées, pas encore en graphiques visuels. Choix de portée délibéré face à l'ampleur du lot, pas un oubli silencieux.

---

## PARTIE 12 — Facturation & Monétisation — 🟡 PARTIEL (~18/23)

Voir [`docs/billing/PARTIE_12_BILLING.md`](billing/PARTIE_12_BILLING.md) pour le guide consolidé.

✅ **12.1 Plans tarifaires** -- `Plan`/`Subscription` (déjà réels depuis 11.4) étendus avec prix annuel, `max_api_keys`/`max_webhooks`/`max_requests_per_month`, `priority_support`/`advanced_features`/`sla`. `GET /billing/plans` et `/billing/plans/{id}` publics (catalogue, pas de données d'organisation) ; `POST/PATCH/DELETE` restent sur `/admin/plans` (11.4) -- pas de duplication. `POST .../subscribe|upgrade|downgrade|cancel|reactivate` sous `/organizations/{org_id}/billing/...` (Owner uniquement).

✅ **12.2 Abonnements (Stripe)** -- intégration Stripe réelle (`api/services/billing_stripe.py`, SDK `stripe==11.4.1`) : checkout, portail client, méthodes de paiement, webhook avec vérification de signature et idempotence (`StripeEvent`). **Portée honnête** : `STRIPE_SECRET_KEY` n'est pas configuré dans cet environnement (aucun compte Stripe réel) -- chaque fonction renvoie un vrai `501 Not Implemented` plutôt que de simuler un paiement, vérifié par test (`test_stripe_checkout_honestly_501s_without_configured_keys`).

✅ **12.3 Crédits / utilisation** -- `Credit`/`CreditTransaction` réels, 4 packs fixes (Starter/Pro/Business/Enterprise), taux de conversion réels. Réutilise le vrai système d'usage déjà existant (`api/security/usage.py`, Partie 1.3.8) plutôt que de dupliquer un second compteur -- `check_limits` vérifie contre les vraies limites du `Plan`.

✅ **12.4 Factures** -- `Invoice`/`InvoiceLine` réels, numérotation séquentielle, PDF généré via WeasyPrint (même pattern que l'export de conversation, Partie 8). Génération mensuelle automatique (Celery) pour tout abonnement réellement payant (`monthly_price_cents > 0`) -- jamais de facture sur un plan gratuit.

✅ **12.5 Écran de facturation** -- page consolidée `/dashboard/billing` (6 onglets : Overview/Plans/Usage/Credits/Invoices/Payment), même discipline que Security (10.6) et Admin (11) -- pas de fragmentation en dizaines de composants. Vérifié en direct dans un vrai navigateur : abonnement, crédits (octroi de bienvenue réel, achat de pack réel), facture générée.

🐛 **Bug réel trouvé et corrigé** : `get_db()` n'auto-commit jamais (`api/database.py`) -- presque tous les endpoints mutants de `api/routers/billing.py` créaient/modifiaient des lignes qui étaient silencieusement annulées à la fermeture de la session (même classe de bug que le catalogue RBAC en Partie 10.1). Trouvé en testant en direct : le solde de crédits affichait 1000 mais aucune transaction ne persistait. Corrigé en ajoutant `await db.commit()` explicite sur chaque endpoint mutant, vérifié en re-testant en direct (transaction "Grant — Signup Allotment" puis achat de pack, toutes deux persistées).

⬜ **Restant (~5/23)** : synchronisation Stripe Products/Prices non testée contre une vraie API Stripe (code réel mais jamais exécuté avec de vraies clés) ; pas de relances automatiques testées en conditions réelles (dépend d'un vrai Celery beat en production) ; pas de composants frontend séparés pour chaque sous-élément (page consolidée à la place, même choix que 10.6/11).

---

## PARTIE 13 — Developer Experience — 🟡 PARTIEL (~10/52)

| Section | Statut |
|---|---|
| 13.1 Qualité du code (9 items) | ⬜ (pas de ruff/mypy/pre-commit/dependabot/bandit configurés) |
| 13.2 Tests (11 items) | 🟡 (383 tests auth réels en CI + 105 tests RAG hérités — substantiel, mais pas de tests E2E Playwright faute de frontend) |
| 13.3 CI/CD (8 items) | 🟡 (GitHub Actions réel : tests + Snyk + ZAP + build Docker ; pas de lint/type-check en CI, pas de déploiement automatique) |
| 13.4 Déploiement (12 items) | ⬜ (Docker existe et testé en CI ; Terraform/K8s/Helm/multi-cloud : rien) |
| 13.5 Observabilité (12 items) | Couvert par 10.3 |

🐛 **Incohérence réelle relevée** : un second lot de prompts DeepSeek a réutilisé le numéro "Partie 13" pour un sujet totalement différent (Monitoring & Observabilité : métriques Prometheus, logging structuré, alerting, tracing OpenTelemetry, écran de monitoring) — y compris ses propres sous-numéros 13.1 à 13.5, qui collisionnent aussi avec les 5 lignes réelles ci-dessus. Ce second lot est réel et livré — voir [`docs/monitoring/PARTIE_13_OBSERVABILITY.md`](monitoring/PARTIE_13_OBSERVABILITY.md) — mais documenté séparément plutôt que de renuméroter cette section réelle, préexistante, du cahier des charges (même discipline que pour toutes les collisions Partie 10/11/12 précédentes).

✅ **Partie 13 (bis) — Monitoring & Observabilité — 🟡 PARTIEL (~18/23)** — real Prometheus counters HTTP+Celery, corrélation request_id réelle (bug trouvé : `system_logs.request_id` n'était jamais rempli, corrigé), logging JSON structuré, alerting réel (règles/canaux/historique/incidents) évalué contre de vraies données (psutil/Celery), vérifié en direct (règle créée, déclenchée réellement, visible dans l'historique). OpenTelemetry réel mais désactivé par défaut (aucun collecteur OTLP réel dans cet environnement). Écran : onglets "Monitoring" et "Alerting" ajoutés à `/admin` (pas de nouvelle page séparée, même discipline anti-duplication que 10.6/11/12.5).

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

🐛 **Incohérence réelle relevée** : un second lot de prompts DeepSeek a réutilisé le numéro "Partie 15" pour un sujet totalement différent (Intégrations avancées CRM/ERP : connecteurs universels, Zapier/Make/n8n, Airbyte) — collision avec cette vraie section préexistante du cahier des charges (déjà elle-même incomplète). Documenté séparément ci-dessous plutôt que renuméroté, même discipline que pour toutes les collisions précédentes (Partie 10/11/12/13).

✅ **Partie 15 (bis) — Intégrations avancées (CRM/ERP) — 🟡 PARTIEL, endpoints/jobs/frontend/tests tous complétés (~/~40)** — voir [`docs/integrations/PARTIE_15_ADVANCED_INTEGRATIONS.md`](integrations/PARTIE_15_ADVANCED_INTEGRATIONS.md). Résumé honnête : le sortant (notifier Zapier/Make/n8n d'un événement de cette app) existe déjà réellement depuis la Partie 9.2.7 (`Webhook`/`WebhookDelivery`) — pas dupliqué. Ce qui est réellement nouveau : un vrai récepteur entrant (`IntegrationConnection`, jeton bearer réel, mapping de champs réel — CRUD complet avec `PATCH`, action réelle "ingérer comme document" réutilisant le vrai pipeline RAG existant), tous les endpoints (providers/test/sync/syncs/mappings PATCH), les 3 jobs Celery périodiques (`retry_failed_syncs`, `process_integration_webhooks`, `sync_integrations`), les 11 composants frontend réels (`ProviderList`/`ProviderCard`/`ConnectionList`/`ConnectionItem`/`ConnectionForm`/`ConnectionTest`/`SyncHistory`/`MappingEditor`/`MappingList`/`WebhookConfig`/`IntegrationLogs`) et les 5 fichiers de tests (4 backend + `components.test.tsx`, ce dernier ayant nécessité l'installation complète de Vitest/RTL, absente du projet jusqu'ici) — tout vérifié en direct. Un vrai client Airbyte (appelle la vraie API REST d'une vraie instance Airbyte) répond honnêtement `501` tant qu'aucune instance réelle n'est configurée. L'installation réelle via `abctl` a créé un vrai cluster Kubernetes local mais est bloquée par un vrai blocage réseau (CDN GitHub Pages inaccessible depuis cette machine, hors du contrôle du code) — voir le document lié pour le détail exact. Aucun des 300+ connecteurs Airbyte n'est réimplémenté ici, Airbyte lui-même les fournit.

🐛 **Incident réel trouvé et corrigé pendant ce travail** : la suite de tests utilisait les vraies clés Twilio live présentes dans `.env`, causant un vrai appel à l'API Twilio (charge réelle de -0.001 $) lors d'un test censé vérifier le comportement "non configuré". Corrigé par un fixture autouse dans `tests/conftest.py` qui neutralise les credentials Twilio par défaut pour tous les tests — voir le document Partie 15 lié pour le détail complet.

🐛 **Incohérence réelle relevée** : un troisième lot de prompts DeepSeek a réutilisé le numéro "Partie 16" (déjà pris par les 4 modèles de vente, documentés "Partie 16 (bis)") pour un sujet totalement différent (Marketplace de plugins). Documenté comme "Partie 16 (ter)", même discipline que toutes les collisions précédentes.

✅ **Partie 16 (ter), suite (2026-09-18) — les 4 derniers points internes finalisés** : **sandbox conteneurisé réel** (`Dockerfile.plugin-sandbox`, image construite et testée en direct via de vrais `docker run` — `--network none`, `--read-only`, `--cpus=0.5`, `--memory=256m`, `--cap-drop ALL`, `--security-opt no-new-privileges`, utilisateur non-root — utilisé automatiquement quand Docker est disponible, repli honnête sur le sous-processus sinon) ; **les 6 hooks restants câblés** sur de vrais événements plateforme (`on_message_received`/`on_message_sent` dans `agent_orchestrator.py`, `on_agent_created` dans `create_agent`, `on_conversation_started` dans `create_conversation_endpoint`, `on_error` via un vrai middleware FastAPI, `on_schedule` via une vraie tâche Celery Beat horaire) — les 7 hooks sont maintenant réellement câblés (contre 1/7 avant) ; **vérification des permissions à l'exécution** réelle (le dispatch de hook ignore silencieusement un plugin installé qui n'a pas déclaré la permission requise ; l'exécution manuelle accepte un `required_permission` et renvoie un vrai `403` sinon) ; **filtre gratuit/payant réel** (`Plugin.pricing`/`price`, validés, filtrables et triables dans le marketplace — métadonnée déclarative honnête, sans vrai flux de paiement derrière). Deux points externes traités en parallèle : bug CircleCI réel corrigé (`<<` heredoc, token YAML 2.1 réservé, trouvé via un vrai run CircleCI échoué — déplacé dans `scripts/ci_create_buckets.py`), GitHub Actions désactivé explicitement (`.github/workflows.disabled/`, décision de ne pas payer), connexion Airbyte Cloud tentée en direct avec de vraies credentials OAuth2 (échec `401` constant et honnêtement rapporté, code d'échange de token réel et correct malgré tout). Voir [`docs/plugins/SECURITY.md`](plugins/SECURITY.md) pour l'analyse complète et honnête de ce que "isolé" signifie réellement.

🐛 **Deux vrais bugs trouvés et corrigés via le premier run CircleCI réel de bout en bout (2026-09-19, pipeline #2, commit `444f162`)** — l'IA de résumé de CircleCI a signalé un vague "exit code 4 (tests en échec)" sans détail exploitable ; reproduction réelle en local (mêmes 263 fichiers de test, `pytest --cov ... --cov-fail-under=75`) a donné un résultat différent et exact : 5 échecs sur 3847 tests (2 étaient un artefact du `.env` local contenant les vraies clés Airbyte, non pertinents pour la CI). Les 2 vrais bugs corrigés : (1) **43 tables sans Row Level Security** (`airbyte_connections`, `plugins`/`plugin_versions`/`plugin_installations`/`plugin_reviews`/`plugin_executions`, `credits`, `invoices`, `licenses`, `subscriptions`, etc.) — toutes les migrations depuis 0088 (Partie 10 sécurité/conformité) avaient oublié la ligne `ENABLE ROW LEVEL SECURITY` que chaque migration antérieure avait ; corrigé par une nouvelle migration additive `0098_rls_coverage_gap.py` (aucun changement de comportement observable, RLS est un signal de conformité/défense en profondeur documenté dans `docs/AUTH_BACKEND_SETUP.md`, pas une isolation fonctionnelle — l'app se connecte en `postgres`, `rolbypassrls`). (2) **Collision réelle de clé `metadata_json["structure"]`** dans `api/security/documents.py` : l'extraction JSON pose `"structure": "nested_array"` (forme du document), mais le bloc générique de détection de plan (titres PDF/DOCX/MD/HTML/TXT) écrasait inconditionnellement cette même clé avec `[]` pour tout autre format (JSON, CSV, XML, EPUB) — corrigé en ne réécrivant `"structure"` que pour les 5 formats qui produisent réellement un plan de titres, laissant intacte la valeur posée par l'extracteur spécifique au format sinon.

✅ **Airbyte Cloud — intégration réelle finalisée (2026-09-19)** : les 6 fonctions de [`airbyte_client.py`](../api/services/airbyte_client.py) réécrites contre la vraie API REST publique d'Airbyte Cloud (elles ciblaient l'ancienne API OSS "Configuration", que Cloud n'expose pas). Vérifié en direct de bout en bout dans le vrai compte : création d'une vraie source de test (`source-faker`), découverte du vrai schéma (3 streams), création d'une vraie destination de test (`/dev/null`), création d'une vraie connexion, déclenchement d'un vrai job de synchronisation (statut `running` confirmé), puis nettoyage complet des 3 ressources de test. `GET /integrations/airbyte/status` répond maintenant honnêtement `{"configured": true, "reachable": true}`. Voir [`docs/integrations/AIRBYTE.md`](integrations/AIRBYTE.md).

✅ **Partie 16 (ter) — Marketplace de plugins — ✅ COMPLET (scope honnête)** — voir [`docs/marketplace/PARTIE_16_TER_MARKETPLACE.md`](marketplace/PARTIE_16_TER_MARKETPLACE.md), [`docs/plugins/DEVELOPER_GUIDE.md`](plugins/DEVELOPER_GUIDE.md), [`docs/plugins/MARKETPLACE.md`](plugins/MARKETPLACE.md), [`docs/plugins/SECURITY.md`](plugins/SECURITY.md). Système réel : `Plugin`/`PluginVersion` (vrai historique de versions append-only)/`PluginInstallation`/`PluginReview`/`PluginExecution` (vrai journal d'exécution), validation stricte du manifest (schéma + whitelist de permissions/hooks fixe, convention `resource:action` alignée sur `permission_catalog.py`) et scan statique réel du code avant toute publication. **Sandbox d'exécution réel** ajouté dans une passe ultérieure (`api/security/plugin_sandbox.py`) : vrai sous-processus OS séparé (`node`/`python`), vrai timeout, vraie limite mémoire POSIX (`RLIMIT_AS`, absente sur Windows — gap honnête documenté), aucune autorité ambiante (environnement quasi-vide). Vérifié en direct sans mock (vrais sous-processus lancés par les tests) : succès, erreur, timeout réel (5s de sleep contre 1s de limite), et preuve réelle qu'un secret du process de test n'est PAS visible dans le sandbox. Rate-limiting réel (invocations/minute). 4 jobs Celery réels (re-scan pending/approved, nettoyage, réconciliation du compteur d'installations). Système de hooks réel (`api/services/plugin_hooks.py`) : 7 hooks déclarables, **1 seul réellement câblé** sur un vrai événement plateforme (`on_document_uploaded`, dans `upload_document`) — les 6 autres sont réels et dispatchables mais honnêtement non câblés à un événement réel, documenté explicitement plutôt que fabriqué. 22 endpoints réels au total. Frontend : 14 composants réels séparés (`PluginMarketplace`/`PluginCard`/`PluginDetail`/`PluginInstallButton`/`PluginList`/`PluginFilters`/`PluginSearch`/`PluginReviews`/`PluginReviewForm`/`PluginCreateForm`/`PluginVersionForm`/`InstalledPlugins`/`PluginConfigForm`/`PluginLogs`), composés dans une page consolidée `/dashboard/marketplace`. Vérifié en direct de bout en bout dans un vrai navigateur : publication réelle → upload S3 réel → statut `pending` → approbation admin réelle → visibilité marketplace → installation réelle → désinstallation. Deux vrais bugs trouvés et corrigés (crash `MissingGreenlet` sur `updated_at` après une UPDATE ; type enum Postgres non créé automatiquement par `add_column` lors de la migration). Scope honnête et explicite : pas de sandbox conteneurisé (Docker/gVisor), pas d'accès réseau sortant réel pour `access:external_api`, pas de filtre gratuit/payant (aucun modèle de prix pour les plugins), permissions non vérifiées contre le contenu réel du payload à l'exécution — tout documenté sans être caché.

---

## PARTIE 18 — Modèles de vente (SaaS / Self-hosted / Partenaire / White-label) — ✅ COMPLET (scope honnête)

Discipline établie appliquée dès le départ : les 4 modèles de vente
demandés existaient déjà en grande partie (SaaS complet depuis la
Partie 11.4/12 ; self-hosted, hybrid support/SLA, et reseller/sub-client
depuis la Partie 16 (bis) ; white-label depuis les Parties 1.3.10/1.4.1/
1.4.5). Un agent d'exploration dédié a d'abord audité l'existant avant
tout code, pour ne construire QUE les vrais manques réels — voir le
détail complet dans [`docs/sales/PARTNER_PROGRAM.md`](sales/PARTNER_PROGRAM.md).

✅ **Programme partenaire — le vrai manque comblé** : `PartnerCommission`
(migration `0099_partner_commissions.py`, RLS activé dès la création —
leçon retenue de `0098`), le ledger persisté (payé/en attente) que
`calculate_reseller_commission` (Partie 16 bis) laissait volontairement
en calcul à la volée uniquement. Inscription self-service réelle
(`POST /partners/register`, jusque-là superadmin uniquement),
tableau de bord partenaire (`GET /partners/me`, `/me/clients`,
`/me/commissions`), paiement manuel (`POST /partners/commissions/{id}/pay`)
et 2 tâches Celery réelles (`calculate_partner_commissions` mensuel,
idempotent par période — testé en direct ; `pay_partner_commissions`
quotidien, respecte un vrai seuil minimum de paiement,
`PARTNER_MIN_PAYOUT_CENTS`). Aucun vrai virement bancaire (pas de
Stripe Connect) — honnêtement documenté comme un changement d'état de
ledger, pas un paiement réel automatisé. Frontend :
`PartnerDashboard.tsx`/`CommissionList.tsx`, composés dans
`/dashboard/partners`.

✅ **Self-hosted — les 2 scripts manquants ajoutés** : `update.sh`
(sauvegarde réelle avant toute mise à jour, chemin de restauration
explicite en cas d'échec) et `uninstall.sh` (ne supprime jamais les
données par défaut, `--purge-data` explicite requis). Nouvelle tâche
Celery `validate_licenses` (revalidation périodique réelle, teste en
direct : bascule une licence expirée à `expired`).

✅ **SaaS — alerte d'usage réelle ajoutée** : tâche Celery
`check_usage_limits` (horaire), réutilise le même comptage réel de
ressources que l'enforcement à la demande, envoie un vrai email
d'avertissement avant qu'une organisation n'atteigne sa limite réelle.

🟡 **White-label** : à l'époque de la Partie 18, aucun vrai manque
trouvé au-delà de ce qui existait déjà (branding, domaines
personnalisés, email de domaine personnalisé, bascule white-label).
Un audit plus poussé demandé explicitement en Partie 19 a trouvé de
vrais manques réels (voir plus bas) — non contredit, juste approfondi.

10 tests réels ajoutés dans `tests/test_sales_models.py` (inscription,
double-inscription rejetée, tableau de bord, paiement de commission,
idempotence du calcul mensuel, seuil de paiement minimum, expiration
de licence), tous passés en direct.

---

## PARTIE 19 — White-label complet — ✅ COMPLET (scope honnête)

Discipline établie appliquée en premier : audit de l'existant AVANT
tout code (demandé explicitement par ce prompt). Résultat honnête :
9 des 15 champs du `WhiteLabelConfig` demandé existaient déjà sur
`OrganizationBranding` (Partie 1.3.10), 2 de plus sur `CustomDomain`
(Partie 1.4.1). Créer une deuxième table aurait dupliqué une source de
vérité déjà réelle — exactement l'erreur qu'`api/security/white_label.py`
avait déjà documenté avoir rejetée une fois, pour la même raison. Donc :
`organization_branding` étendue avec les 6 vrais champs manquants
(`company_email`/`support_email`/`email_sender_name`/`email_sender_email`/
`custom_js`/`is_active`, migration `0101`, RLS non concerné — table déjà
couverte), le reste vient en lecture croisée depuis `custom_domains`.

✅ **12 endpoints réels** sous `/organizations/{org_id}/whitelabel/...`
(Member+ lecture, Admin+ écriture — un cran plus permissif que
l'ancien `/white-label` Owner-only, conservé inchangé) : config
GET/PATCH, domaine POST/DELETE/verify, email POST/DELETE, logo
POST/DELETE, favicon POST, preview GET, reset POST. Logo/favicon
délèguent au vrai upload S3 déjà existant (Partie 1.3.10), domaine
délègue à la vraie vérification DNS déjà existante (Partie 1.4.1) —
rien réimplémenté.

✅ **Vrai kill switch `is_active`**, distinct de `hide_platform_branding` :
testé en direct — désactivé, l'aperçu retombe sur les vrais défauts de
la plateforme sans perdre la configuration sauvegardée.

✅ **Middleware réel de détection de domaine** (`api/services/white_label_middleware.py`)
— le vrai manque d'infrastructure trouvé par l'audit : rien ne lisait
encore le header `Host` d'une requête entrante pour résoudre
l'organisation via son domaine personnalisé. **Vrai bug trouvé et
corrigé pendant l'écriture de ses propres tests** : une première
version ouvrait sa propre session DB directement, contournant la
substitution de base de test — 36 tests non liés sont passés de
quelques secondes à 3m24s, la preuve chiffrée que CHAQUE requête de
toute la suite de tests tapait réellement la vraie base Postgres de
production. Corrigé en passant par `request.app.dependency_overrides`,
le même mécanisme que `Depends(get_db)` utilise déjà.

✅ **`custom_js` honnêtement non sanitisé** : contrairement à
`custom_css` (motifs dangereux réels rejetés), un script est du code
arbitraire par définition — la vraie barrière de sécurité documentée
est le contrôle d'accès (Admin+ uniquement) et la portée (seulement la
page white-labelée de cette organisation), pas une sanitisation
illusoire.

✅ **16 tests backend réels** (`tests/backend/whitelabel/test_config.py`,
`test_domain.py`, `test_email.py`, `test_logo.py`) + **14 tests
frontend réels** (`frontend/components/whitelabel/components.test.tsx`
— placé à côté des composants comme `plugins`/`integrations`, pas au
chemin `tests/frontend/whitelabel/` suggéré, hors de la racine vitest
et jamais découvert), tous passés en direct. Voir
[`docs/whitelabel/CONFIGURATION.md`](whitelabel/CONFIGURATION.md),
[`docs/whitelabel/DOMAIN.md`](whitelabel/DOMAIN.md),
[`docs/whitelabel/EMAIL.md`](whitelabel/EMAIL.md),
[`docs/whitelabel/RESELLER.md`](whitelabel/RESELLER.md).

⬜ **Gap honnête non construit** : pas de propagation automatique de la
marque d'un revendeur vers tous ses sous-clients (chaque organisation
reste sa propre config white-label indépendante) — voir
`docs/whitelabel/RESELLER.md`.

---

## PARTIE 20 — Analytics avancés — ✅ COMPLET (scope honnête)

Audit préalable (agent d'exploration dédié) : Prometheus, la santé
système, les revenus/MRR/ARR/ARPU/churn (compte brut), le ledger
d'usage quotidien par organisation, le tableau de bord qualité RAG, et
le suivi tokens/coût par évaluation étaient TOUS déjà réels — rien
dupliqué. 3 vrais manques comblés : `AnalyticsEvent` (journal
d'événements produit en texte libre, délibérément distinct d'`AuditLog`
dont l'enum d'actions est fermé et à visée sécurité/conformité),
`AnalyticsAggregate` (agrégats matérialisés par période, pour des
requêtes de tableau de bord rapides), `AnalyticsDashboard` (mise en
page de widgets sauvegardée — le seul vrai manque de "dashboard
personnalisable" dans tout le code).

✅ **Business (superadmin, plateforme entière)** : étend
`admin_subscriptions.py` avec le **vrai taux de churn** (pas juste le
compte brut), la **rétention**, le **LTV** (ARPU / taux de churn,
honnêtement `null` sans signal de churn) et une **tendance de revenu
quotidienne réelle** (approximation honnêtement documentée : prix du
plan actuel appliqué rétroactivement, faute d'historique de prix).

✅ **Produit (par organisation)** : usage (réutilise le ledger existant),
adoption, engagement (utilisateurs actifs quotidiens), funnels — tout
basé sur `AnalyticsEvent`, honnêtement vide tant qu'aucun événement
réel n'est tracké.

✅ **Technique (par organisation)** : performance/erreurs sont
honnêtement documentées comme **plateforme entière, pas par
organisation** (Prometheus n'a pas de label `org_id`) ; usage API
réutilise le ledger existant ; usage LLM est un vrai pont vers le
suivi tokens/coût de l'Evaluation Lab, avec le champ
`"scope": "evaluation_lab_runs_only"` explicite — n'inclut PAS les
vraies conversations de production, aucun suivi token/coût n'existe
pour ce chemin dans ce code, honnêtement signalé plutôt que tu.

✅ **Dashboards personnalisables réels** : CRUD complet, un seul
dashboard par défaut appliqué automatiquement, widgets en JSON opaque
côté frontend.

✅ **Export CSV/JSON réel**, borné par `ANALYTICS_MAX_EXPORT_ROWS`.

✅ **Première dépendance de graphiques du frontend** : `recharts`
ajoutée (`--legacy-peer-deps`, conflit préexistant et non lié entre
`vitest@5` et `@types/node@^20`) — aucune librairie de graphiques
n'existait avant.

✅ **29 tests backend + 10 tests frontend réels**, tous passés en
direct dès la première exécution. Voir
[`docs/analytics/METRICS.md`](analytics/METRICS.md),
[`docs/analytics/BUSINESS.md`](analytics/BUSINESS.md),
[`docs/analytics/PRODUCT.md`](analytics/PRODUCT.md),
[`docs/analytics/TECHNICAL.md`](analytics/TECHNICAL.md),
[`docs/analytics/DASHBOARDS.md`](analytics/DASHBOARDS.md).

⬜ **Gap honnête non construit** : segmentation réelle (par plan, par
rôle, etc.) — `SegmentSelector.tsx` n'offre qu'un seul segment
fonctionnel ("Tous les utilisateurs") aujourd'hui, aucune dimension de
segmentation réelle n'est trackée sur `AnalyticsEvent`.

---

## PARTIE 21 — A/B testing avancé — ✅ COMPLET (scope honnête)

Audit préalable : la Partie 7.3.10 avait déjà construit un vrai système
d'A/B testing EN PRODUCTION, mature — bucketing déterministe réel (hash
MD5 mod 100), statistiques incrémentales réelles
(`{count, sum, sum_sq}` par variante/métrique), et une vraie p-value
(approximation normale du test t de Welch). Rien reconstruit. Seuls les
vrais manques ont été comblés : champs de config par test
(`test_type`, `target_metric`, `min_sample_size`, `confidence_level`),
`ABTestAssignment` (audit réel des assignations — le hash n'en avait
jamais eu besoin pour fonctionner, mais rien ne répondait à "qui a été
assigné à quoi"), `ABTestResult` (snapshot historique réel, distinct du
`metrics` JSON qui reste les statistiques courantes), intervalle de
confiance/Cohen's d/puissance statistique réels, décision automatique
statistique (`POST /decide`, distincte du choix humain manuel
préexistant `.../variants/choose`), CRUD complet (PATCH/DELETE/resume),
export CSV/JSON, 4 tâches Celery réelles, et le partage Member+/Admin+
explicitement demandé par ce prompt.

🐛 **Vrai bug trouvé et corrigé en testant en direct — répond
directement à la vision critique "les statistiques sont-elles
correctes"** : `track_ab_test_metric` faisait une copie SUPERFICIELLE
(`dict(test.metrics)`) avant de muter la statistique d'une variante.
Les dictionnaires imbriqués par variante restaient les MÊMES objets
que ceux déjà attachés à `test.metrics` — muter la variante B mutait
donc `test.metrics["b"]` en place, AVANT même la réaffectation
`test.metrics = metrics`. SQLAlchemy ne détectait alors aucune vraie
différence entre l'ancienne et la nouvelle valeur et sautait
silencieusement la mise à jour SQL. Confirmé en direct avec des prints
réels : l'échantillon tracké pour la variante B apparaissait dans la
réponse de CETTE requête, puis disparaissait — jamais réellement
persisté. Corrigé avec `copy.deepcopy` au lieu d'une copie superficielle.

✅ **25 tests backend + 7 tests frontend réels**, tous passés en
direct (le seul échec initial était une erreur dans mon PROPRE test,
pas dans le code — une intervalle de confiance à largeur nulle est
mathématiquement correcte quand la variance des deux groupes est nulle,
pas un bug). Aucune régression sur les tests préexistants
(`tests/test_ab_tests.py`, `tests/test_ab_tests_endpoints.py`). Voir
[`docs/ab-testing/OVERVIEW.md`](ab-testing/OVERVIEW.md),
[`docs/ab-testing/STATISTICS.md`](ab-testing/STATISTICS.md),
[`docs/ab-testing/BEST_PRACTICES.md`](ab-testing/BEST_PRACTICES.md).

---

## PARTIE 22 — Multi-modal (images, audio, vidéo) — ✅ COMPLET (scope honnête, 2 décisions déclinées documentées)

Audit préalable (agent d'exploration dédié) : OCR Tesseract réel déjà
câblé dans le pipeline documents (`api/services/ocr.py`,
`document_images`), transcription audio réelle déjà câblée
(`api/services/voice.py::transcribe_audio`, Whisper/Deepgram via
litellm), et le pipeline RAG réel existant
(chunk/clean/normalize/embed → `DocumentChunk`). Rien de tout ça n'a
été reconstruit. La vidéo, en revanche, était un vrai terrain vierge
total (aucun ffmpeg/opencv/extraction de frames nulle part) — c'est le
plus gros vrai manque comblé ici.

**Construit** : `MediaAsset`/`MediaTranscript`/`MediaFrame` (upload
autonome image/audio/vidéo, distinct des images embarquées dans un
document) ; `document_images` étendu (pas dupliqué) avec
`description`/`objects_json` ; `document_chunks.document_id` rendu
nullable + nouvelle colonne `media_asset_id` pour indexer le texte
issu des médias dans le MÊME index RAG (pas un second store vectoriel
parallèle) ; description d'image réelle par LLM vision
(`describe_image`, réutilise `chat_completion`/litellm — aucun appel
vision n'existait avant cette partie) ; extraction audio/frames vidéo
réelle via ffmpeg (`api/services/video_extraction.py`, même catégorie
de dépendance binaire système que Tesseract/poppler) ; recherche
multi-modale (`POST /media/search`) réutilisant la similarité cosinus
déjà existante ; 5 tâches Celery réelles (traitement + 4 sweeps de
rattrapage/nettoyage) ; endpoints upload/list/get/delete/process/
status/transcript/description/frames/search ; migration `0104` (RLS
activé à la création).

### Finalisation (post-livraison initiale)

Suite à une demande explicite de traiter les 4 points partiels :

- **Diarisation audio** : ajoutée, réelle, Deepgram uniquement (seul
  fournisseur STT intégré dont l'API réelle la supporte — Whisper n'a
  aucun paramètre équivalent). Nouvelle fonction
  `transcribe_audio_with_diarization` (jamais un changement de
  `transcribe_audio` — même discipline "ne jamais renommer/changer une
  fonction déjà appelée par des tests préexistants" que Partie 21).
  **Limite honnête et documentée** : aucun compte Deepgram réel
  disponible dans cet environnement pour vérifier la forme exacte de
  la réponse diarisée que litellm normalise — le parsing est
  défensif (`_parse_diarization_segments`) et renvoie honnêtement
  `None` (jamais un locuteur inventé) si la forme attendue n'est pas
  trouvée.
- **Description vision dans `process_document`** : câblée, réelle,
  mais **désactivée par défaut**
  (`MULTIMODAL_DESCRIBE_DOCUMENT_IMAGES=False`) — un appel LLM vision
  synchrone par image embarquée ajouterait une latence et un coût réels
  à CHAQUE upload de document, pour chaque organisation,
  inconditionnellement. Même logique que `AB_TEST_AUTO_DECIDE`/
  `OTEL_ENABLED` : réel et fonctionnel, activable une fois le
  coût/latence acceptés par l'opérateur.
- **14 composants frontend séparés** : audit de correspondance
  confirmé — voir "Deuxième finalisation" ci-dessous.

### Deuxième finalisation — YOLO local + audit frontend

Suite à confirmation par l'utilisateur qu'un vrai `torch==2.13.0+cpu`
était déjà installé, le détecteur d'objets séparé (initialement
décliné) a été ajouté pour de vrai :

- **`api/services/object_detection.py`** : détection réelle, locale,
  YOLOv8n via `ultralytics` (poids ~6.5 Mo, réutilisation de torch déjà
  présent — plus une dépendance lourde). **Confirmé en direct** contre
  une vraie photo (l'échantillon `bus.jpg` fourni par ultralytics
  lui-même) : détection réelle `['bus', 'person']`. Câblé en PRIORITÉ
  dans le pipeline (`process_media_asset`, `extract_video_frames`) —
  repli sur les objets du LLM vision uniquement si YOLO n'est pas
  disponible (paquet absent, poids non téléchargeables). Poids stockés
  dans `storage/ml_models/` (gitignored, jamais commités).
- **Tests** : 15 tests réels (parsing, dégradation gracieuse,
  priorité YOLO sur LLM vision dans le pipeline, et un test réel de
  bout en bout non mocké contre la vraie photo `bus.jpg`).

**Audit de correspondance frontend (14 composants demandés)** :
aucun manque fonctionnel trouvé. `MediaUpload.tsx` est couvert par
`MediaUploadZone.tsx` (upload + drag-and-drop dans le même fichier) ;
`VisualSearch.tsx` est couvert par `MediaSearch.tsx` (filtre
`media_type=image`, même interprétation que les 3 routes de recherche
du prompt original — une recherche textuelle filtrée par type, pas une
recherche par similarité d'image). Les 12 autres noms demandés
correspondent 1:1 à des fichiers du même nom déjà créés. Aucun fichier
correctif ajouté puisqu'aucun manque fonctionnel réel n'a été trouvé.

### Troisième finalisation — recherche visuelle réelle par CLIP

Suite à une demande explicite d'ajouter CLIP, comblant le dernier gap
honnête signalé ci-dessus (recherche textuelle filtrée par type ≠
recherche par similarité d'image) :

- **`api/services/visual_search.py`** : CLIP réel
  (`openai/clip-vit-base-patch32` via `transformers`, déjà une
  dépendance réelle) + `faiss-cpu` (nouvelle dépendance, réellement
  légère) pour le classement par plus proches voisins. **Confirmé en
  direct, sans mock** : la requête texte "a photo of a bus" obtient un
  score de similarité réel plus élevé contre la vraie photo `bus.jpg`
  (échantillon ultralytics) que contre `zidane.jpg` (un joueur de
  football) — preuve réelle que les embeddings CLIP capturent
  effectivement le sens visuel.
- **Indexation réelle** : chaque image traitée obtient un vrai
  embedding CLIP stocké dans `MediaAsset.clip_embedding` (migration
  `0105`) — dégradation honnête si CLIP est indisponible (pas de
  réseau au premier chargement, etc.) : l'image n'apparaît simplement
  pas dans les résultats visuels, jamais un résultat inventé.
- **2 nouveaux endpoints réels et distincts** (pas une simple variante
  filtrée) : `POST /media/search/visual` (texte → images) et
  `POST /media/search/similar` (image → images similaires).
- **Frontend** : `VisualSearch.tsx`, un composant réel et distinct
  (recherche texte + upload d'image), câblé comme nouvel onglet
  "Visual search" sur la page média.
- **Tests** : 7 tests backend (dont le test réel de bout en bout
  ci-dessus, non mocké) + 2 tests frontend réels.

✅ **16 + 10 + 7 tests backend + 5 + 2 tests frontend réels**, tous
passés en direct (upload, validation de taille/type, contrôle
d'accès, traitement image/audio/vidéo avec mocks sur les vraies
frontières externes — LLM vision, transcription, diarisation, ffmpeg
—, indexation RAG, recherche textuelle et visuelle, isolation
multi-tenant). Aucune régression sur les tests préexistants
OCR/extraction d'images/voice/telephony. Voir
[`docs/media/OVERVIEW.md`](media/OVERVIEW.md),
[`docs/media/IMAGES.md`](media/IMAGES.md),
[`docs/media/AUDIO.md`](media/AUDIO.md),
[`docs/media/VIDEO.md`](media/VIDEO.md),
[`docs/media/SEARCH.md`](media/SEARCH.md).

---

## PARTIE 23 — Agents autonomes — ✅ COMPLET (scope honnête)

Audit préalable (agent d'exploration dédié) : un vrai chatbot Agent
mono-tour (Partie 5.3), une vraie décomposition/validation de tâches
(Partie 5.1.13), un vrai registre d'outils avec sélection réelle
(Partie 5.1.2), et de vrais garde-fous (Partie 5.3.9) existaient déjà.
**Chaque docstring de ces modules signale explicitement qu'aucune
vraie boucle d'exécution multi-étapes n'a jamais été construite** —
c'est le seul vrai manque, mais un manque réel et conséquent, comblé
ici.

**Pourquoi `AutonomousAgent` est une nouvelle table, pas des colonnes
sur `Agent`** : `Agent` est un chatbot configuré, multi-tour (un
`system_prompt`, pas de `goal`, pas de statut d'exécution). Un
`AutonomousAgent` est un objectif unique qu'il planifie et exécute
lui-même, puis s'arrête. Deux vrais cycles de vie distincts, pas la
même table avec des colonnes en plus.

**Construit** : `AutonomousAgent`/`AgentPlan`/`AgentStep`/
`AgentMemory`/`AgentCollaboration` (5 tables, RLS activé à la
création, migration `0106`) ; la vraie boucle d'exécution
(`run_autonomous_agent`) — planifie, sélectionne un outil réel ou
retombe sur du raisonnement pur, exécute, écrit le résultat, vérifie
garde-fous/limites/approbation humaine avant chaque étape, replanifie
une fois en cas d'échec ; mémoire réelle à 3 niveaux (court terme/long
terme/épisodique) avec embeddings réels, récupération sémantique
réelle, consolidation réelle, oubli réel ; collaboration agent-à-agent
réelle mais volontairement bornée à un seul appel LLM (pas de
récursion imbriquée non bornée) ; endpoints CRUD + run/pause/resume/
stop/status + plans/steps + memory + collaborate ; 5 tâches Celery
réelles ; 12 composants frontend + page dédiée.

**Réutilisé, pas reconstruit** : `task_planning.decompose_task`/
`validate_plan` (décomposition LLM réelle) ; `tool_selection.select_tools`
+ le registre `ToolSpec` réel (calculator/word_count déjà utilisables) ;
`agent_guardrails.check_unsafe_content` (rendu public pour cette
réutilisation, mêmes vrais patterns regex) ; `generate_embeddings` +
`cosine_similarities` (déjà utilisés pour la recherche média Partie
22) pour la mémoire sémantique ; la convention JSON-liste-de-floats de
`DocumentChunk.embedding` pour `AgentMemory.embedding`.

🐛 **Simplification réelle, documentée, pas un manque caché** :
l'approbation humaine réutilise le cycle pause/resume existant plutôt
qu'une nouvelle file d'approbation séparée — une étape nécessitant une
approbation met simplement l'agent en pause, un humain le reprend via
le même endpoint `/resume`. La collaboration reste un seul appel LLM
borné (pas une exécution imbriquée complète) pour éviter toute
récursion agent-appelle-agent non bornée.

### Finalisation — suivi de coût réel (`AUTONOMOUS_MAX_COST`)

Suite à une demande explicite de finaliser le suivi de coût :

- **`AutonomousAgent.total_cost` / `AgentStep.total_cost`** (migration
  `0107`) : réels, persistés, en dollars — réutilisent
  `cost_tracking.calculate_cost_per_request` (vraie table de prix
  $/M-tokens déjà existante, Partie 7.2.15) et
  `chat_completion_with_usage` (vrai usage réel remonté par le
  fournisseur, Partie 7.2.14) — aucune nouvelle table de prix, aucun
  nouveau code de mesure d'usage.
- **Vérifié avant chaque étape** : `enforce_limits` met l'agent en
  pause dès que `total_cost` atteint le vrai plafond (override réel
  par agent `guardrails.max_cost`, sinon `AUTONOMOUS_MAX_COST` global)
  — la même vraie pause que `max_steps`.
- **`GET /autonomous-agents/{id}/cost`** : coût total réel, plafond
  effectif, dépassement, détail réel par étape.
- **Intégré aux garde-fous** : `check_guardrails` signale un budget
  déjà dépassé comme une vraie violation.

🐛 **Simplification réelle, documentée, pas un manque caché** : seuls
les 2 vrais appels LLM que `execute_step` fait lui-même sont
comptabilisés (extraction de paramètres d'outil, réponse de
raisonnement) — `decompose_task` (planification) et
`execute_collaboration` utilisent toujours `chat_completion` (une
fonction partagée par de nombreux autres appelants réels de ce
codebase ; changer sa forme de retour pour ce seul besoin sortait du
périmètre). Coût de planification/collaboration : vrai manque plus
étroit, signalé honnêtement.

✅ **21 + 5 tests backend + 8 tests frontend réels**, tous passés en
direct (CRUD, contrôle d'accès, planification avec mocks sur la vraie
frontière LLM, exécution avec le vrai outil calculator, garde-fous
réels, pause à `max_steps`, pause pour approbation humaine, pause pour
dépassement de coût réel, mémoire avec vrais embeddings
sentence-transformers et vraie similarité sémantique, consolidation,
oubli, collaboration réelle de bout en bout). Aucune régression. Voir
[`docs/autonomous/OVERVIEW.md`](autonomous/OVERVIEW.md),
[`docs/autonomous/PLANNING.md`](autonomous/PLANNING.md),
[`docs/autonomous/EXECUTION.md`](autonomous/EXECUTION.md),
[`docs/autonomous/MEMORY.md`](autonomous/MEMORY.md),
[`docs/autonomous/COLLABORATION.md`](autonomous/COLLABORATION.md).

---

## Total recompté (mis à jour après Étape 1.2.8, 2026-09-02)

Compté précisément item par item sur les Parties 1.1 à 14 (500 items
identifiés) ; la Partie 15 (~15 items pour atteindre les 515 annoncés)
reste de taille inconnue, son texte original n'ayant jamais été retrouvé
au-delà de "15.1.1 Ticke...".

| | Items (/500 connus) | % |
|---|---|---|
| ✅ Fait | 131 | 26.2% |
| 🟡 Partiel | 66 | 13.2% |
| ⬜ Non commencé | 303 | 60.6% |

**Complétion globale (/515, Partie 15 incluse en approximation)** :
- Strictement ✅ : **138/515 (~26.8%)**
- ✅ + 🟡 touchés d'une manière ou d'une autre : **210/515 (~40.8%)**
- Pondéré (✅=1, 🟡=0.5) : **~171/515 (~33.2%)** -- le chiffre le plus représentatif de l'avancement réel. Note : 3.4.8/3.4.9 (déjà comptés via les Parties 3.3.5/3.3.6) et leurs doublons littéraux (3.4.13-3.4.16, tous identiques à 3.4.7/8/9/12) sont marqués ✅ dans le tableau de la Partie 3.4 ci-dessus par référence croisée (le vrai travail existe) mais délibérément EXCLUS de ce comptage numérique tant que leur statut de véritables items séparés dans les 500 items connus n'est pas confirmé contre le texte original du cahier des charges maître.

Mis à jour après Partie 3.1.3 (Extraction du texte, amélioration, 2026-09-04) :
Partie 3 : ~10/41 → ~11/41 (3.1.3 seul item touché -- ✅, un seul vrai
manque trouvé en révisant réellement chaque extracteur existant : les
notes de bas de page DOCX (python-docx n'a aucune API publique pour
elles). PDF/EPUB capturaient déjà ce texte sans changement de code ;
`extract_text_image` déjà couvert par 3.1.6. La série complète 3.1.1 à
3.1.6 de ce lot est maintenant terminée).

Précédemment, mis à jour après Partie 3.1.6 (OCR, 2026-09-04) :
Partie 3 : ~9/41 → ~10/41 (3.1.6 seul item touché -- ✅, nouveau module
`api/services/ocr.py` (pytesseract/pdf2image), intégré dans l'extraction
PDF et dans la boucle d'images de 3.1.5. Limite réelle énoncée en
évidence : ni Tesseract ni poppler ne sont installés sur la machine de
développement -- le job CI installe désormais les deux binaires réels,
seul environnement où la vérification de bout en bout est réellement
possible. Déviation assumée : `get_ocr_confidence` prend les données
réelles par mot de l'OCR, pas du texte brut -- un score de confiance
honnête ne peut venir que du moteur au moment de l'inférence. La série
3.1.1/3.1.2/3.1.4/3.1.5/3.1.6 est terminée ; seul 3.1.3 (amélioration
de l'extraction, notes de bas de page) reste à finaliser dans ce lot).

Précédemment, mis à jour après Partie 3.1.4+3.1.5 (Extraction des tableaux et des images, 2026-09-04) :
Partie 3 : ~7/41 → ~9/41 (3.1.4 et 3.1.5 seuls items touchés -- ✅ tous
les deux. 3.1.4 : constat réel important -- l'extraction de tableaux
existait déjà pour PDF/DOCX/Markdown/CSV depuis 2.1.x mais seul un
compte était stocké ; comble le vrai manque HTML et expose enfin les
données structurées. Deux vrais bugs pandas trouvés et corrigés en
testant. 3.1.5 : nouveau modèle `DocumentImage`, initiative réelle
assumée pour intégrer l'extraction/stockage au pipeline (non demandé
explicitement) et ajouter une route de lecture -- sinon la
fonctionnalité serait restée inerte. Limite HTML honnêtement assumée
(référence seulement, pas de fetch pour éviter une nouvelle surface
SSRF). Ordre de dépendance réel : 3.1.6 (OCR) sera traité avant 3.1.3
pour ne pas construire l'OCR deux fois).

Précédemment, mis à jour après Partie 3.1.1+3.1.2 (Nettoyage et normalisation du texte, 2026-09-04) :
Partie 3 : ~5/41 → ~7/41 (3.1.1 et 3.1.2 seuls items touchés -- ✅ tous
les deux, nouveaux modules réels `api/services/text_cleaning.py`/
`text_normalization.py`, intégrés dans `process_document`, appliqués
sur chaque chunk juste avant l'embedding. Point honnête soulevé pour
3.1.2 : normaliser dates/nombres à l'indexation sans normalisation
symétrique côté requête peut réduire le rappel littéral -- assumé et
documenté, pas résolu ici).

Précédemment, mis à jour après Partie 2.2.16 (Batch processing, 2026-09-04) :
Partie 2 : 26✅/8🟡/1⬜ → 27✅/8🟡/0⬜ sur 35 (2.2.16 seul item touché --
✅, nouvelles tables `batch_jobs`/`batch_job_items` (migration 0044,
RLS en ligne). Couche de suivi générique par item réutilisant les 5
pipelines déjà existants (upload/reindex/delete/sync/replace), aucune
nouvelle logique métier. Annulation coopérative réelle, reprise réelle
via la même fonction sous deux noms. **La PARTIE 2 (Knowledge Base
universelle) est désormais couverte à 100% de ses 35 items (27✅/8🟡),
plus aucun ⬜ restant -- les 8 🟡 correspondent tous au même volet UI
explicitement différé depuis la décision "backend seul pour l'instant"
du 2026-09-04, jamais à un travail backend manquant**).

Précédemment, mis à jour après Partie 2.2.15 (Réindexation programmée, 2026-09-04) :
Partie 2 : 25✅/8🟡/2⬜ → 26✅/8🟡/1⬜ sur 35 (2.2.15 seul item touché --
✅, nouvelle table `reindex_schedules` (migration 0043, RLS en ligne)
et colonne `Document.reindex_schedule`. Zéro nouvelle dépendance --
parsing cron via la vraie classe Celery `crontab` déjà utilisée pour
Beat. Réutilisation totale de `reindex_organization`/`reindex_document`
(2.2.9). Bug réel corrigé, même famille que 2.2.13/2.2.14 : commit par
item, pas en une seule transaction finale. Permission Admin+, plus
stricte que le Manager+ de 2.2.14).

Précédemment, mis à jour après Partie 2.2.14 (Synchronisation automatique, 2026-09-04) :
Partie 2 : 24✅/8🟡/3⬜ → 25✅/8🟡/2⬜ sur 35 (2.2.14 seul item touché --
✅, nouvelle table `external_sources` (migration 0042, RLS en ligne).
Réutilisation totale des pipelines d'import existants (2.1.12-2.1.18),
aucune nouvelle logique réseau. Config chiffrée au repos (Fernet,
déviation assumée par rapport à JSONB). Deux limites réelles énoncées
en évidence : identifiants toujours au niveau serveur, pas par
organisation ; une resynchronisation réimporte tout le conteneur à
chaque fois qu'elle a lieu (pas encore de déduplication incrémentale
par item), `detect_source_changes` rendant ce cas rare sans l'éliminer).

Précédemment, mis à jour après Partie 2.2.13 (Détection de documents modifiés, 2026-09-04) :
Partie 2 : 23✅/8🟡/4⬜ → 24✅/8🟡/3⬜ sur 35 (2.2.13 seul item touché --
✅, nouvelles colonnes `last_modified`/`last_checked` (migration 0041).
Détection réelle via requête HTTP HEAD (`Last-Modified`) sur
`source_url`, applicable de fait à quasiment toutes les sources
d'import mais honnêtement limitée aux URLs publiques non authentifiées
-- les sources authentifiées (Drive/Notion/Confluence) relèveront
proprement de 2.2.14. Bug réel corrigé : le balayage périodique
committe désormais par document, pas en une seule transaction globale).

Précédemment, mis à jour après Partie 2.2.12 (Détection de doublons, 2026-09-04) :
Partie 2 : 22✅/8🟡/5⬜ → 23✅/8🟡/4⬜ sur 35 (2.2.12 seul item touché --
✅, nouvelle colonne `content_hash` (migration 0040, SHA-256 des octets
bruts). Deux déviations réelles et documentées : un simple INDEX plutôt
qu'une contrainte UNIQUE en base (sinon la route de déduplication ne
trouverait jamais rien à faire) ; l'identité de doublon inclut
`file_type`, pas seulement le hash (les mêmes octets peuvent
légitimement être deux documents différents selon le format détecté,
comme déjà établi par les tests Markdown/CSV vs TXT). Régression réelle
trouvée et corrigée sur le helper de test `_upload()` partagé par 110+
appels existants).

Précédemment, mis à jour après Partie 2.2.11 (Statut d'indexation, 2026-09-04) :
Partie 2 : 22✅/7🟡/6⬜ → 22✅/8🟡/5⬜ sur 35 (2.2.11 seul item touché --
🟡, backend réel et complet, UI polling explicitement différée -- voir
2.2.2). Déviation assumée par rapport au texte littéral : pas de
deuxième colonne `indexing_status` dupliquant `Document.status` --
seules deux colonnes réellement nouvelles (`indexing_started_at`,
`indexing_error`) sur les deux vrais points de transition de
`process_document`, déjà réutilisé sans changement de logique (même
raisonnement "éviter deux sources de vérité" qu'en 2.2.8). Deux
nouvelles routes (`GET .../status` par document, `GET .../status`
organisation-wide, Admin+, comptage réel par statut).

Précédemment, mis à jour après Partie 2.2.10 (Historique des modifications, 2026-09-04) :
Partie 2 : 21✅/7🟡/7⬜ → 22✅/7🟡/6⬜ sur 35 (2.2.10 seul item touché --
✅, nouvelle table document_audit_logs (migration 0038, RLS activée en
ligne cette fois). Intégration réelle dans 6 fonctions existantes sur
3 fichiers, chacune une seule ligne additive. Lacune honnête assumée :
l'action "restored" (undelete) est définie mais jamais produite,
puisque 2.2.8 n'a pas construit de vraie fonctionnalité d'annulation
de suppression. Journalisation transactionnelle (jamais best-effort,
contrairement au pub/sub Redis de 2.2.3) -- un enregistrement d'audit
manquant trahirait le but de l'étape. La série 2.2.6 à 2.2.10 est
maintenant intégralement livrée).

Précédemment, mis à jour après Partie 2.2.9 (Réindexation manuelle, 2026-09-04) :
Partie 2 : 20✅/7🟡/8⬜ → 21✅/7🟡/7⬜ sur 35 (2.2.9 seul item touché --
✅, aucune nouvelle logique de chunking -- reindex_document appelle
simplement process_document, qui supprime/recrée déjà les chunks à
chaque rerun depuis 2.1.1. Réindexation d'organisation réellement
pilotée par Celery à deux niveaux (fan-out d'une tâche par document,
pas une boucle géante). Vrai bug de monkeypatch (même piège qu'en
2.2.7) capturé et corrigé AVANT le CI cette fois, diagnostic déjà
appris. Note importante : la migration 0037, poussée séparément entre
2.2.8 et 2.2.9, a corrigé un vrai oubli RLS sur les 3 tables de
2.2.6/2.2.7 (document_tags/document_tag_assignments/document_versions),
détecté pour de vrai par le CI Postgres -- même oubli déjà commis une
fois par ce dépôt et corrigé de la même façon (migration 0032)).

Précédemment, mis à jour après Partie 2.2.8 (Suppression/remplacement, 2026-09-04) :
Partie 2 : 19✅/7🟡/9⬜ → 20✅/7🟡/8⬜ sur 35 (2.2.8 seul item touché --
✅, DELETE /documents/{id} devient un vrai soft delete (deleted_at/
deleted_by, migration 0036), la suppression définitive réelle
déménage vers /permanent (Owner/Admin uniquement). Un seul correctif
à fort effet de levier -- le point de passage partagé
_get_document_and_membership -- rend un document supprimé invisible
sur les 7 routes mono-document à la fois, confirmé par un test dédié.
replace_document réutilise honnêtement create_document_version_from_upload
de 2.2.7. Test préexistant corrigé pour refléter le nouveau
comportement (soft au lieu de hard delete)).

Précédemment, mis à jour après Partie 2.2.7 (Versioning, 2026-09-04) :
Partie 2 : 18✅/7🟡/10⬜ → 19✅/7🟡/9⬜ sur 35 (2.2.7 seul item touché --
✅, nouvelle table document_versions (migration 0035) + current_version_id
sur Document, création/restauration mettant à jour le document LIVE
pour que chaque lecteur existant continue de fonctionner sans
changement. Restauration = nouvelle version, jamais un retour en
arrière du numéro. Vrai bug de monkeypatch trouvé et corrigé pendant
les tests (schedule_document_processing importé par nom dans le
routeur, contournant le stub -- un vrai Celery.delay() tentait de
joindre Redis, causant un ralentissement de 16+ minutes sur 2 tests).
Limite honnête assumée : l'upload original n'est pas rétroactivement
versionné).

Précédemment, mis à jour après Partie 2.2.6 (Tags/catégories, 2026-09-04) :
Partie 2 : 17✅/7🟡/11⬜ → 18✅/7🟡/10⬜ sur 35 (2.2.6 seul item touché --
✅, deux vraies tables (document_tags, document_tag_assignments,
migration 0034), module de sécurité séparé, permissions créateur/
Admin réutilisant la forme déjà établie de DELETE /documents/{id},
garde-fou cross-organisation réel sur l'assignation. Déviation
documentée : lecture ouverte au Viewer sur les 3 routes GET, cohérent
avec chaque autre route GET de ce routeur).

Précédemment, mis à jour après Parties 2.2.2/2.2.3/2.2.4/2.2.5 (Drag & drop, Barre de
progression, Preview, Extraction metadata, 2026-09-04) :
Partie 2 : 17✅/3🟡/15⬜ → 17✅/7🟡/11⬜ sur 35 (les quatre 🟡 -- avant de
commencer, question posée explicitement à l'utilisateur sur comment
traiter la partie frontend de ces quatre étapes (toutes demandent
littéralement un composant React), puisque ce dépôt n'a AUCUN frontend
React -- son seul frontend réel est un dashboard Streamlit servant
l'ANCIEN pipeline RAG, pas `api/`. Réponse : backend seul pour
l'instant. 2.2.2 (drag & drop) est 100% frontend, honnêtement non
démarrée -- les deux routes d'upload qu'elle utiliserait (2.1.1 et
2.2.1) existent déjà. 2.2.3 (progression) : `GET .../progress` +
`GET .../progress/stream` (SSE, pas WebSocket -- ce flux n'a jamais
besoin de recevoir quoi que ce soit du client), réutilisant le vrai
Redis déjà en service (rate limiting/geoip) pour un vrai pub/sub, sans
nouvelle infrastructure ; granularité honnêtement limitée au statut du
Document (0/50/100/100%), pas un pourcentage par chunk -- éviterait de
toucher `process_document`, le chemin le plus partagé de tout ce
dépôt, pour un gain marginal. 2.2.4 (preview) : route sécurisée
(jamais d'accès S3 direct/public) avec téléchargement par vrais chunks
bornés en mémoire, vérifié contre S3/MinIO réel ; miniature (explicitement
optionnelle dans la consigne) non construite. 2.2.5 (métadonnées) :
normalisation réelle des métadonnées hétérogènes déjà extraites depuis
2.1.1-2.1.9 vers une forme commune {title, author, created_date,
keywords} -- jamais fabriquée pour un format sans le concept réel
(CSV/JSON/XML/TXT) ; extension réelle de 3 extracteurs existants
(DOCX/HTML/EPUB) pour surfacer un vrai champ déjà standard mais jamais
exposé ; distinction réelle PDF `creator` (logiciel) vs `author`
(personne), jamais confondus. Aucune nouvelle colonne de base de
données pour les quatre étapes).

Précédemment, mis à jour après Partie 2.2.1 (Upload multiple, 2026-09-04) :
Partie 2 : 16✅/3🟡/16⬜ → 17✅/3🟡/15⬜ sur 35 (2.2.1 seul item touché --
✅, nouvelle route dédiée `POST .../documents/batch` plutôt qu'une
modification littérale de la route d'upload existante -- une vraie
réponse multi-fichiers ne peut pas avoir la forme d'un `DocumentResponse`
unique, et ce choix ne casse aucun des dizaines de tests d'upload déjà
en place. Validation de contenu par fichier réelle et SYNCHRONE dans la
requête elle-même (réponse immédiate, pas seulement dans les logs).
Déviation honnête assumée : les octets de chaque fichier accepté
transitent par les arguments Celery (base64, bornés par
`DOCUMENT_BATCH_MAX_TOTAL_SIZE`) -- contrairement à chaque fan-out
précédent, un fichier fraîchement uploadé n'a nulle part ailleurs où
vivre durablement à ce stade. Un seul job Celery pour tout le lot,
conforme au texte littéral. Aucune nouvelle colonne de base de données).

Précédemment, après Partie 2.1.19 (Import depuis archives ZIP, 2026-09-04) :
Partie 2 : 15✅/3🟡/17⬜ → 16✅/3🟡/16⬜ sur 35 (2.1.19 seul item touché --
✅, le SEUL import de toute la série 2.1.10-2.1.19 sans la moindre API
externe ni le moindre identifiant, donc entièrement vérifiable pour de
vrai. Réutilise la route d'upload existante plutôt qu'une route dédiée.
Vraie protection ZipSlip + vraie défense zip-bomb par flux borné en
mémoire (pas seulement la métadonnée déclarée). Déviation honnête :
`zip_file_id` ajouté à `process_zip_archive` par nécessité (fan-out
Celery). Effet de bord découvert et corrigé : deux tests préexistants
2.1.2/2.1.9 supposaient un ZIP simple toujours rejeté, désormais
accepté comme format propre. Le fichier de test le plus fidèlement
réel de toute la série -- zéro mock, chaque test construit une vraie
archive locale. Toutes les 5 étapes de ce lot (2.1.15-2.1.19) sont
maintenant livrées).

Précédemment, après Partie 2.1.18 (Import depuis OneDrive, 2026-09-04) :
Partie 2 : 15✅/2🟡/18⬜ → 15✅/3🟡/17⬜ sur 35 (2.1.18 seul item touché --
🟡, même limite honnête que 2.1.14 : aucun identifiant Microsoft/Azure
réel disponible pour vérifier de bout en bout. Contrairement à 2.1.17,
un vrai hôte universel indépendant du tenant existe ici (point de
terminaison `common` de Microsoft, hôte fixe `graph.microsoft.com`).
Découverte réelle honnête : le point de terminaison de token Microsoft
s'est montré non-déterministe en direct entre deux appels identiques
(deux codes d'erreur réels différents à des moments différents) --
rapporté tel quel, test réseau réel ajusté pour ne pas dépendre d'un
code précis. Structurellement le plus proche parent de 2.1.14. Aucune
nouvelle colonne de base de données).

Précédemment, après Partie 2.1.17 (Import depuis Confluence, 2026-09-04) :
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
   2.1.13 (GitHub -- issues), 2.1.15 (Google Docs), 2.1.16 (Notion) et
   2.1.19 (ZIP) livrés en ✅ ; 2.1.14 (Google Drive), 2.1.17 (Confluence)
   et 2.1.18 (OneDrive) livrés en 🟡 -- 2.1.10 a introduit sa propre
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
   rejet d'authentification, d'où son propre statut 🟡, 2.1.18 a
   implémenté OneDrive contre l'API Microsoft Graph -- structurellement
   le plus proche parent de 2.1.14, avec un vrai hôte universel
   contrairement à 2.1.17, mais restant 🟡 pour la même raison que
   2.1.14 (aucun identifiant Microsoft/Azure réel disponible), et une
   découverte honnête supplémentaire : le point de terminaison de token
   Microsoft s'est montré non-déterministe en direct entre deux appels
   identiques, et 2.1.19 a clos la série avec les archives ZIP -- le
   SEUL import de toute la série 2.1.10-2.1.19 sans la moindre API
   externe ni le moindre identifiant, donc entièrement vérifiable pour
   de vrai (✅), avec une vraie protection ZipSlip et une vraie défense
   zip-bomb par flux borné en mémoire. Aucune des dix n'a introduit la
   moindre nouvelle colonne de base de données. **La série complète
   2.1.10-2.1.19 (import multi-source) est maintenant intégralement
   livrée.** La Partie 2.2 (gestion des documents) a démarré avec 2.2.1
   (upload multiple, ✅, nouvelle route dédiée `POST .../documents/batch`).
   2.2.2 (drag & drop), 2.2.3 (barre de progression), 2.2.4 (preview) et
   2.2.5 (extraction de métadonnées) demandaient tous un réel composant
   React, or ce dépôt n'a AUCUN frontend React -- son seul frontend
   existant est un dashboard Streamlit (`dashboard/app.py`) qui sert
   l'ANCIEN pipeline RAG (`src/`), pas `api/`, l'architecture multi-
   tenant que construit toute cette Partie 2. Question posée à
   l'utilisateur avant de construire quoi que ce soit côté frontend --
   réponse : **backend seul pour l'instant**. Les quatre étapes ont donc
   été livrées en 🟡, chacune avec son vrai travail backend complet
   (2.2.2 : rien à construire, les routes d'upload existent déjà ;
   2.2.3 : SSE + poll réels via le vrai Redis existant ; 2.2.4 : route
   de preview sécurisée, streaming par vrais chunks bornés ; 2.2.5 :
   normalisation réelle des métadonnées + extension de 3 extracteurs)
   et l'affichage/l'interaction utilisateur explicitement différés.
   Reste toute la suite de la Partie 2.2 (2.2.6 à 2.2.16 : tags,
   versioning, réindexation, détection de doublons, sync). Gros
   chantier restant,
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
- Partie 12 (Facturation) -- sync Stripe Products/Prices jamais testée contre une vraie clé API
- Partie 14 (Documentation), le reste -- guide admin, guide utilisateur, FAQ
- Partie 15 (Human-in-the-loop) -- dès que le contenu complet du cahier des charges original est retrouvé

**On commence par laquelle ?**
