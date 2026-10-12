# PHASE 1 — Préservation des preuves et sécurisation (2026-10-12)

Suite de `../phase0-2026-10-12/PHASE_0_READ_ONLY_SECURITY_AUDIT.md`. Périmètre appliqué : sauvegarde de preuves, protection contre les commits accidentels, scripts de collecte pour la propriétaire. **Aucune migration, aucune écriture en base, aucun test, aucune poussée, aucune fusion, aucun déploiement, aucune rotation de secret.**
Distinction : **EXÉCUTÉ ET PROUVÉ** / **ÉCRIT, NON EXÉCUTÉ** / **EN ATTENTE DE LA PROPRIÉTAIRE**.

## 1. Exécuté et prouvé

| # | Action | Preuve |
|---|---|---|
| 1.1 | Règles d'ignore ajoutées à `.gitignore` (seul fichier suivi modifié) : `backups/`, `*.dump`, `*.sql.gz`, `*.pgdump`, `.env.*` avec exceptions `!.env.example` et `!.env.*.example`, `rag-secure-evidence/` | `git check-ignore -v` : `backups/prod_backup.dump`, `tmp/x.dump`, `.env.sandbox`, `.env.local` ignorés ; `.env.example` et `.env.staging.example` non ignorés ; aucun fichier déjà suivi ne correspond aux nouvelles règles (`git ls-files -ci` vide) ; `git status` ne montre plus `backups/` |
| 1.2 | Instantané Git des deux extractions, des worktrees, des branches, des divergences | `evidence/git_state_snapshot.txt` |
| 1.3 | Graphe des migrations de trois références (gaps, 1555, origin/main) | `evidence/migrations_graph_analysis.txt` : une tête chacune (0143, 0137, 0142), aucun doublon interne ; collision `0137` entre gaps et 1555 |
| 1.4 | Copie de sécurité du travail non commité de l'autre session : patch des 5 fichiers suivis modifiés et inventaire (noms, tailles, dates, **sans contenu**) des fichiers non suivis | `evidence/other_session_uncommitted_tracked_changes.patch` (+71/−29, aucune correspondance de motif de secret) ; `evidence/other_session_untracked_inventory.txt` |
| 1.5 | Les 232 exécutions de `ci.yml` avec date, événement, branche, SHA, conclusion, lien, et un indicateur « secrets du dépôt utilisés par `backend-tests` » pour les n°1 à n°194 | `evidence/ci_yml_runs_1-232.csv` (194 lignes marquées) |
| 1.6 | Extraits bruts d'API conservés : jobs du run n°193, queue du journal de `backend-tests` n°193, queue du journal du worker Celery n°137 | `evidence/run193_*.json`, `evidence/celery_worker_run137_failed_job_log_tail.json` (aucun motif de secret) |
| 1.7 | Empreintes SHA-256 de tout le dossier | `MANIFEST.sha256` |

## 2. Écrit, non exécuté (à lancer par la propriétaire dans son terminal)

| Script | Rôle | Garde-fous |
|---|---|---|
| `owner_scripts/owner_readonly_checks.sql` + `run_owner_readonly_checks.ps1` | Répond aux questions C.2 du rapport de phase 0 : révision appliquée, rôle et `rolbypassrls`, nombre de politiques et de tables sans RLS, propriétaires des tables, droits `anon`/`authenticated`, comptage de `jwt_signing_keys`, pollution « test », version de pgvector | Uniquement des `SELECT` ; session forcée en lecture seule (`default_transaction_read_only=on`) ; ne lit pas la colonne `secret` ; n'affiche jamais l'URL ; résultat écrit **hors du dépôt** (`~\rag-secure-evidence`) |
| `owner_scripts/download_actions_logs.ps1` | Télécharge les archives de journaux des runs n°1–194 (`gh api …/logs`) avant l'expiration à 90 jours ; liste ceux qui ont déjà expiré | Lecture seule ; archives hors dépôt ; empreintes SHA-256 |

Les deux scripts ont été vérifiés par l'analyseur syntaxique de PowerShell (0 erreur) ; ils n'ont **pas** été exécutés.

## 3. En attente de la propriétaire

1. Lancer les deux scripts ci-dessus et me transmettre **les réponses** (pas l'URL de connexion).
2. Décider du sort de `backups/prod_backup.dump` : je l'ai laissé en place car le runbook l'attend à cet endroit ; il ne peut plus être commité par accident, mais il reste une copie de données de production dans le worktree. Recommandation : le déplacer hors du dépôt et le chiffrer (je n'ai pas de phrase secrète à utiliser).
3. Rotation des secrets (ordre proposé dans le rapport de phase 0, section E) : non commencée.
4. Journaux Supabase des créneaux de CI ; configuration de déploiement Render/Vercel ; protections de l'environnement `production-migrations` ; journaux CircleCI du run 603.
5. Confirmer à qui appartient le fichier non suivi `FGbmsPryLaJXqu5hfC24RTZe` (30 octets, 2026-10-08, extraction principale). Son nom ressemble à un jeton : **son contenu n'a pas été lu** et il ne doit jamais être commité.

## 4. Défauts nouveaux relevés pendant la phase

* **Runbook** (`docs/RELEASE_RUNBOOK_2026-10-11.md`, ligne 38) : un caractère de contrôle `0x08` (retour arrière) remplace `\b` dans `-v "${PWD}…ackups:/out"`. La commande de sauvegarde de production telle qu'écrite monte un mauvais chemin. Correction attendue : remplacer par `${PWD}\backups:/out`. Non corrigé ici (je n'ai pas pu cibler ce caractère invisible avec mes outils d'édition sans réécrire le fichier) ; à corriger à la main ou par une phase de documentation.
* Le worker Celery GitHub (CI-008) continue de tourner avec les secrets de production : aucun changement fait.

## 5. État Git à la fin de la phase
* Branche `bob/auto-fix-20261010-gaps`, HEAD d'origine `c04100e` ; modification non commitée : `.gitignore` ; non suivis : `audit-reports/phase0-2026-10-12/`, `audit-reports/phase1-2026-10-12/`, `rag-saas-project-handover.zip`.
* Rien n'est poussé.

## 6. Critères d'entrée de la phase 2 (isolation des tests et de la CI)
* Réponses aux requêtes lecture seule (au minimum révision et rôle), pour savoir ce que la CI a pu toucher et dans quel état est le schéma.
* Décision : où héberger le worker Celery et quoi faire du secret `DATABASE_URL` du dépôt (le retirer du niveau dépôt dès que le worker est déplacé).
* Accord pour modifier la CI (`ci.yml`, `.circleci/config.yml`) et les gardes des tests, avec des tests de contrat qui échouent sans les gardes, sans supprimer ni affaiblir aucun test existant.
