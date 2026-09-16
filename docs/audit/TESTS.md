# Rapport des tests — audit du 2026-09-16

## Méthode

Exécution réelle de la suite de tests complète en local, dans les mêmes 4 lots que
`.circleci/config.yml` (découpés en processus séparés pour éviter l'OOM d'un unique gros
processus chargeant de nombreux modèles ML — voir le commentaire de ce fichier). Script
reproductible : `scripts/run_full_test_suite.sh`.

## Résultat — lot par lot

| Lot | Résultat | Durée |
|---|---|---|
| 1/4 | **1211 passed, 2 skipped, 0 failed** | 20 min 48 s |
| 2/4 | *voir note ci-dessous* | — |
| 3/4 | *voir note ci-dessous* | — |
| 4/4 (incluant les 12 fichiers nouvellement câblés, voir COHERENCE.md) | *voir note ci-dessous* | — |

**Incident opérationnel pendant cet audit** : le script `run_audit_tests.sh` a été
déplacé vers `scripts/run_full_test_suite.sh` (rangement propre) alors qu'il tournait
encore en arrière-plan pour le lot 1 — l'interpréteur bash a lu une ligne corrompue au
moment de la transition vers le lot 2 (`echo '--- batch 2/4 ---'` tronqué), mais la
commande pytest du lot 2 elle-même s'est lancée correctement avec la liste de fichiers
complète et exacte (vérifié directement via la ligne de commande du processus). Le lot 1
(1211/1211 réussis) est un résultat propre et fiable, identique au résultat de référence
d'une exécution précédente dans cette même session. Les lots 2 à 4 ont été relancés
proprement après l'incident — voir la mise à jour ci-dessous une fois terminés.

## Lot ciblé — fichiers modifiés pendant cet audit

Avant même le lancement des 4 lots complets, une exécution ciblée des fichiers de test
directement affectés par les corrections de cet audit (limite de pagination sur 12
routers, réordonnancement de `human_approval.py`, plus les fichiers auparavant orphelins
`test_billing.py`/`test_admin_*.py`/`test_observability.py`/`test_compliance.py`) a été
lancée séparément et a servi de garde-fou avant tout commit :

```
264 passed in 480.19s (0:08:00)
```

0 échec. C'est ce résultat qui a validé les corrections avant leur envoi sur `main`
(commit `a02d5ac`).

## Suite pytest orpheline — corrigée

Voir `docs/audit/COHERENCE.md` section 2 pour le détail complet : 12 fichiers de test
réels (264 tests) n'étaient référencés dans aucun lot CircleCI — corrigé, ajoutés au lot
4. 5 autres fichiers restent délibérément exclus, pour des raisons désormais documentées
directement dans `.circleci/config.yml`.

## Frontend

`npx tsc --noEmit` exécuté à plusieurs reprises pendant cette session (après la traduction
du tableau de bord, après le remplacement du widget Google Translate, après l'ajout des
sections Tarifs/Sécurité/FAQ) — **0 erreur à chaque fois**. Aucune suite de tests
automatisés frontend (Vitest/RTL) n'a été relancée dans le cadre spécifique de cet audit
— `docs/integrations/PARTIE_15_ADVANCED_INTEGRATIONS.md` mentionne que l'installation de
Vitest/RTL a été faite pour un composant spécifique (`components.test.tsx`), mais une
exécution complète de cette suite n'a pas été demandée ni relancée ici.

## Portée non couverte

- Couverture de code (`--cov-fail-under=75`) : non vérifiée séparément dans cet audit —
  le seuil est déjà appliqué automatiquement par le lot 4 de la CI elle-même.
- Suite de tests frontend (Vitest/RTL) non ré-exécutée dans le cadre de cet audit
  spécifique.
- Tests end-to-end navigateur (Playwright/Crawlix) : hors périmètre de cet audit, déjà
  couverts par la campagne de tests par personas IA documentée séparément
  (`docs/testing/`).
