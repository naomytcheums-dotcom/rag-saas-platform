# Prompt de reprise pour Claude (à coller tel quel dans une nouvelle session Claude Code)

Remplis les CONFIRMATIONS en bas AVANT d'envoyer. Le reste est prêt.

---

Tu reprends le projet RAG SaaS Platform (dépôt GitHub naomytcheums-dotcom/rag-saas-platform). Tu travailles seul, en autonomie, sans me poser de questions de confort : tu ne me
demandes quelque chose que si une décision m'appartient ou si un compte/une clé que tu ne peux pas créer te manque. Tu rends compte en FRANÇAIS, en distinguant toujours ce qui est
EXÉCUTÉ et PROUVÉ de ce qui est seulement ÉCRIT. Tu ne dis jamais "prêt" sans preuve exécutée.

## 1. Où on en est (vérifié le 2026-10-11)
- Branche de travail : bob/auto-fix-20261010-gaps, PR #25 ouverte vers main. Worktree : C:\Users\NITROV15\rag-work\wt-gaps (worktree du dépôt principal
  C:\Users\NITROV15\Downloads\rag-saas-platform). Interpréteur Python à utiliser : C:\Users\NITROV15\Downloads\rag-saas-platform\.venv\Scripts\python.exe (le worktree n'a pas de .venv).
- Bilan sur les 514 fonctionnalités du cahier des charges (fichier audit-reports/functional-audit-2026-10-10/10-final-status-2026-10-11.md, généré depuis le CSV) :
  283 vérifiées complètes, 114 corrigées et testées, 25 décisions/corrections, 13 validées avec l'outil officiel mais jamais déployées, 19 écrites mais jamais exécutées,
  34 implémentées non vérifiées, 26 bloquées par un service externe, 0 ambiguë.
- Lis d'abord : AGENTS.md, docs/DECISIONS.md (surtout D15, D16, D17), docs/RELEASE_RUNBOOK_2026-10-11.md, le fichier de statut ci-dessus, et ta mémoire (MEMORY.md).
- Une AUTRE session (Copilot dans VS Code) travaille dans le dépôt principal sur la branche bob/auto-fix-20261010-1555 et partage mes conteneurs Docker de test. Ne touche à aucun de ses
  processus ni fichiers. Ses commits locaux (0c4dfcf, 52a357d) ne sont pas poussés.

## 2. Règles non négociables
1. JAMAIS de test, de script d'essai ni d'import "pour voir" avec la base de production. Le .env du projet contient les vraies valeurs (Supabase, Upstash, Resend, Grafana Cloud, Twilio...).
   Tout passe par scripts/run_tests_local.sh (il vide Loki, Tempo, Langfuse, Sentry...). Pour un script ad hoc qui importe api.*, exporte d'abord DATABASE_URL vers la base jetable.
2. Tu ne touches PAS à la base de production et tu n'as pas ses accès. La procédure de production est dans docs/RELEASE_RUNBOOK_2026-10-11.md : c'est moi qui lance sauvegarde et migrations.
3. Jamais de push direct sur main, jamais --force, jamais de secret dans le chat ni dans un commit. Une clé de test que je te donne va dans un fichier local non versionné.
4. Tu ne modifies jamais un test pour qu'il passe, tu ne supprimes aucun test. Un test mal écrit se corrige en expliquant pourquoi, assertion préservée. Chaque correction de code vient avec un test
   qui échoue sans elle (prouve-le).
5. Tu ne modifies jamais une migration existante. Après une nouvelle migration : alembic upgrade head sur les 3 bases jetables.
6. Tu as mon accord pour TOUS les téléchargements nécessaires (modèles, images Docker, outils). La connexion fait environ 0,5 Mo/s : lance les gros téléchargements en arrière-plan, surveille avec
   Monitor, n'interroge pas en boucle, ne mets jamais un `timeout` court sur un passage de tests.
7. Un nouveau commit = ruff check api/ propre, tests ciblés verts, puis push sur la branche de la PR.

## 3. Environnement local (déjà en place, à vérifier avec docker ps)
- rag-test-pg : PostgreSQL 17 + pgvector, 127.0.0.1:25432, utilisateur rag_test, bases pytest_p0, rag_test_integration, rag_test_roundtrip_scratch (migrées jusqu'à 0143).
  Mot de passe : docker exec rag-test-pg printenv POSTGRES_PASSWORD (ne l'affiche jamais).
- rag-test-redis : 26379. rag-test-redis-b : 26380 (à toi seul, pour un worker Celery privé). rag-test-minio : 29000 ; rag-test-minio-9000 : 9000 avec les compartiments avatars/documents/voice
  (scripts/ci_create_buckets.py). rag-test-clamav : 3310. rag-test-jaeger : 16686 et 4318. rag-test-ollama : 11434 (modèle qwen2.5:3b en cours de téléchargement, image ollama/ollama de 9,4 Go).
- Lancer des tests : exporter TEST_DATABASE_URL (asyncpg vers pytest_p0) et TEST_REDIS_URL, mettre le .venv dans le PATH, puis : sh scripts/run_tests_local.sh <fichiers> -q
- La fixture db_session du projet est une SQLite en mémoire : les tests PostgreSQL ont leurs propres fixtures (pg_engine, ou celle de tests/test_pgvector_real_search.py).
- Variables des tests optionnels : PGVECTOR_REAL_TEST=1, CLAMAV_REAL_TEST_HOST=127.0.0.1, OTEL_REAL_TEST_JAEGER=http://127.0.0.1, PROMPT_INJECTION_MEASURE=1, HF_HUB_OFFLINE=1,
  RAG_DISPOSABLE_PG_URL + RAG_DISPOSABLE_PG_CONFIRM=rag_test_roundtrip_scratch, P0_PG_TEST_URL.
- Test du cycle de vie complet (tests/test_e2e_lifecycle.py) : il faut un worker Celery à toi, sur rag-test-redis-b et la même base (voir scripts/test_env/celery_beat_probe.py).
- Playwright : cd e2e puis PYTHON=<le python du .venv> et, si les ports sont pris, E2E_API_PORT/E2E_WEB_PORT (8777/3011 ont servi).
- Ma machine : RTX 4060 Laptop 8 Go de VRAM, 16 threads, 15,7 Go de RAM, Windows 11. Docker Desktop.
- Après tout changement de statut : python apply_fixes_overlay.py, python apply_test_runs.py, python build_final_status.py (dossier audit-reports/functional-audit-2026-10-10), commit, push.

## 4. Tâches, dans cet ordre (critère de réussite pour chacune)

### T1. Erreurs et CI
- gh pr checks 25 : corriger tout ce qui est rouge sauf le job bandit (non bloquant ; il reste 5 alertes Hugging Face sans révision fixée : les épingler si tu peux obtenir les empreintes).
- Corriger : les 17 erreurs ruff des fichiers de tests (sans changer d'assertion), puis réduire les 305 erreurs mypy (api/) en commençant par les modules d'authentification, de facturation et de sécurité.
- Réussite : CI verte (hors bandit), ruff propre sur api/ ET tests/ ET scripts/, mypy en baisse mesurée.

### T2. Ollama : vérifier l'installation et tout tester avec un vrai modèle local
- Vérifie : docker exec rag-test-ollama ollama list ; curl http://127.0.0.1:11434/api/tags. Si le modèle n'est pas arrivé, attends (Monitor).
- Utilise la carte graphique : recrée le conteneur avec --gpus all (même volume rag-test-ollama-data, pas de nouveau téléchargement) et vérifie que le GPU est utilisé. Télécharge ensuite un modèle
  de 7 à 8 milliards de paramètres qui tient dans 8 Go de VRAM (qwen2.5:7b-instruct ou llama3.1:8b) pour le juge d'injection et les évaluations. Garde qwen2.5:3b comme repli.
- Teste les fournisseurs du produit contre Ollama pour de vrai : provider "ollama" ET provider "openai_compatible" (OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:11434/v1), en conversation simple,
  en streaming, avec outils, avec erreur (modèle absent, arrêt du serveur en cours de réponse).
- Généralise tests/llm_optin/test_real_llm.py avec REAL_LLM_TEST_PROVIDER/REAL_LLM_TEST_MODEL (ajout, pas de modification d'assertion) et exécute-le contre Ollama (items 13.2.7, 13.2.8, 4.1.5, 5.4.3).
- Base de référence de qualité RAG (R-06) : ingère un vrai corpus (ex. la documentation FastAPI en Markdown, avec eval_datasets/verticals/fastapi.csv), exécute un vrai job d'évaluation et consigne
  Recall@k, MRR, NDCG (indépendants du LLM) et fidélité/pertinence (juge local) dans docs/PERFORMANCE_REPORT.md. Mesure aussi HyDE et multi-requêtes en A/B sur le même jeu (3.4.7, 3.4.8).
- Réussite : chiffres réels, protocole reproductible (script ou test), limites écrites (petit modèle = jugement faible).

### T3. Les 12 % de faux positifs du détecteur d'injection
- Contexte : api/services/prompt_injection_detection.py. Le classificateur seul : rappel 0,953, faux positifs 0,122 (3 sur 6 en français) sur tests/data/injection_eval_set.json (92 phrases).
  Les agents créés par agent_factory ont la détection ACTIVE. Un second avis par modèle de langage est déjà codé (detect_prompt_injection_confirmed, réglage PROMPT_INJECTION_LLM_CONFIRM,
  24 tests avec un faux modèle) mais il n'a jamais été mesuré avec un vrai modèle.
- Fais : mesure le pipeline complet avec le modèle local (T2). Sépare le jeu en développement et test : tu règles le prompt de confirmation sur la partie développement seulement, tu rapportes sur la partie test.
  Ajoute au moins 40 nouvelles phrases françaises et anglaises écrites après le réglage pour éviter le surapprentissage. Objectif : faux positifs inférieurs ou égaux à 3 % et rappel supérieur ou égal à 90 %.
- Si l'objectif n'est pas atteint : essaie un modèle plus grand, puis un classificateur multilingue ; en dernier recours expose un réglage par agent "bloquer / seulement signaler" et mets la valeur par défaut sur
  "signaler". Mets à jour tests/test_prompt_injection_measured.py (plancher), D15 et le CSV.
- Réussite : chiffres sur un jeu de test non utilisé pour le réglage, et un test qui échoue si on régresse.

### T4. Exécuter les 19 éléments "écrits, jamais exécutés"
Liste exacte (statut WRITTEN_NOT_EXECUTED du CSV) et ce qu'il faut faire pour chacun :
- 1.1.10 suppression du compte : le cron de purge doit tourner sur l'hébergeur (voir T5) ; en local, rejoue tests/test_e2e_lifecycle.py avec ton worker privé.
- 1.3.5 et 13.2.10 isolation / tests base : exécute tous les fichiers test_postgres_* en CI-like (RAG_DISPOSABLE_PG_*), puis décris dans D8 ce qu'il faudrait pour des politiques RLS réelles ; ne les active
  PAS en production sans ma décision.
- 10.1.14 chiffrement au repos : ce qui dépend de l'hébergeur ne se vérifie pas localement ; écris la liste précise des réglages à contrôler chez lui (Supabase, S3) et laisse l'item en attente de ma réponse.
- 13.1.6 couverture : lance pytest --cov=api sur toute la suite (PostgreSQL + Redis + MinIO + worker) ; consigne le chiffre réel ; écris des tests pour les modules critiques les moins couverts
  (auth, facturation, isolation). Ne prétends pas atteindre 90 % si ce n'est pas vrai.
- 13.2.7 et 13.2.8 tests LLM et RAG : voir T2.
- 13.4.3 Render, 13.4.4 Railway, 13.4.5 Fly.io, 13.4.9 DigitalOcean : valide chaque fichier avec l'outil hors ligne quand il existe ; le vrai déploiement exige mes comptes : demande-les-moi une fois, en liste.
- 14.1.11 dépannage : exécute chaque étape du guide sur la pile locale ; corrige le guide s'il ment.
- 14.2.7 vidéo de démonstration : lis-la réellement (ouvre le fichier, vérifie durée, lecture, contenu) et dis ce que tu vois.
- 14.3.2, 14.3.4, 14.3.8 pages démo, architecture, documentation : ouvre-les dans le navigateur intégré ou Playwright, prends des captures, vérifie liens et affichage mobile.
- 14.4.2 logo : décision qui m'appartient : ne l'invente pas.
- 14.4.4 charte graphique : compare par script les jetons CSS réels avec docs/commercial/BRAND_GUIDE.md.
- 15.2.7 boucle retour utilisateur vers évaluation : exécute-la de bout en bout sur des données locales avec le modèle de T2.

### T5. Déployer les 13 éléments "validés, jamais déployés"
Éléments : 10.4.7 à 10.4.11 (tenant dédié, base dédiée, privé, sur site, VPC), 13.2.11 et 13.3.8 (workflows), 13.4.6 à 13.4.8 et 13.4.12 (Terraform AWS, GCP, Azure), 13.4.10 (Kubernetes), 13.4.11 (Helm).
- Termine la construction de l'image (docker build -f Dockerfile.api -t rag-saas-api:test, avec INSTALL_OPTIONAL_RAG_DEPS=0 puis 1) et lance-la avec la base et Redis locaux : /health doit répondre.
- Kubernetes et Helm : crée un cluster local (kind, télécharge-le), charge l'image, fais helm install puis kubectl apply sur le manifeste, vérifie les pods, /health par port-forward et le worker. Démonte ensuite.
- docker-compose.tenant.yml et docker-compose.selfhosted.yml : docker compose up avec des secrets factices, vérifie la santé, détruis.
- Terraform : terraform plan/apply exige des identifiants cloud réels : dis-moi lesquels (compte de test) ; sans eux, l'item reste "validé, non déployé" et tu le dis.
- Workflows GitHub : après la fusion, lance e2e.yml et post-deploy-smoke.yml avec gh workflow run et rapporte le résultat. migrate.yml : seulement en mode répétition, et seulement si je te le demande.

### T6. Débloquer les 26 éléments "bloqués par un service externe"
- Ce qui se teste en local : 4.1.5 (Ollama, T2), 5.2.8 et 5.4.10 (e-mail SMTP : lance Mailpit), 10.3.5 (Jaeger : fait), 10.3.6 et 13.5.5 (traces LLM : instance Langfuse locale si possible),
  10.3.9 et 13.5.8 (suivi d'erreurs : GlitchTip ou Sentry local), 1.4.3 (Let's Encrypt : staging Pebble en local), 8.2.1 et 8.2.2 (voix : Whisper local, synthèse locale).
- Ce qui exige MES comptes : Anthropic, OpenAI, Gemini, Mistral, Voyage, Cohere, Slack, Teams, Discord, Google, Microsoft, Twilio, Datadog, hébergeur. Écris docs/SANDBOX_SETUP.md : pour chaque service, ce que je dois créer
  (palier gratuit si possible), les variables à renseigner dans un fichier local .env.sandbox (non versionné), la commande de test que tu lanceras, et dis-moi dans quel ordre le faire. Ne crée aucun compte à ma place.
- Paiement : D16. Voir T7 pour le connecteur CinetPay.

### T7. Défauts restants connus (à traiter ou à documenter avec preuve)
- D17 : les outils d'agents email, calendrier et GitHub (api/tools) utilisent encore des identifiants du serveur pour toutes les organisations : donne-leur le même traitement par organisation.
- D17 : les appels HTTP des connecteurs vers des adresses saisies par les clients passent par un client httpx ordinaire (fenêtre de réattribution DNS) : bascule-les vers ssrf_safe_client() sans casser les tests.
- Connexion OAuth "Se connecter avec Google / Microsoft" pour Drive et OneDrive (bouton au lieu de coller une clé) : conçois-la, implémente le côté serveur, dis-moi quelles applications enregistrer.
- Remboursements (BILL-016) et coupons en pourcentage au paiement (12.1.4) : propose une conception avec les deux options de politique (reprise ou non des crédits) et attends ma décision.
- Connecteur CinetPay : si j'ai collé la documentation officielle dans la section CONFIRMATIONS, implémente-le derrière BillingProvider (crédits prépayés), avec tests sur les contrats documentés,
  puis écris le test réel opt-in qui utilisera mes clés sandbox. Sinon, ne l'écris pas de mémoire.
- Fusion : voir la règle de la section 5.

### T8. Compte rendu final
Regénère le CSV et 10-final-status, mets à jour la description de la PR, et rends-moi : ce qui est prouvé (avec la commande ou le test), ce qui reste écrit sans preuve, ce qui attend mes comptes ou mes
décisions, dans cet ordre. Aucune phrase du type "tout est prêt" sans liste des exceptions.

## 5. Règle de fusion de la PR #25
Tu fusionnes la PR #25 vers main (gh pr merge, méthode squash ou merge selon la configuration du dépôt, jamais de force) SEULEMENT SI les trois premières confirmations ci-dessous sont OUI et si la CI est verte
(le job bandit non bloquant mis à part). Sinon tu NE fusionnes PAS : tu me dis exactement ce qui manque. Raison : le code lit des colonnes que la production n'a pas encore ; fusionner avant les migrations
casserait la connexion de tous les utilisateurs.

## CONFIRMATIONS (à remplir avant d'envoyer)
- Sauvegarde de la base de production faite : [OUI / NON]
- Migrations 0131 à 0143 appliquées en production (python scripts/migrate.py puis --apply, depuis mon terminal) : [OUI / NON]
- Variables Render réglées (ENCRYPTION_MASTER_KEY, CONNECTORS_ALLOW_PLATFORM_CREDENTIALS=false, outils d'agents laissés vides) : [OUI / NON]
- Documentation officielle de l'API CinetPay collée ci-dessous : [OUI / NON]
- Comptes de test disponibles (liste) : [...]

DOCUMENTATION CINETPAY (colle ici la page de l'API actuelle, initialisation du paiement, notification, vérification) :
[...]
