# PHASE 3 — Isolation multi-tenant : partie code (2026-10-12)

Suite de `../phase0-2026-10-12/PHASE_0_READ_ONLY_SECURITY_AUDIT.md` (TEN-003, TEN-004, TEN-005, TEN-006). Périmètre appliqué : revue des 77 recherches par identifiant, tests d'isolation A/B, corrections de code. **Non fait** : rôle de base, politiques RLS, migrations, staging (exigent la propriétaire et Supabase). Rien n'est poussé ni fusionné.
Commit local : `b0c3339` (avec `c8fb325` et `d219f48` : 3 commits non poussés).

## 1. Résultat principal : 3 défauts réels d'isolation, corrigés et prouvés

Classe de défaut : la route autorise l'appelant sur `org_id` **du chemin**, puis passe un autre identifiant du même chemin à un service qui charge l'objet **par cet identifiant seul**. Un administrateur d'une organisation B agit alors sur un objet de l'organisation A (s'il connaît l'UUID).

| # | Route | Effet démontré par le test (avant correction) | Correction |
|---|---|---|---|
| 1 | `DELETE /organizations/{org_id}/api-keys/{key_id}` | **204** : la clé d'API d'une autre organisation est révoquée | `revoke_api_key(..., organization_id=org_id)` ; clé étrangère → 404 |
| 2 | `DELETE /organizations/{org_id}/rbac/users/{user_id}/roles/{role_id}` | l'affectation de rôle personnalisé d'un utilisateur d'une autre organisation est supprimée | rôle lié à l'organisation (comme toutes les fonctions sœurs), membre vérifié, 404 sinon |
| 3 | `GET` / `PATCH /organizations/{org_id}/security/vulnerabilities/{vuln_id}` et `POST …/alerts/{alert_id}/dismiss` | lecture, changement de statut et fermeture sur des objets d'une autre organisation | filtre par l'organisation du scan / de l'alerte ; 404 sinon |

* **Preuve** : `tests/test_p3_org_path_object_binding.py` (2 tests) et `tests/test_p3_api_key_tenant_isolation.py` (1 test) sont des tests A/B (deux organisations réelles). Le test RBAC et le test du scan de sécurité **échouent sans la correction** ; le test des clés échouait aussi sur la révocation (204) avant la correction. Avec la correction : 107 tests passés, 11 ignorés (tests de staging réel) sur 20 fichiers voisins ; `ruff` propre. Chaque test comporte des contrôles positifs : l'administrateur légitime peut toujours agir.
* **Balayage reproductible** (`scan_path_org_with_object_id.py`) : appliqué au code **non corrigé** (HEAD), il signale exactement ces 5 routes ; après correction il ne signale plus rien. Limite : il ne détecte que ce motif textuel (parent du chemin absent du corps de la route).
* **Les mêmes défauts existent sur `origin/main`** (code identique ; route des clés d'API depuis 2026-09-09, route RBAC depuis 2026-09-10). Si `main` est déployé, ils sont actifs. La correction n'est que sur cette branche locale.
* Gravité : élevée en intégrité/disponibilité (révocation de clés d'une autre organisation, retrait de rôles), atténuée par le fait qu'il faut connaître des UUID non devinables. Aucun accès à des secrets : la clé en clair n'est jamais renvoyée par ces routes.
* Fiches pour le registre : **TEN-011** (clés d'API), **TEN-012** (RBAC), **TEN-013** (scan de sécurité / alertes), statut *Confirmé et corrigé sur la branche, non déployé*.

## 2. Revue des 77 recherches par identifiant (TEN-004)

Méthode : graphe d'appels statique (`triage_candidates.py`, sortie `candidate_triage.csv`). « Protégé » = un contrôle d'organisation ou de propriété est **présent** chez l'appelant (pas prouvé correct).

| Verdict | Nombre | Lecture |
|---|---|---|
| Protégé en amont | 46 | présence d'un contrôle sur tous les chemins vers un point d'accès |
| Aucun appelant trouvé dans l'application | 19 | code mort ou appelé dynamiquement (ex. `delete_conversation` ×2, `get_chunk_content`, 5 fonctions de `message_actions`, 3 de `organization_api_keys`) : **risque latent**, non exploitable aujourd'hui |
| Atteint par une tâche Celery | 11 | confiance dans l'identifiant du message de file (TEN-005) |
| Point d'accès sans marqueur | 1 | `GET /share/{token}` : lien public par jeton `secrets.token_urlsafe(32)`, expiration et nombre de vues ; conception voulue |

Mise en file des tâches (`triage_task_enqueuers.py`, `task_enqueuer_triage.csv`) : 45 sites ; 0 dans un point d'accès non gardé ; sur 18 fonctions de planification sans marqueur propre, 15 sont atteintes uniquement par des chemins gardés, 2 sont des tâches internes, 1 est `POST /webhooks/{trigger_id}` (workflows) authentifié par un jeton propre au déclencheur comparé en temps constant (`secrets.compare_digest`).

## 3. Couverture A/B ajoutée sans défaut trouvé
`tests/test_p3_eval_lab_tenant_isolation.py` : 21 routes de l'Eval Lab (11 lectures, 10 écritures : métriques, comparaisons, régressions, versions, jeux de questions, import, découpage, comparaisons de prompts/rerankers/retrievers) que `test_evaluation_idor.py` ne touchait pas. Tous les appels de l'attaquant sont refusés (404), rien n'est écrit, aucun job n'est lancé ; les contrôles du propriétaire obtiennent 200/201 (ou 422 pour un corps volontairement vide). Cela ne prouve que ces routes ; c'est un garde de non-régression.

## 4. Non fait, par dépendance ou décision
| Élément | Raison |
|---|---|
| Rôle applicatif sans `BYPASSRLS`, politiques RLS, contexte `app.current_org` | exige Supabase / staging, la décision D2/D8 et la résolution de la collision `0137` ; aucune migration écrite |
| Tâches Celery : passer et vérifier `organization_id` signé | changement de conception des messages de file ; à valider (compatibilité des tâches en vol) |
| 19 fonctions sans appelant : ajouter le paramètre d'organisation ou les retirer | suppression interdite sans analyse et accord ; à lister dans le registre de fonctionnalités |
| Classification des 77 tables à tenant indirect (TEN-006) | revue de domaine avec la propriétaire |
| A/B sur les autres domaines (documents, conversations, workflows, facturation) | déjà couverts par des tests existants (`test_document_idor`, `test_workflow_idor`, `test_billing_idor`, `test_p0_chat_conversation_isolation`…), non réexaminés route par route |
| Autres variantes du défaut (autorisation sur un parent différent de l'organisation, services qui acceptent mais ignorent l'organisation) | le balayage couvre 11 parents (org, agent, espace, jeu de données, workflow, conversation, équipe, document, projet, intégration, canal) mais reste textuel ; non exhaustif |

## 5. Décisions et actions
1. **Pousser la correction** (3 commits) vers la PR #25 puis fusionner dès que la CI est acceptable : tant que `main` n'a pas ce correctif, les trois défauts sont présents dans le code de `main`. Le déclenchement du déploiement de production reste non vérifié.
2. Résultat des requêtes de lecture seule de la phase 1 (révision, rôle) : toujours attendu.
3. Autoriser la conception « organisation signée dans les tâches » et la revue des 19 fonctions sans appelant.
4. Décider la collision `0137` avant toute politique RLS.

## 6. Critères d'entrée de la phase 4 (cohérence des migrations)
* Révision réelle de la base (`alembic_version`) ; * choix entre renuméroter le pilote RLS ou l'intégrer après `0143` ; * accord pour travailler uniquement en base jetable (aller-retour `0130 → 0143`), sans toucher à la production.
