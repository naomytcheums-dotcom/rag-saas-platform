# COPILOT — TRAVAILLE MAINTENANT, N'ÉCRIS PLUS DE PROMPT NI DE PLAN

Tu as déjà reçu des documents de contexte (`COPILOT_CONTINUATION_PROMPT.md`, `PROMPT_COPILOT_REPRISE.md`). **Ne les réécris pas, ne produis plus de plan, de résumé ni de rapport de préparation.** Ta seule sortie utile est du code qui tourne, des tests exécutés avec leur résultat, des commits et des pushs. Réponds en français. Si tu t'arrêtes pour expliquer ce que tu *vas* faire au lieu de le faire, tu échoues la mission.

## Règle de la propriétaire (Naomy), valable pour toute la session
Elle autorise explicitement : modifier le code, les tests, la doc technique et les configs locales ; créer des commits et pousser des branches ; **fusionner une PR dans `main` quand la CI bloquante est verte** (`backend-tests`, CircleCI `api-tests`, `frontend-checks`, `build-backend`, `build-frontend` ; mypy et bandit sont non bloquants). Une branche à la fois.
Interdits absolus : lancer pytest avec le `.env` ou une base de production ; modifier une migration existante (en créer une nouvelle) ; `git push --force` ; secrets en clair ; affaiblir un test de sécurité ; présenter un mock comme un vrai service ; paiement réel, envoi massif d'e-mails, déploiement cloud réel.

## Objectif
Faire passer à un état prouvé les **60 fonctionnalités** restantes du catalogue (`audit-reports/functional-audit-2026-10-10/01c-feature-verification-after-test-runs.csv`, colonne `status_final`), plus tout défaut ou fonctionnalité partielle trouvé en chemin. Ces 60 ids : 
- 17 non vérifiées : 1.4.1 1.4.5 1.4.9 5.3.10 8.2.3 8.2.5 12.1.2 12.1.6 12.1.7 12.1.8 12.1.10 12.2.1 12.2.2 12.2.3 12.2.4 12.2.5 12.3.1
- 22 externes : 1.4.3 4.1.1 4.1.2 4.1.3 4.1.4 4.2.1 4.2.2 4.2.3 5.2.2 5.2.7 5.2.8 5.4.11 8.2.2 9.4.1 9.4.2 9.4.3 10.1.15 10.3.6 10.3.9 11.3.4 13.5.5 13.5.8
- 10 écrites non exécutées : 10.1.14 13.1.6 13.4.4 13.4.5 13.4.9 14.2.7 14.3.2 14.4.2 14.4.4 15.2.7
- 11 validées non déployées : 10.4.7 10.4.8 10.4.9 10.4.10 10.4.11 13.4.6 13.4.7 13.4.8 13.4.10 13.4.11 13.4.12

## Étape 0 (≤ 5 minutes, puis tu codes)
```bash
git fetch origin
git worktree add ../wt-billing  origin/bob/auto-fix-20261013-billing
git worktree add ../wt-infra    origin/bob/auto-fix-20261013-infra
git worktree add ../wt-external origin/bob/auto-fix-20261013-external
git worktree add ../wt-rag      origin/bob/auto-fix-20261013-rag
```
Chaque branche contient du travail déjà fait + un dernier commit `wip(...)` non testé. Dans chaque worktree : `git checkout -B <même nom de branche>` sur sa branche distante, pour pouvoir pousser.

Environnement local de test (déjà installé sur la machine) : Docker, conteneurs `rag-test-pg` (Postgres+pgvector, port 25432, utilisateur `rag_test`, mot de passe dans `docker inspect rag-test-pg`), Redis port 26390, Mailpit (SMTP 1025, API 8025), MinIO 9000, Ollama 127.0.0.1:11434 (qwen2.5:3b et 7b, CPU lent : préfère 3b). Python du projet : `C:\Users\NITROV15\Downloads\rag-saas-platform\.venv\Scripts\python`. Tests backend : `sh scripts/run_tests_local.sh <fichiers> -q` avec `TEST_DATABASE_URL=postgresql+asyncpg://rag_test:<mdp>@127.0.0.1:25432/<base dont le nom contient "test">`, puis `python -m alembic upgrade head` sur cette base. Une base et un numéro de Redis (11 à 14) par chantier. Windows + Git Bash : `MSYS_NO_PATHCONV=1` devant les commandes Docker ; arrêter un processus avec PowerShell `Stop-Process`. RAM limitée : tests par lots, jamais toute la suite d'un coup, 2 chantiers en parallèle au maximum.

## Chantier 1 — billing (branche `bob/auto-fix-20261013-billing`) — commence ici
Ids : 12.1.2 12.1.6 12.1.7 12.1.8 12.1.10 12.2.1–12.2.5 12.3.1 ; 1.4.1 1.4.5 1.4.9 ; 5.3.10.
1. Lance les tests déjà écrits : `tests/test_domains_email_postgres.py`, `tests/backend/whitelabel/test_email.py`, `tests/test_billing*.py`, `tests/test_plans*.py`. Les deux fichiers de test de domaines doivent utiliser la route `/whitelabel/config` (dernière correction en cours).
2. Corrige jusqu'au vert. Puis écris et exécute ce qui manque : annulation d'abonnement, rétrogradation avec usage supérieur au plan, limites aux frontières (3ᵉ/4ᵉ document, 10ᵉ/11ᵉ question du jour pour le plan gratuit ; 100/500 ; 1 000/illimité ; 10 000 + API + white-label ; illimité), épuisement des crédits IA, historique des paiements, webhooks de paiement idempotents (événements en double), domaine personnalisé et adresse d'envoi d'e-mail (faux DNS/Resend locaux, dis-le), déploiement d'un agent (5.3.10), isolation entre organisations et rôles.
3. Commit, push, ouvre la PR, attends la CI, fusionne.

## Chantier 2 — infra (branche `bob/auto-fix-20261013-infra`)
Ids : 10.4.7–10.4.11, 13.4.4 13.4.5 13.4.6 13.4.7 13.4.8 13.4.9 13.4.10 13.4.11 13.4.12, 10.1.14, 13.1.6, 14.2.7, 14.3.2, 14.4.2, 14.4.4, 15.2.7.
Exécute réellement : `terraform fmt -check` et `terraform validate` (image Docker `hashicorp/terraform` si pas installé), `helm lint` et `helm template` (image `alpine/helm`), validation des manifestes Kubernetes (`kubeconform` ou `kubectl --dry-run=client`), `docker build -f Dockerfile.api .`, `docker compose up` de la pile locale avec vérification des health checks, validation des fichiers Railway/Fly/DigitalOcean (schémas/toml/yaml), tests d'artefacts de déploiement, chiffrement au repos de bout en bout (déjà prouvé sur MinIO : relance les tests), couverture : mesure avec la commande exacte (`pytest tests/ --cov=api --cov-report=term-missing` par lots) et écris de vrais tests sur les modules les moins couverts jusqu'à 90 % ou documente le chiffre mesuré. Vidéo/démo : enregistre la page de démo avec le script Playwright déjà écrit. N'applique rien sur un vrai cloud. Vérifie le test `tests/test_celery_worker_workflow.py` en local Windows (il a été rendu portable : exécute-le pour de bon).

## Chantier 3 — external (branche `bob/auto-fix-20261013-external`)
Ids : les 22 externes + 8.2.3 8.2.5.
Fait : contrats LLM, OAuth/Gmail, embeddings, Slack/Teams/Discord, observabilité. Reste : voix (TTS local réel par Windows SAPI ou piper, lecture en temps réel, détection de parole VAD, gestion d'erreurs vocales — fichiers `api/services/voice.py`, `api/routers/voice.py`, `frontend/components/VoiceOutput.tsx`, `e2e/voice/`), recherche web (Tavily/Google), calendrier, TLS (certificat auto-signé local derrière un reverse proxy), traçage LLM, suivi d'erreurs, sonde de disponibilité (`scripts/uptime_probe.py`). Pour chaque fournisseur sans clé : adaptateur complet + tests de contrat sur un faux serveur local (écris que c'est un faux) + une commande `scripts/validate_<fournisseur>_live.py` gardée par un drapeau d'environnement ; statut `IMPLEMENTED_EXTERNAL_VALIDATION_REQUIRED`. Ne lis pas `.env` : si des clés existent, elles sont dans l'environnement du processus.

## Chantier 4 — rag (branche `bob/auto-fix-20261013-rag`)
Chaîne complète avec Ollama (pile privée : API port 8030, worker Celery propre, Redis DB 14, base `rag_test_rag`; inspire-toi de `scripts/test_env/e2e_stack_env.sh`, `e2e_stack_start.sh`, `scripts/e2e_full_journey.py`, `scripts/e2e_rag_ingestion_search.py`).
- Ingestion : tous les formats, lots, très gros/très petits, vides/corrompus, doublons/réimports, métadonnées/filtres, asynchrone, reprise après échec, réindexation, suppression avec nettoyage vérifié en base.
- Recherche : dimensions/identité des modèles d'embedding, vectoriel/lexical/hybride, paramètres par organisation, cas sans résultat, Recall@k/MRR/NDCG sur `data/test_set.json` (ne jamais modifier les réponses attendues).
- Chat : streaming, timeouts, citations/fidélité, question sans réponse, garde-fous.
- Scénarios : connexion → organisation → import → async → index → recherche → chat cité → historique → suppression ; échec d'ingestion puis reprise ; Ollama coupé puis rétabli ; deux organisations sans fuite ; utilisateur sans permission ; documents contradictoires ; conversations simultanées ; réindexation après modification.
- Ids IMPLEMENTED_UNVERIFIED du catalogue hors 12.x/1.4.x/5.3.10/8.2.3/8.2.5 : relis le CSV `01b` (liste avant superposition) : Eval Lab 7.x, interface chat 8.1.x, API publique/clés/widget/SDK 9.x, sécurité 10.x, métriques 11.x, tests/CI 13.x, docs 14.x. Vérifie leur comportement réel (état, autorisations, erreurs), pas seulement le HTTP 200.
- Re-vérifie aussi les correctifs de la PR #26 : seuil de score 0.0 et `top_k`, détecteur d'injection, streaming avec garde-fous, TLS SMTP, bloc e-mail, signatures de webhooks V2, upload vide, S3 non configuré (503), Whisper, redirections GitHub, bouton imbriqué (vitest `ConversationItem`).

## Pour chaque fonctionnalité
Lire la ligne du CSV et le code → implémenter le manque → tests d'intégration + cas d'échec → **les exécuter** → corriger → relancer les tests voisins → noter la preuve dans `audit-reports/functional-audit-2026-10-10/apply_fixes_overlay.py` (préfixe « tests pass » pour une preuve exécutée) → régénérer : `cd audit-reports/functional-audit-2026-10-10 && python apply_fixes_overlay.py && python apply_test_runs.py && python build_final_status.py` → commit. Statuts honnêtes : `IMPLEMENTED_AND_TESTED`, `IMPLEMENTED_TEST_FAILED`, `IMPLEMENTED_EXTERNAL_VALIDATION_REQUIRED`, `IMPLEMENTATION_INCOMPLETE`, `BLOCKED` (cause exacte). Le code qui existe, un mock qui passe ou une CI verte ne suffisent pas.

## Fin de chaque chantier
`git push`, `gh pr create --base main`, attendre la CI bloquante verte, `gh pr merge --merge`, puis tirer `main` dans le chantier suivant. Si ton contexte se remplit : écris `docs/project-handover/e2e_evidence/RESUME.md` (dernier id fini, suivants, commandes, tests en échec, blocages, prochaine action), pousse, et continue depuis ce fichier.

## Message final (seulement quand tout est traité)
Liste des 60 ids avec statut réel + preuve ; corrections ; commandes de test et résultats ; résultats du parcours Ollama ; validations externes encore indispensables (une commande chacune) ; défauts restants ; fichiers modifiés et migrations nouvelles ; commandes de reproduction. Rappelle à Naomy : régénérer la clé de chiffrement collée dans un ancien chat ; le déploiement de production (variables Render, worker + beat, migrations) reste à faire par elle.

**Premier geste attendu : exécuter les commandes de l'étape 0, puis lancer les tests du chantier 1. Maintenant.**
