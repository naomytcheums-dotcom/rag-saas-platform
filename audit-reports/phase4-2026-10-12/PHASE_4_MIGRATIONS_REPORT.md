# PHASE 4 — Cohérence des migrations (2026-10-12)

Suite de `../phase0-2026-10-12/` (MIG-001 à MIG-003, MIG-005, MIG-007). Tout a été exécuté sur des **bases jetables créées pour l'occasion** dans le conteneur local `rag-test-pg` (`rag_test_phase4_scratch`, `rag_test_phase4_fresh`, supprimées à la fin) avec `RAG_ENV_FILE=.no-env`. Aucune migration existante n'est modifiée ; la production n'est pas touchée ; rien n'est poussé ni fusionné.
Commit local : `6b855f9` (4 commits non poussés en tout : `c8fb325`, `d219f48`, `b0c3339`, `6b855f9`).

## 1. Prouvé (commandes exécutées)

| Vérification | Résultat |
|---|---|
| Chaîne complète `0001 → 0143` sur base vide | réussit ; une racine, une tête (`0143`), aucun doublon ni parent manquant |
| Schéma reconstruit à `0130` | **178 tables dont 12 sans RLS, 0 politique** : identique à l'observation de la base de production du 2026-10-06 (`docs/FINAL_STATUS.md`). C'est cohérent avec « production en 0130 », mais ne prouve pas la révision réelle |
| Chemin de production `0130 → 0143` avec 11 lignes réelles (2 utilisateurs, 1 organisation, 3 connexions SSO, 2 documents, 3 chunks) | réussit en **9 s** ; empreintes des colonnes d'origine **inchangées** (6 tables) ; 184 tables, 1 sans RLS (`alembic_version`), 0 politique |
| `downgrade 0143 → 0130` puis `upgrade head` | réussit ; retour exact à 178/12 puis 0143 ; schéma **identique** à une base migrée directement (seule différence : le jeton aléatoire `\restrict` écrit par `pg_dump`) |
| `0134` (domaine SSO) | seule la connexion créée par un superadmin reste vérifiée ; celle créée par un client et celle sans créateur passent à `domain_verified = false` et reçoivent un jeton : **leurs utilisateurs ne passent plus par le SSO tant que la preuve DNS TXT n'est pas refaite** (déjà annoncé par le runbook) |
| `0133` (déclencheurs BM25) | 9 déclencheurs, 3 fonctions ; le compteur augmente **par instruction** (1 pour 100 lignes) ; **contention mesurée** : une 2e transaction qui écrit pour la même organisation attend la fin de la 1re (**4 s**), une autre organisation 0,3 s |
| `scripts/migrate.py` (l'outil du runbook) sur la base remise en `0130` | répétition : « REHEARSAL PASSED », révision restée `0130` ; `--apply` : révision `0143` |
| Pilote RLS de l'autre branche, renuméroté `0144` (copie temporaire, rien écrit dans le dépôt) | s'applique sur `0143` (une seule tête `0144`), 6 politiques `tenant_isolation`, 0 `FORCE` ; aller-retour `downgrade -1` / `upgrade` correct |
| Collision `0137` | confirmée : sur `origin/main` seul la chaîne est saine ; avec le fichier du pilote tel que numéroté, le contrat signale « duplicate revision id 0137 » |

## 2. Ajouté au dépôt (commit `6b855f9`)
* `tests/test_migration_chain_contract.py` (3 tests, lecture des fichiers, sans base) : identifiant unique, numéro de fichier = identifiant, parents existants, pas de bifurcation, une racine et une tête, `downgrade()` présent. La chaîne réelle passe ; trois cas synthétiques (collision `0137`, deux têtes, parent absent, mauvais numéro, `downgrade` absent) sont détectés ; appliqué aux fichiers réels `origin/main` + pilote, il détecte la vraie collision. Il aurait empêché la fusion de la branche du pilote telle quelle.
* `docs/RELEASE_RUNBOOK_2026-10-11.md`, ligne `0133` : effet de contention mesuré et consigne de surveiller les verrous. La ligne 38 (caractère de contrôle) n'est toujours pas corrigée.

## 3. Constats nouveaux

| ID | Prio | Constat | Statut |
|---|---|---|---|
| MIG-009 | P1 | `0133` sérialise les écritures de `documents`, `document_chunks`, `media_assets` d'une **même organisation** jusqu'à la validation (verrou de ligne sur `organizations`). Avec une ingestion Celery concurrente et des transactions longues : débit réduit et risque de verrou mort selon l'ordre des écritures | Confirmé en base jetable ; impact sur le volume réel de production non mesuré |
| MIG-010 | P1 | Politiques du pilote RLS `TO PUBLIC`, alors que la décision de staging du 2026-10-03 (`RLS_STAGING_DECISION.md`) les voulait limitées à un rôle dédié. Inertes pour `postgres` (propriétaire, `BYPASSRLS`), mais applicables aux rôles Supabase `anon`/`authenticated` | Confirmé (fichier et catalogue) ; à trancher en phase RLS |
| MIG-011 | P2 | `0134` change le comportement de connexions SSO existantes (voir plus haut) | Confirmé ; à annoncer aux clients concernés avant la mise en service |

## 4. Ce qui reste non vérifié
* **La révision réellement appliquée à Supabase** (MIG-001) : toujours inconnue ; le schéma reconstruit à `0130` correspond à l'observation du 2026-10-06, mais le dossier de transmission déclare `0143` appliquée le 2026-10-11. Seule la requête `select version_num from alembic_version` (script de la phase 1) tranche.
* Le comportement de `0133` sous la charge réelle de production et le temps des migrations sur les vrais volumes (la base jetable ne contient que quelques lignes).
* Si Render ou Vercel suivent `main` (MIG-002) : non consultable.
* Documentation : je ne l'aligne pas sur une révision de production non établie.

## 5. Décisions qui attendent la propriétaire
1. **Renuméroter le pilote RLS en `0144`** (après `0143`) quand la branche de l'autre session sera intégrée : faisable et testé ; il ne faut jamais modifier l'existante. Cela implique de remplacer son `down_revision` et son identifiant dans le fichier du pilote, de ses tests et de son aller-retour `0137` (la CI de cette autre branche).
2. Politique `TO PUBLIC` ou rôle dédié (MIG-010).
3. Accepter ou non le risque de contention de `0133` avant la mise en service, ou demander une alternative (compteur par organisation hors du chemin d'écriture, ou mise à jour différée).
4. Résultat de `alembic_version` en production (toujours attendu).

## 6. Critères d'entrée de la phase 5 (corrections fonctionnelles et de sécurité)
* Pousser les 4 commits (CI à valider, coût CircleCI) ;
* décision sur les points 1 à 3 ci-dessus ;
* accord pour traiter ensuite : rédaction des journaux (SEC-009), `organization_id` signé dans les tâches Celery (TEN-005), les 19 fonctions sans appelant, les erreurs d'embeddings non converties (même défaut que celui corrigé pour les LLM).
