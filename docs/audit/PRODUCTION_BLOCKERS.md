# Production Blockers — Initial

Date : 2026-10-03. Cette liste reflète le code/workspace présent; elle ne
prétend pas décrire la configuration réellement déployée. Les deux corrections
autorisées après l'audit initial sont consignées ci-dessous.

## P0 — Bloquer la validation de mise en production

### P0-1 — Vérifier que la production n'active pas les recharges gratuites

- **Correctif local appliqué :** `api/config.py` utilise maintenant le défaut
  fermé `CREDITS_ALLOW_UNPAID_TOPUP=False`; les top-ups self-hosted restent
  possibles uniquement par opt-in explicite.
- `api/routers/billing.py:176-196` : achat direct autorisé lorsqu'aucun
  provider n'est résolu et que le flag reste actif.
- **Risque :** création de crédits sans paiement; coût LLM/storage transféré
  à la plateforme.
- **Vérification locale :** `tests/test_config.py` vérifie le défaut fermé et
  `tests/test_billing.py` couvre le endpoint; inclus dans 51 tests ciblés
  réussis.
- **Condition résiduelle :** la configuration effective déployée n'a pas été
  lue/vérifiée. Une surcharge de l'environnement peut encore activer ce mode.
- **Critère de sortie production :** démontrer, sans divulguer de secrets,
  qu'un provider réel est obligatoire ou que le flag est désactivé; vérifier
  checkout/webhook avec un environnement sandbox isolé.

### P0-2 — Révision de la base réelle inconnue

- `alembic heads` identifie `0131`; `alembic current` termine en échec avec le
  code 1. Aucune version appliquée n'a été établie.
- **Risque :** incompatibilité code/schéma et migrations supposées appliquées
  sans preuve.
- **Critère de sortie :** vérifier l'accès à une base de staging/read-only,
  obtenir la version, comparer le schéma et la sauvegarde, contrôler les
  migrations en attente. Ne pas lancer une migration de production à l'aveugle.

## P1 — Bloquer le parcours concerné avant activation commerciale

### P1-1 — Vérifier le débit A2A sur PostgreSQL après correction

- **Correctif local appliqué :** le préflight vérifie le coût forfaitaire
  complet; le débit verrouille et actualise la ligne de solde avant l'appel
  agent. BYOK n'est pas débité.
- **Vérification locale :** le test de solde inférieur au coût confirme HTTP
  402 sans appel agent; un autre test constate le débit avant l'appel et un
  test vérifie le rollback de la réservation sur échec. `tests/test_a2a_router.py`
  est inclus dans les 84 tests ciblés réussis.
- **Condition résiduelle :** exécution sur PostgreSQL pour confirmer le verrou,
  essais concurrents et intégration A2A réelle non effectués.

### P1-2 — RLS ne protège pas le rôle API

- Tests de référence : `tests/test_postgres_integration.py`; RLS activé mais
  aucune policy, rôle API contournant RLS.
- **Risque :** aucune barrière de base contre une régression d'autorisation
  inter-tenant.
- **Critère de sortie :** revue de la stratégie de rôles/policies et tests
  d'isolation DB sur deux organisations avec rôles distincts, après conception
  compatible avec les travailleurs et migrations. Aucun accès croisé ne doit
  réussir.

### P1-3 — Worktree non isolé et fortement modifié

- État initial : branche `main`, 130 fichiers suivis modifiés et 140
  non suivis, y compris des routes et migrations.
- **Risque :** l'état à auditer ou livrer n'est pas équivalent au HEAD et son
  historique est incomplet.
- **Critère de sortie :** inventorier et sauvegarder le travail préexistant,
  confirmer sa provenance, séparer le travail de livraison sans écraser ni
  supprimer ces changements.

## P2 — Fiabilité et preuve insuffisantes

- `.github/workflows/celery-worker.yml` neutralise l'échec worker avec
  `|| true`; rendre les échecs actionnables.
- La vérification 0132 est dans `scripts/pending/`, hors du graphe Alembic;
  inspecter modèle/API/migration et n'intégrer que par le processus normal.
- Les mesures RAG documentées ne démontrent pas 10k/50k documents,
  pgvector/HNSW, p95/p99 ou utilisateurs concurrents; le README indique que
  BM25 balaie les chunks de l'organisation.
- Aucun parcours réel document→retrieval, payment→webhook→ledger,
  workflow/Celery ou SDK→API n'a été démontré pendant cette phase.
- Ruff signale des défauts statiques préexistants sur les surfaces ciblées :
  huit champs Settings redéclarés dans `api/config.py`, les appels FastAPI
  `Depends` correspondant à B008 et des imports/variables inutilisés dans les
  tests billing/A2A. Les sous-contrôles ciblés des nouveaux changements passent;
  les défauts hors périmètre n'ont pas été corrigés.
- Une tentative initiale de test a sollicité Resend avec une adresse
  `example.com` rejetée en HTTP 422; les helpers de tests billing/A2A isolent
  maintenant cet envoi. Vérifier les autres suites avant de les lancer avec
  des credentials réels.

## Conditions générales de levée

1. Garder secrets et jeux de données hors des rapports et commits.
2. Tester les changements dans une base et des services isolés; sauvegarder
   avant tout essai de migration.
3. Ne classer une intégration `VERIFIED` qu'après résultat réel reproductible,
   avec credentials non exposés.
4. Publier les résultats et preuves de test dans les rapports d'audit après
   chaque phase, sans remplacer l'état historique ni inventer des métriques.

## Validation des corrections locales

`pytest tests/test_a2a_router.py tests/test_billing.py
tests/test_billing_credits_spend_caps.py tests/test_config.py
tests/test_agent_orchestrator_credit_preflight.py tests/test_agent_factory.py
tests/test_rag_control_plane_router.py -x` : **84 passed**, deux avertissements
de coroutines `ActiveTask`.

Les contrôles `ruff check api/services/billing_credits.py tests/test_config.py`
et `ruff check --select I api/routers/a2a.py` passent. Ruff sur l'ensemble des
fichiers ciblés retourne 19 constats préexistants (8 champs dupliqués, 6
FastAPI `Depends` B008, 1 import inutilisé dans A2A tests, 4 imports non triés
et une variable inutilisée dans les tests billing); ils restent ouverts et
hors des deux corrections autorisées.
