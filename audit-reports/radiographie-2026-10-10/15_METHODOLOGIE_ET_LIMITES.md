# 15 — Méthodologie et limites

## Date et état Git
- Audit : **2026-10-10**, début ≈ 14:45 (UTC+1), fin ≈ 16:30.
- Dépôt : `C:\Users\NITROV15\Downloads\rag-saas-platform`. Branche locale `bob/auto-fix-20261009-0715`, **HEAD `59d5ec9b5ab69a1d04cafe64ec1ad617ba2bcea0`** (« Merge pull request #20 », parents `bb0a89d` et `eb2e8e5`), identique à `origin/main` (0 commit d'écart) ; 1 commit d'avance sur la référence locale `origin/bob/auto-fix-20261009-0715` (référence distante non rafraîchie : **aucun `git fetch` n'a été fait**).
- Remote : `origin` = dépôt GitHub public `naomytcheums-dotcom/rag-saas-platform` (sans credentials dans l'URL).
- **Avant l'audit** : `git status --short` = 2 entrées non suivies préexistantes (`FGbmsPryLaJXqu5hfC24RTZe`, `scripts/pending/`). Branches locales : 19 (dont 5 `worktree-agent-*`, `claude/*`, `backup/pre-redaction-20261005`). Worktrees : 10 (5 agents Claude Code dans `.claude/worktrees/`, 1 `claude/magical-dewdney`, 3 sous `C:/Users/NITROV15/rag-work/`). Aucun conflit en cours (pas de MERGE_HEAD, rebase, cherry-pick). Aucun stash. 565 commits (131 depuis `2e7bfaa`, l'ancien `main` local).
- **Après l'audit** : `git status --short` = les 2 entrées préexistantes + `audit-reports/` (nouveau, livrables). HEAD inchangé.
- Note : **HEAD a changé pendant la session** — au début de la journée la branche pointait sur `4ee2c22` ; la PR n°20 a été fusionnée à 11:40 par l'utilisatrice, qui a aussi ajouté `eb2e8e5` (TEN-012). Ce n'est pas une action de cet audit.

## Commandes réellement exécutées (lecture seule)
- Git : `branch`, `rev-parse`, `log`, `status`, `rev-list --left-right --count`, `merge-base`, `merge-base --is-ancestor`, `worktree list`, `stash list`, `remote -v`, `ls-files`, `show --stat`, `check-ignore`. Aucune commande modifiant des références.
- Scripts d'inventaire Python placés **hors du dépôt** (`D:\rag-work\audit-scripts\` : `cahier.py`, `cahier2.py`, `routes.py`, `db.py`, `findings.py`) :
  - `routes.py` importe `api.main` avec `DATABASE_URL` factice (`127.0.0.1:1`, injoignable) et lit `app.openapi()` + les dépendances FastAPI ; `PYTHONDONTWRITEBYTECODE=1`. Aucune requête réseau.
  - `db.py` importe les modèles et lit les métadonnées SQLAlchemy ; aucune connexion.
- `pytest --collect-only` (aucun test exécuté) ; `ruff check api` ; `tsc --noEmit` ; `eslint .` ; `vitest run` (27 fichiers, 178 tests).
- Lecture d'API publiques : GitHub (`actions/runs`, `jobs`, journaux de jobs) et CircleCI v1.1 (builds #465, #482-#496), **sans authentification, en GET**. Ces appels sont des lectures, pas des écritures.
- Quatre explorations en lecture seule déléguées à des sous-agents (RAG ; auth/tenant/sécurité ; agents/MCP/Celery/stockage ; déploiement/frontend). Leurs textes sont repris en annexe de `03`, `05`, `06`, `07` et `14`, **avec leurs limites** : numéros de ligne parfois approximatifs, quelques erreurs détectées (voir « Contradictions » ci-dessous).

## Tests exécutés / non exécutés
Voir `10_TESTS_CI_DEPLOIEMENT.md`. Résumé : ruff, tsc, eslint, vitest exécutés avec succès ; collecte pytest faite (6 130 tests) ; **suite pytest backend complète NON EXÉCUTÉE dans cet audit** (résultats distants consultés à la place) ; tests PostgreSQL opt-in non relancés dans cet audit (résultats antérieurs du jour cités).

## Sources consultées
`docs/CAHIER_DES_CHARGES.md` (3 898 lignes), `ROADMAP.md`, `README.md`, `agents.md`, `AUDIT.md`, `docs/audit/*` (33 fichiers, **non lus un par un**), `docs/admin/BILLING.md`, `docs/devops/CI.md`, `render.yaml`, Dockerfiles, workflows GitHub, `.circleci/config.yml`, migrations, modèles, routeurs, services, tâches, frontend, tests ; rapports d'audit d'origine **hors dépôt** `D:\rag-work\audit-evidence\*.md` (billing, tenant, map, rag, superadmin, ux, tests, secreview — 173 identifiants) ; historique Git (messages de commit).

## Exclusions
`.venv*`, `node_modules`, `.next`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.claude/worktrees/` (copies d'autres agents), `snyk.exe` (binaire de 55 Mo à la racine : présent sur disque, non analysé), `.coverage`, `dump.rdb`, `storage/`, `staging-artifacts/`. **Fichiers `.env`, `.env.staging` : jamais ouverts.** `.env.example` non repris ligne par ligne.

## Limites d'accès / informations indisponibles
- Base de données réelle (Supabase) : non consultée. Redis, S3/R2, Render, Vercel, Stripe, Paystack, Resend : non consultés.
- Résultats Vercel : **STATUT DISTANT NON VÉRIFIÉ**.
- Lien exigence ↔ test/code de la matrice (`02_MATRICE_EXIGENCES.csv`) : **heuristique** (référence textuelle à l'identifiant près des mots « Partie / item / étape ») — il sous-estime fortement les liens réels.
- Lien route ↔ test (`04_API_ENDPOINTS.csv`) : heuristique par présence du chemin littéral dans un fichier de test (paramètres normalisés), pas par appel prouvé.
- Colonne « authentification » du CSV des routes : déduite de l'arbre de dépendances FastAPI ; les 84 routes classées « aucune dépendance d'auth détectée » incluent des routes réellement publiques (webhooks, login, widget…) mais aussi des routes protégées par un autre mécanisme non reconnu (par exemple `/account/me`, `/sessions`) : **à vérifier une à une**.

## Contradictions relevées et traitement
1. Cahier des charges : l'en-tête annonce « 515 fonctionnalités », le tableau « Total recompté » annonce 110 lignes (90/17/3) ; le recomptage reproductible donne 150 lignes de tableau (130/18/2) — voir `01_INVENTAIRE_FONCTIONNALITES.md`.
2. Sous-agent « déploiement/frontend » : annonce « 74 fichiers `page.tsx` » ; le décompte direct (`Get-ChildItem` et `git ls-files`) donne **57**. C'est le chiffre retenu (le sous-agent a probablement compté d'autres fichiers).
3. Sous-agent « sécurité » : écrit que les règles SADM-005 « ne sont pas retrouvées » ; le code les contient (`api/routers/admin_subscriptions.py`, `tests/test_p1_sadm005_*.py`). C'est le code qui fait foi.
4. Sous-agent « sécurité » : écrit que le rate limiting devient inopérant si Redis est indisponible (fail-open) ; les journaux de tests montrent « degrading to the in-process limiter » (repli sur un limiteur en mémoire de processus, non partagé entre workers). Statut retenu : **dégradé, pas inopérant**.
5. `agents.md` : Python 3.11 ; code/CI : 3.13.
6. `docs/CAHIER_DES_CHARGES.md` : « GitHub Actions désactivé explicitement » (2026-09-18) alors que `.github/workflows/ci.yml` existe et tourne (réactivé depuis ; la phrase est obsolète).
7. Annexes des sous-agents (« déploiement » et « infrastructure ») : elles disent que `docker-entrypoint.sh` lance Celery + gunicorn dans le conteneur ; `Dockerfile.api` n'utilise que gunicorn (le worker embarqué a été retiré). C'est le Dockerfile qui fait foi.
8. Annexe du sous-agent « RAG » : « Recall@K/MRR/NDCG NON TROUVÉ » ; ils sont dans `api/services/retrieval_metrics.py`. Le corps de `06` fait foi.

## Aucun secret
Les livrables ne contiennent aucune valeur de secret : seules des **noms** de variables sont cités. **Contrôle effectué en fin d'audit** (`validate.py`) : balayage par motifs (clés `sk-…`, `sk_live_`/`sk_test_`, `whsec_`, `AKIA…`, clés privées, JWT, URL de base avec mot de passe, jetons longs) sur les 17 livrables : **0 occurrence**. Les trois CSV sont valides (16, 11 et 13 colonnes constantes ; 150, 943 et 180 lignes).

## Contrôles de la seconde passe (phase R)
- Totaux cohérents entre livrables : 943 opérations (04 = 03 = 00 = 16), 177 tables (08 = 03), 150 lignes d'inventaire (01 = 02), 180 constats (11 = 16 ; 173 d'origine + 7 « R »), 6 130 tests collectés (10 = 00).
- État Git **après** l'audit : HEAD `59d5ec9` inchangé, aucune modification des fichiers suivis (`git diff` vide, rien en index), 0 stash, 10 worktrees (inchangés), seule différence : le dossier non suivi `audit-reports/` ; les deux fichiers non suivis préexistants (`FGbmsPryLaJXqu5hfC24RTZe`, `scripts/pending/`) sont intacts.
- Aucun `__pycache__` créé dans `api/` ni `tests/` pendant l'audit (`PYTHONDONTWRITEBYTECODE=1`).
- Aucune exécution n'a été faite contre une base ou un service réel : la `DATABASE_URL` de tous les processus Python était une cible factice injoignable. **Précision** : l'auditeur n'a jamais ouvert `.env`, mais les scripts qui importent `api.main` / `api.models` chargent la configuration via pydantic-settings, qui lit `.env` en mémoire (valeurs jamais affichées ni écrites) ; l'import n'ouvre aucune connexion. Le `.env` local référence un pooler PostgreSQL et un Redis Upstash distants.

## Parties non terminées (honnêteté)
- Matrice des exigences : statut d'implémentation **non vérifié ligne par ligne** (150 lignes « NON DÉTERMINÉ ») ; liens tests/code heuristiques.
- Registre des constats : 122 lignes `OUVERT (NON REVÉRIFIÉ)` ; `docs/audit/*` (33 fichiers) non intégrés au registre.
- Inventaire des routes : permissions par dépendance FastAPI, pas de lecture route par route ; « rôles autorisés » et « effets de bord » non détaillés ; pas de colonnes schémas/validations/limitation de débit.
- Frontend : aucune navigation réelle ; sécurité : aucune relecture exhaustive des 101 routeurs ; performance : aucune mesure.
- Recherche externe de concurrents : non faite.
