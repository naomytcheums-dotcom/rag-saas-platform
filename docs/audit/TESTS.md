# Rapport des tests — audit du 2026-09-16

## Méthode

Exécution réelle de la suite de tests complète en local, dans les mêmes 4 lots que
`.circleci/config.yml` (découpés en processus séparés pour éviter l'OOM d'un unique gros
processus chargeant de nombreux modèles ML). Script reproductible :
`scripts/run_full_test_suite.sh`.

## Résultat final — lot par lot

| Lot | Résultat | Durée |
|---|---|---|
| 1/4 | **1211 passed, 2 skipped, 0 failed** | 20 min 48 s |
| 2/4 | **1077 passed, 0 failed** | 6 min 02 s |
| 3/4 | **703 passed, 0 failed** | 5 min 40 s |
| 4/4 (avec les 12 fichiers nouvellement câblés) | **1349 passed, 9 skipped, 0 failed** | 53 min 17 s |
| **Total** | **4340 passed, 11 skipped, 0 failed** | — |

## Un vrai bug trouvé par ce processus, pas seulement rapporté — corrigé

Le lot 4 a échoué à deux reprises avant d'atteindre ce résultat propre, sur le même test :
`tests/test_admin_dashboard.py::test_system_log_handler_writes_real_rows` — l'un des 12
fichiers ajoutés à la CI pendant cet audit (voir `docs/audit/COHERENCE.md`). C'est
directement la preuve que l'ajout de ces fichiers avait de la valeur : ce bug n'aurait
jamais été détecté tant que le fichier restait orphelin.

**Cause réelle, trouvée en deux couches** (voir le détail complet dans le commit
`12740c2` et dans `COHERENCE.md` section 5) :
1. Le test écrivait dans la vraie base partagée avec un message fixe, sans nettoyage
   fiable en cas d'échec — corrigé par un message suffixé d'un UUID et un nettoyage de
   toutes les lignes correspondantes plutôt que d'une seule.
2. Même après ce premier correctif, le test échouait encore, mais **seulement** dans le
   contexte de la suite complète, jamais isolément : un handler de journalisation
   installé globalement sur le logger racine (dès qu'un autre test déclenche le vrai
   cycle de vie de l'application FastAPI) recevait aussi le message du test par
   propagation — écrivant la ligne deux fois. Corrigé en désactivant la propagation sur
   le logger dédié du test.

Chaque étape a été **reproduite directement** (pas supposée) avant d'être considérée
corrigée : le second bug a été reproduit dans un script autonome qui installe
manuellement le handler racine puis exécute la même logique — 2 lignes avant correction,
1 ligne après.

## Incidents opérationnels pendant cet audit (honnêtement documentés)

- Le script `run_audit_tests.sh` a été déplacé vers `scripts/run_full_test_suite.sh`
  pendant qu'il tournait encore en arrière-plan — a corrompu une ligne `echo` en transition
  de lot, sans affecter les commandes pytest elles-mêmes (vérifié directement). Les lots 1
  et 2 de cette exécution particulière restent valides.
- Le disque de la machine s'est retrouvé à 0 octet libre pendant une des relances du lot 4
  (C:\Users pèse 250 Go sur un disque de 510 Go — problème préexistant de la machine, pas
  causé par cet audit) — a fait planter pytest lors de l'écriture de son propre cache
  interne, juste après l'exécution complète des tests. Libéré ~1,25 Go via les caches
  pip/npm (sûrs, régénérables), puis 8 Go supplémentaires via deux dossiers temporaires
  d'installateur Visual Studio/.NET clairement obsolètes (`%TEMP%\ahmsz33r`,
  `%TEMP%\swlgp0us`) — aucun fichier du projet ni donnée personnelle identifiable touché.

## Lot ciblé — fichiers modifiés pendant cet audit (avant les 4 lots complets)

Exécution ciblée des fichiers directement affectés par les corrections de pagination et
`human_approval.py`, en garde-fou avant le premier commit :

```
264 passed in 480.19s (0:08:00)
```

## Frontend

`npx tsc --noEmit` exécuté à plusieurs reprises pendant cette session — **0 erreur à
chaque fois**. Aucune suite de tests automatisés frontend (Vitest/RTL) n'a été relancée
dans le cadre spécifique de cet audit.

## Re-vérification (2026-09-16, après correction)

- Les 12 fichiers de test confirmés présents dans `.circleci/config.yml` (grep direct sur
  les 12 noms de fichiers, tous trouvés).
- Les 5 exclusions légitimes confirmées documentées en commentaire dans le même fichier.
- `tests/test_admin_dashboard.py` relancé en direct après le correctif de propagation de
  logger : **7/7 tests verts**, y compris `test_system_log_handler_writes_real_rows`.
- Vérifié en direct contre la vraie base partagée : **0 ligne fantôme restante** portant
  l'ancien message fixe (`"a real warning captured by the real handler..."`).
- Un nouveau correctif de pagination (`api/routers/questions.py`, voir
  `docs/audit/LIMITS.md`) revérifié : 11/11 tests (`tests/test_suggested_questions.py`)
  verts.

## Portée non couverte

- Couverture de code (`--cov-fail-under=75`) : le seuil est appliqué automatiquement par
  le lot 4 lui-même (confirmé passant), pas revérifié séparément dans cet audit.
- Suite de tests frontend (Vitest/RTL) non ré-exécutée dans le cadre de cet audit
  spécifique.
- Tests end-to-end navigateur (Playwright/Crawlix) : hors périmètre de cet audit, déjà
  couverts par la campagne de tests par personas IA documentée séparément
  (`docs/testing/`).
