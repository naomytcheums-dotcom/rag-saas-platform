# 13 — Plan de travail priorisé

Audit du 2026-10-10. Plan **proposé**, rien n'a été exécuté. Chaque tâche : preuve, impact, dépendances, risque de régression, critères d'acceptation, méthode de vérification. Aucune tâche ne propose de supprimer une fonctionnalité pour simplifier le code ou faire passer des tests.

## P0 — sécurité, perte de données, facturation incorrecte, blocages d'usage sûr
| ID | Tâche | Preuve | Impact | Dépendances | Risque de régression | Critères d'acceptation | Vérification |
|---|---|---|---|---|---|---|---|
| P0-1 | **Décider et traiter l'isolation tenant en base** : soit documenter officiellement « isolation applicative » et ajouter un test de contrat par route, soit créer un rôle applicatif non contournant + `FORCE RLS` + politiques (`app.current_org`) sur les 80 tables à `organization_id` | R-01 ; 0 FORCE / 0 POLICY ; `0098` | Fuite inter-tenant si un filtre est oublié | décision produit ; rôle de base dédié ; nouvelle migration (ne jamais modifier les anciennes) | **Élevé** (toute requête sans contexte d'organisation échouerait) → déploiement progressif table par table | un utilisateur d'une organisation A ne lit/écrit rien de B même avec un `WHERE` omis, prouvé sur PostgreSQL jetable | test d'isolation PostgreSQL en CI (service `pgvector`), plus l'actuel `P0_PG_TEST_URL` rendu obligatoire |
| P0-2 | **Établir et fiabiliser l'exécution des tâches** : service worker Celery + beat dédié et supervisé (ou équivalent) ; vérifier le rattrapage des documents `pending` | R-02 | factures périodiques, crédits, purge RGPD, ingestion non garanties | hébergeur ; budget RAM (torch) ; Redis | Moyen (double exécution si deux beats) | une tâche périodique s'exécute à l'heure dite ; aucun document `pending` > N min ; une seule instance de beat | observation en staging ; test `celery_dispatch_fail_fast` ; alerte sur file/âge de tâche |
| P0-3 | **Processus de migration de production** : documenter qui lance `alembic upgrade head`, vérifier `alembic current` sur staging/read-only, appliquer 0136, sauvegarde avant | R-03, R-04 | routes de modèles de notification en 500 ; risque de migration à l'aveugle | accès base ; sauvegarde | Faible si sauvegarde + staging | `alembic current` = `0136` ; table `notification_templates` présente ; `GET /organizations/{id}/notifications/templates` ≠ 500 | commande en lecture + appel authentifié sur staging |
| P0-4 | **Sauvegarde/restauration prouvées** : un backup restauré dans une base jetable, RPO/RTO écrits | PROD-009 | perte de données | Supabase/plan | Faible | restauration réussie documentée avec date et durée | procédure rejouée |
| P0-5 | **Valider la facturation de bout en bout en sandbox** (Stripe test mode, Paystack test) : checkout, webhook, annulation, rejeu, événement tardif ; décider la politique de remboursement | R-05 | revenus/crédits erronés | clés **de test** fournies par la propriétaire ; endpoint webhook public de staging | Moyen | scénarios de `09` passent contre sandbox ; remboursement spécifié (état `refunded` ou interdiction explicite) | scripts d'intégration manuels + tests « live » activés en CI manuelle |
| P0-6 | Vérifier la **configuration réelle de production** sur les drapeaux sensibles (`CREDITS_ALLOW_UNPAID_TOPUP`, `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS`, `COOKIE_SECURE`, `METRICS_AUTH_TOKEN`, `MCP_STDIO_ENABLED`, `CLAMAV_ENABLED`) sans divulguer de valeur | R-10, P0-1 de `PRODUCTION_BLOCKERS.md` | crédits gratuits, métriques publiques | accès au tableau de bord Render | Aucun | tableau « variable → définie/absente → conforme » signé | revue manuelle |

## P1 — fonctionnalités essentielles incorrectes ou incomplètes
| ID | Tâche | Preuve | Dépendances | Risque | Acceptation | Vérification |
|---|---|---|---|---|---|---|
| P1-1 | **Mesurer la qualité RAG** sur un jeu de questions réel (Recall@1/3/5/10, MRR, NDCG, citations) avec l'Eval Lab existant ; consigner la ligne de base | R-06, code `retrieval_metrics.py` | un jeu annoté, clé LLM | Faible | une ligne de base chiffrée datée dans la doc | exécution reproductible (jeton, version de commit) |
| P1-2 | **Clarifier le chemin de recherche** (numpy vs HNSW), câbler ou retirer l'alternative non utilisée, câbler les stratégies de chunking annoncées ou corriger la documentation | `06` | P1-1 pour comparer | Moyen (qualité de recherche) | un seul chemin documenté, tests de dimension d'embedding | tests + comparaison de métriques avant/après |
| P1-3 | **Classer les 84 routes « sans auth détectée »** (publique légitime / protégée autrement / à protéger) et couvrir par un test paramétré qui échoue sur une route nouvelle non classée | `04_API_ENDPOINTS.csv` | — | Faible | liste blanche versionnée, test de contrat | pytest |
| P1-4 | **Tests PostgreSQL en CI** (service `pgvector`) pour verrous, RLS, concurrence, avec la garde jetable | `08`, R-05 | P0-1 | Moyen (durée CI) | tests opt-in exécutés et verts en CI | CI |
| P1-5 | **Remboursements et litiges** (BILL-016), **achat de crédits Paystack** ou refus documenté, **devises** (BILL-018), **plafonds atomiques** (BILL-012) | `09` | P0-5 | Moyen | selon décision | tests sandbox |
| P1-6 | **TEN-003 complet** : `asyncio.to_thread` ou client asynchrone pour les autres importeurs, timeouts boto3 courts | `11` (partiel) | — | Faible | aucun appel boto3 bloquant sur la boucle | test de thread comme `test_p2_ten003_*` |
| P1-7 | **Pages manquantes** : demande de restauration / réactivation / récupération 2FA | `05` (grep) | — | Faible | parcours complet depuis l'interface | vitest + essai manuel |
| P1-8 | Réexaminer les **122 constats « OUVERT (NON REVÉRIFIÉ) »** : reproduire chacun, fermer ou prioriser | `11` | — | Faible | registre mis à jour avec preuve par ligne | script de reproduction par constat |

## P2 — robustesse, tests, performance, observabilité
- P2-1 Aligner la documentation : `agents.md` (chemins d'API, version de Python), `render.yaml` (décrire l'API et le worker ou retirer l'ancien blueprint), cahier des charges (méthode de comptage reproductible, note GitHub Actions).
- P2-2 Réduire la durée des CI (< 40 min), générer la liste de tests CircleCI au lieu de la coder en dur ; distribuer les lots.
- P2-3 Benchmarks bornés et reproductibles : chargement des chunks par organisation, latence du chat, coût LLM ; fixer des plafonds de pagination.
- P2-4 Observabilité de production : alertes sur file Celery, échecs de webhook, erreurs 5xx, âge des documents `pending`, taux de refus RAG.
- P2-5 Mettre à jour les dépendances (Dependabot) une à une avec tests : **stripe 16, sqlalchemy 2.1, typescript 7** en dernier ; exécuter `npm audit` et `pip-audit` hors CI.
- P2-6 Mesurer la couverture du frontend et des SDK (aucune mesure aujourd'hui).
- P2-7 Nettoyer l'environnement de travail (branches/worktrees obsolètes) **sans toucher aux fichiers non suivis** sans accord.

## P3 — fonctions avancées, expérience, commercialisation
- P3-1 Parcours d'onboarding validé par un vrai utilisateur ; accessibilité et responsive audités.
- P3-2 Analyse concurrentielle (aucune recherche externe n'a été faite dans cet audit).
- P3-3 Conditions d'utilisation, confidentialité, support, SLA, page de statut.
- P3-4 Finaliser ou retirer les fonctions annoncées mais non câblées (chunking avancé, BeeAI/auto-évolution à documenter comme expérimentales).
- P3-5 Compléter ou clore la Partie 15 du cahier des charges (texte d'origine perdu : décision de la propriétaire).

## Ordre conseillé
P0-6 → P0-3 → P0-4 → P0-2 → P0-5 → P0-1 (en parallèle de P1-3/P1-4) → P1-1 → P1-2 → reste.
