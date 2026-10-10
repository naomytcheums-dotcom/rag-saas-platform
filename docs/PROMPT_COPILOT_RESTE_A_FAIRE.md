# Prompt Copilot — tout ce qui reste à faire (2026-10-10)

Contexte : plateforme RAG SaaS (FastAPI + Next.js 16, Supabase, Render, Vercel). Migrations au head 0136 (prod aussi).
Règles absolues : jamais de push direct sur `main` (branche `bob/auto-fix-AAAAMMJJ-HHMM` + PR), jamais de `git push --force`,
ne jamais modifier une migration existante, ne jamais écrire de secret dans un fichier/log/chat, ne jamais toucher la base de production
(lecture seule, et seulement si la propriétaire l'a demandé), `pytest` + `ruff check api/` verts avant chaque commit, un test qui échoue
se corrige dans le code (jamais en modifiant ou supprimant le test). Rendre compte en français, en distinguant « exécuté » de « écrit ».

## 0. Garde-fou d'isolation (à faire en premier)
- Tout serveur ou script local (aperçu design, SQuAD, benchmarks) tourne sur SQLite ou une base Postgres locale jetable.
- Il doit **refuser de démarrer** si `DATABASE_URL`, `DATABASE_URL_TRANSACTION`, `REDIS_URL`, `CELERY_*`, `S3_ENDPOINT_URL`, `RESEND_API_KEY`,
  `STRIPE_*`, `PAYSTACK_*` ou `SENTRY_DSN` pointent hors de localhost (modèle : `D:\rag-work\dev_sqlite_server.py`).
- Ajouter ce garde-fou dans le dépôt (`scripts/dev_isolated_server.py` + test) au lieu de le laisser hors dépôt.

## 1. Pousser ce qui est encore local
- PR #21 (TEN-003 reste) : checks obligatoires verts (bandit est non bloquant) → à fusionner par la propriétaire.
- Committer sur une branche + PR : `audit-reports/` (relire chaque fichier avant, aucun secret), `scripts/pending/` (trier), garde-fou §0.
- Supprimer les fichiers locaux inutiles : worktrees `wt-20`, `wt-ci`, `wt-sec`, `tok_*.txt` (jetons), `design-preview*.db`, le fichier parasite
  `FGbmsPryLaJXqu5hfC24RTZe` à la racine. Vérifier que rien d'utile n'est perdu (`git status`, `git stash list`, `git worktree list`).

## 2. Test réel de l'agent avec SQuAD 2.0 (base locale isolée uniquement)
- Source : jeu de développement SQuAD 2.0 (https://rajpurkar.github.io/SQuAD-explorer/, licence CC BY-SA 4.0), ~1200 passages validés par la propriétaire.
  Télécharger dans un dossier vide dédié, ne rien exécuter depuis ce dossier.
- Ingérer les passages dans une organisation de test **locale**, puis mesurer : Recall@1/3/5/10, MRR, NDCG, précision des citations
  (la source citée contient-elle la réponse ?), qualité de génération, traitement des questions sans réponse (SQuAD 2.0 `is_impossible` :
  l'agent doit dire qu'il ne sait pas), et **séparer échec de retrieval / échec de génération** (catégories Eval Lab).
- Chemin voix : tester la chaîne STT → agent → TTS avec des enregistrements de test, sans appel Twilio réel.
- Clé LLM : lue dans le `.env` local de la propriétaire, jamais affichée. Si absente : le dire et s'arrêter sur cette partie.
- Livrable : rapport chiffré + comparaison avec les seuils de `agents.md` §2 (mode GUARDIAN), journalisé dans ROADMAP.md.

## 3. Constats d'audit ouverts (matrice « radiographie », ~122)
- Traiter par priorité : sécurité/multi-tenant → facturation → fiabilité → UX → documentation. Un constat = un test de non-régression.
- Décision à documenter : RLS `FORCE` + policies Supabase (migration nouvelle, jamais modifier les anciennes, round-trip upgrade/downgrade testé).
- Déploiement Celery worker + beat ; procédure de migration prod + sauvegarde avant.
- Facturation : tests en mode bac à sable seulement (clés test Stripe/Paystack de la propriétaire, jamais de clé live).
- Corriger `agents.md` : routes `/api/eval/*` et `/mcp/v1/servers*` qui n'existent pas, version Python (3.13).
- Cahier des charges : la Partie 15 est tronquée → demander le texte d'origine à la propriétaire, ne rien inventer.

## 4. Actions réservées à la propriétaire (ne pas les faire)
- Render : `CREDITS_ALLOW_UNPAID_TOPUP=false`, `METRICS_AUTH_TOKEN`, `DISCORD_GATEWAY_SHARED_SECRET`, `TEAMS_BOT_ID`.
- Nettoyage des comptes de test dans la base de production (SQL d'inspection en lecture seule d'abord) et vérification des logs Supabase (8 et 10 oct.).
- Rotation des clés bac à sable Kang collées en chat ; clés Stripe/Paystack de test et clé LLM payante dans son `.env` local.
- Création de son compte superadmin unique avec l'identifiant qu'elle choisit.

## 5. Fin de mission
Tout est sur une branche + PR, CI verte (GitHub Actions + CircleCI), `git status` propre, ROADMAP.md à jour sous `[Bob-Auto-Fixes]`.
