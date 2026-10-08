# Audit autonome 05 — modifications de cette mission

Date : 2026-10-03. Branche `bob/auto-fix-20261003-191324`, HEAD de base
`2e7bfaa3c3fbca3b1a66ad26f9c9ce5ad19d15a2`.
Le worktree contenait déjà de nombreux changements; aucun reset/revert,
aucune migration historique modifiée, aucun commit ni push dans cette mission.

## Correctifs réalisés

| ID | Cause / modification | Fichiers | Validation |
|---|---|---|---|
| ENV-1 | Settings chargeait systématiquement `.env` principal. Sélection opt-in `RAG_ENV_FILE`, défaut ancien conservé. | `api/config.py` | tests config et garde-fous ciblés verts |
| ENV-2 | Ancien loader RAG utilisait `.env` même pour exécution isolée. Même sélection explicite, sans fallback si fichier absent. | `src/generation.py`, `tests/test_dotenv_selection.py` | 2 tests nouveaux passés |
| STG-1 | Absence de profil ignoré staging et allowlist stricte. Template et validation host/driver/port/user/DB/query. | `.gitignore`, `.env.staging`, `scripts/staging_target.py` | check-ignore; 9 tests URL passés |
| STG-2 | Commandes de migration/test/backup non isolées. Runner explicite, SSL, credentials jamais dans argv, environnement filtré. | `scripts/staging_validate.py` | dry-run, refus closed, Ruff; live bloqué |
| STG-3 | Absence de tests PostgreSQL dédiés A/B. Fixtures rollback/savepoint et tests API/RLS rôle non-BYPASS. | `tests/staging_support.py`, `test_staging_idor.py`, `test_staging_full_idor.py` | 11 cas collectés/skippés, aucun PASS live |
| UI-1 | Initialisation dérivable de prompt via setState dans effect déclenchait erreur ESLint. Initialisation lazy useState, `t` dans dépendances du loader. | `frontend/app/dashboard/agents/page.tsx` | lint sans erreur, type-check, 112 tests frontend passés |
| UI-2 | Deux guillemets JSX non échappés. Entités `&quot;`, texte rendu identique. | `frontend/components/eval/FailureAnalysis.tsx` | lint sans erreur et suite frontend verte |
| INV-1 | FastAPI 0.141 diffère : routers inclus différés, parcours brut `app.routes` sous-comptait les routes. Générateur utilise les route contexts effectifs. | `scripts/audit_inventory.py` | 936 opérations, correspondant à OpenAPI actuel; 177 tables ORM |
| DEP-1 | Collection backend échouait : ChromaDB, googleapiclient, mem0, Streamlit absents. Restauration des versions déjà déclarées seulement. | `.venv` seulement, aucun manifest modifié | `pip check` vert; collection suivante 5 335 cas |
| ENV-3 | Le profil isolé manquait de clés de chiffrement et des bibliothèques tierces pouvaient auto-charger dotenv. Clés Fernet/AES locales éphémères et PYTHON_DOTENV_DISABLED explicite. | `scripts/staging_target.py`, `tests/test_staging_target.py` | Guard/config/loader et frameworks : 34 pass; test réel du refus dotenv tiers |
| DEP-2 | Imports média/observabilité/frameworks manquants. Restauration des pins manifest, sans remplacer PyTorch CPU. | `.venv` seulement | Média/Sentry/lineage : 40 pass, 11 skips staging; BeeAI/Graph RAG rejoués verts; pip check vert |

Les 11 lignes ci-dessus décrivent des actions techniques, pas 11
vulnérabilités. Les 125 échecs du run complet sont analysés dans le
[rapport de tests](./AUTONOMOUS_AUDIT_06_TESTS.md) : 104 ont depuis un
rejeu passant, sans prétendre que la suite complète est devenue verte.

## Décisions de non-modification

- 3 253 diagnostics Ruff initiaux ne sont pas tous des bugs; pas de
  suppression massive de règles, d'imports/types ou de fonctionnalités.
- Les dix F821 du relevé étaient des noms d'annotations/modèles déclarés
  sous forme forward references; aucune preuve que chaque occurrence est
  une erreur runtime exploitable. Pas de correction spéculative.
- Les modèles RLS indirects/global/system ne sont pas convertis à une
  policy générique. Pas de grants PUBLIC ou rôle runtime modifié.
- Secret partagé dans le chat non recopié dans le fichier ou les rapports;
  provisioning sûr et rotation externe restent bloquants.
- Aucun SDK vocal intégré; étude/clone externe/plan uniquement.

## Limites

Les tests frontend ne prouvent pas le fonctionnement de providers ou DB.
Les tests staging skippés ne sont pas « sécurisés ».
Le run backend complet et l'audit spécialisé sont rapportés séparément
avec leurs résultats réels, jamais avec un PASS présumé.

## Lot du 2026-10-04 — runner et dépendances

- Défaut reproduit : `python -m scripts.staging_validate dns` levait
  ModuleNotFoundError avant toute action. Import relatif en mode module,
  import local conservé en mode script; pas de catch qui masque l'erreur.
- Deux tests nouveaux exercent les deux entrypoints en dry-run :
  guard/config/loader **22 passed en 23.39 s**, Ruff ciblé PASS.
- Après correction, DNS staging retourne toujours 11001 :
  problème réseau distinct, aucune connexion ou migration exécutée.
- DSPy utilisé par le service n'était pas déclaré : pin `dspy==3.4.0`
  ajouté au manifest API. Validation des tests DSPy encore en attente.
- Résolution conjointe Docling/Presidio/DeepEval/DSPy compatible avec les
  pins Transformers 5.16.1, sentence-transformers 5.7.0 et Torch
  2.13.0+cpu : dry-run PASS. Versions transitives proposées :
  NumPy 2.4.6, Click 8.3.3, Typer 0.26.8, Rich 14.3.4,
  huggingface-hub 1.16.1. Installation réussie, pip check PASS;
  groupe SDK/extraction/guard **63/63 passé sans skip**.
- Les huit échecs initiaux DSPy/DeepEval/Docling ont un rejeu passant;
  PII reste en cours. Aucun test historique modifié/supprimé.
- Résultat PII reçu ensuite : 4/4 sans skip, détection/masquage avec
  modèle officiel en_core_web_lg 3.8.0. Pip check PASS.

## Travail indépendant pendant la suite complète — CI Celery

- Cause confirmée : `.github/workflows/celery-worker.yml` terminait la
  commande worker par `|| true`, masquant les erreurs de démarrage,
  d'exécutable et de terminaison.
- Correction : propager les codes inattendus, accepter seulement 0
  et 124 (fin de fenêtre programmée). TERM demande l'arrêt warm;
  SIGKILL après 60 s ne produit pas une réussite.
- Régression : neuf cas 0/1/2/124/125/126/127/137/143 exécutent le vrai
  bloc Bash du YAML avec seulement la commande timeout substituée.
  **9 passed en 1.43 s**, Ruff PASS. Aucun worker/broker/DB lancé.
- Première validation locale : 8 échecs dus au launcher Bash WSL Windows
  altérant les arguments. Le nouveau test utilise Git Bash natif sous
  Windows; après correction du harness, les neuf cas passent.
- Aucun lancement du workflow GitHub, aucun déploiement ni secret utilisé.
  Cela ne prouve pas que chaque tâche Celery réussit; le code de sortie
  du worker n'est pas le résultat des tâches individuelles.
- Le run backend déjà lancé ne contient pas ce nouveau fichier collecté
  après son démarrage; les neuf tests sont une validation séparée.

## Backup/restore — correctifs indépendants du run backend

- `scripts/backup.sh` publiait immédiatement le nom final, même si
  pg_dump échouait et ne produisait qu'un dump partiel. Fichier temporaire,
  nettoyage EXIT, validation gzip puis publication sans écrasement
  par lien dur sur le même filesystem.
- `scripts/restore.sh` utilisait psql sans ON_ERROR_STOP : des erreurs
  SQL pouvaient être suivies de « Restore complete ». Ajout du flag
  et contrôle gzip avant confirmation et accès Docker.
- Six régressions exécutent les scripts Bash avec Docker substitué :
  dump partiel, dump réussi, collision, archive corrompue, SQL réussi/
  échoué. **15/15 pass avec les neuf tests CI**, Ruff PASS, 3.90 s.
- Aucun backup live ni restore DB effectué. Un restore SQL échoué peut
  avoir déjà changé la cible; la procédure n'est pas un rollback atomique.
- Rétention distante et erreurs d'upload restent inchangées dans ce lot;
  pas de promesse de copie hors site validée. Documentation install mise
  à jour. Les six nouveaux tests sont hors collection du run actif.
