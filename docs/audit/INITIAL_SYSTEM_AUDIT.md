# RAG SaaS Platform — Initial Audit

Audit statique initial du dépôt présent dans le workspace, le 2026-10-03.
Cette phase n'a modifié aucun code, aucune configuration d'exécution ni aucune
migration et n'a créé aucun commit. Les cinq rapports demandés sont des
artefacts d'audit uniquement.
Les corrections de deux constats sécurité ont été autorisées après cette
photographie initiale; leur état et leurs tests sont consignés dans
[SECURITY_AUDIT.md](./SECURITY_AUDIT.md) et
[PRODUCTION_BLOCKERS.md](./PRODUCTION_BLOCKERS.md).

## 1. Repository Health

- Dépôt Git `main`, HEAD `2e7bfaa` (`2026-09-27`), synchronisé sur le commit
  indiqué comme `origin/main`.
- État initial observé avant création de ces rapports : **130 fichiers suivis
  modifiés** et **140 fichiers non suivis**. Il s'agit de travail préexistant,
  dont de nouveaux modules applicatifs et des migrations; aucune attribution
  de ces changements à cet audit n'est faite.
- `.env`, `frontend/.env.local`, `dump.rdb`, `snyk.exe`, `.venv`, les caches
  Python et les sorties frontend existent localement; les chemins sensibles ou
  volumineux consultés sont ignorés par Git. Leur contenu n'a pas été lu.
- 1 883 chemins suivis au HEAD. Plusieurs worktrees d'agents locaux sont
  enregistrés dans `.git`; leurs contenus n'ont pas été inspectés.
- **Action de sûreté** : conserver l'état tel quel. Ne pas lancer une suite qui
  pourrait utiliser des identifiants du `.env` avant d'avoir vérifié ses
  gardes et l'environnement d'exécution.

## 2. Architecture

- API : FastAPI, SQLAlchemy 2 async, configuration dans `api/config.py`,
  assemblage des routes et lifespan dans `api/main.py`.
- Persistance et tâches : PostgreSQL/pgvector, Alembic, Redis et Celery.
- Interface : Next.js/React/TypeScript sous `frontend/`.
- SDKs : Python, JavaScript, React et Vue sous `sdks/`.
- Inventaire statique : 101 modules de routes, 86 modules de modèles, 280
  fichiers de services, 70 fichiers de sécurité, 48 fichiers de tâches,
  131 migrations, 386 fichiers de tests backend et 52 fichiers de page
  frontend selon le comptage de fichiers. Ces nombres ne prouvent pas que les
  parcours sont opérationnels; certains incluent du travail non suivi.
- La configuration est partagée via `api.config.settings`; le code API crée
  un moteur asynchrone dans `api/database.py`. Un second conteneur Postgres /
  Redis existe dans le compose self-hosted.

## 3. Database

- Les modèles SQLAlchemy sont regroupés dans `api/models/`; Alembic est
  configuré avec `api/alembic/env.py` et `Base.metadata`.
- La suite rapide utilise SQLite en mémoire et crée son schéma depuis les
  modèles. Des tests PostgreSQL distincts existent dans
  `tests/test_postgres_integration.py`.
- L'inventaire statique décrit plusieurs tables d'organisation; la vérification
  systématique, table par table, des clés tenant, contraintes, index et
  cascades reste à faire.
- La connexion à la base n'a pas fourni de version Alembic (`alembic current`
  a terminé en erreur, code 1). La base réelle, son schéma, ses policies RLS et
  ses index ne sont donc pas certifiés.
- Détails : [DATABASE_AUDIT.md](./DATABASE_AUDIT.md).

## 4. Migrations

- 131 fichiers de migration sous `api/alembic/versions/`; `alembic heads`
  retourne `0131 (head)`.
- Les migrations 0125, 0126, 0127, 0128 et 0131 sont présentes dans
  l'arbre courant. Leurs statuts Git diffèrent; leur présence locale n'établit
  ni leur inclusion dans un commit ni leur application à une base.
- Le fichier visant la révision 0132 se trouve sous `scripts/pending/`, pas
  sous `api/alembic/versions/`. Il n'appartient donc pas au graphe Alembic
  actuellement chargé.
- La révision déployée est inconnue; aucune migration n'a été appliquée durant
  cet audit. Ne pas lancer `upgrade`/`downgrade` avant comparaison et sauvegarde.

## 5. Multi-Tenancy

- Les modèles `Organization`, `Document` et `Agent` exposent notamment
  `organization_id`; les routes utilisent des dépendances d'organisation et de
  permissions.
- Les migrations activent RLS à plusieurs endroits; 0131 l'active pour onze
  tables supplémentaires.
- **Limite déterminante documentée et testée par le dépôt** :
  `tests/test_postgres_integration.py` affirme qu'il n'existe aucune policy
  RLS sur le schéma `public` et que le rôle de l'application contourne RLS.
  L'isolation actuelle dépend donc des contrôles applicatifs, et non d'une
  isolation Postgres effective pour ce rôle.
- Aucun scénario vivant A→B / B→A n'a été exécuté pendant cet audit.

## 6. Authentication

- Le dépôt contient JWT, sessions, OAuth, réinitialisation de mot de passe,
  TOTP, WebAuthn, révocation et rotation des clés.
- Routes, modèles, services et tests correspondants existent.
- Aucun parcours login/refresh/révocation contre une base PostgreSQL réelle
  n'a été exécuté; l'intégration et le déploiement réel restent non vérifiés.

## 7. Authorization

- RBAC et permissions d'organisation sont présents sous `api/security/`,
  avec des dépendances utilisées par les routes.
- Un audit spécialisé statique a relevé des chemins de billing/A2A à traiter
  (sections 34-35 et [SECURITY_AUDIT.md](./SECURITY_AUDIT.md)).
- L'existence de tests d'autorisation ne démontre pas l'absence de toutes les
  escalades ou erreurs d'isolation; aucune matrice exhaustive des routes n'a
  encore été testée.

## 8. Billing

- Des modules et routes Stripe et Paystack, les abonnements, factures et
  webhooks existent.
- Les appels réels à Stripe/Paystack, la configuration déployée et les
  webhooks en conditions réelles ne sont pas vérifiés.
- Un chemin de recharge sans paiement est activé par défaut au niveau du code
  lorsque aucun fournisseur n'est résolu; voir P0 conditionnel et les détails
  de sécurité.

## 9. Credits

- Les services de crédits, plafonds de dépenses, BYOK et tests associés sont
  présents.
- Le code présente un risque d'achat gratuit lorsque le déploiement n'a pas de
  fournisseur et conserve le défaut `CREDITS_ALLOW_UNPAID_TOPUP=True`.
- A2A exécute le travail avant de tenter le débit; l'insuffisance au débit est
  interceptée après exécution. Ce comportement est un risque de consommation
  non facturée.

## 10. RAG

- Services visibles pour chunking, embeddings, recherche, pipeline de
  retrieval, MMR, HyDE, multi-query, reranking, citations et filtres.
- La migration 0128 et les modifications du modèle décrivent une colonne
  pgvector/HNSW et un chemin de repli numérique; une migration présente et un
  index déclaré ne prouvent pas que le serveur réel l'utilise.
- Le README documente honnêtement que BM25 rescane les chunks de
  l'organisation et que les mesures disponibles ne couvrent pas le chemin
  pgvector ni la charge HTTP concurrente.
- Pas de benchmark ni d'évaluation qualité exécutés pendant cet audit.

## 11. Documents

- Routes/services de documents, extraction, stockage, imports et tâches
  d'indexation présents; les tests couvrent plusieurs formats et traitements.
- Persistance objet, antivirus éventuel, limites effectives, reprise après
  panne et suppression complète n'ont pas été vérifiés sur des services réels.

## 12. Multimodal

- Modules de médias, vision, recherche visuelle, OCR, audio/vidéo et tests
  correspondants présents.
- La disponibilité et les performances dépendent de binaires, modèles et
  fournisseurs externes; aucune validation de bout en bout avec ces services
  n'a été faite. Statut conservateur : `BLOCKED_EXTERNAL` lorsqu'une
  dépendance réelle est nécessaire.

## 13. Agents

- Modèles, routes, orchestration, outils, mémoire, guardrails, traces et
  factory sont présents dans l'arbre courant.
- Plusieurs éléments sont non suivis ou modifiés; leur présence n'établit pas
  qu'ils sont dans la livraison déployée.
- Pas de création puis exécution persistée d'un agent sur une base et un LLM
  réels pendant cet audit.

## 14. Workflows

- Modèles/migrations, routes, services, tâches Celery, versions et
  exécutions de nœuds sont présents.
- Reprise, idempotence, concurrence, annulation et comportement en panne du
  broker/worker ne sont pas démontrés par une exécution dans cet audit.

## 15. MCP

- Modules client et serveur, découverte, outils intégrés, permissions et
  tests présents.
- Aucun appel à un serveur MCP externe réel n'a été validé. SSRF et
  l'isolation des outils doivent rester dans les priorités de validation.

## 16. A2A

- Un nouveau routeur A2A est présent dans le workspace et monté par le code
  courant. Il n'était pas suivi au HEAD initial.
- Revue spécialisée : le coût A2A est débité après l'exécution; un débit
  insuffisant est seulement journalisé. Risque P1, détails et références dans
  [SECURITY_AUDIT.md](./SECURITY_AUDIT.md).
- Ni l'interopérabilité externe, ni le cycle complet des tâches, ni le coût
  effectif n'ont été testés contre un fournisseur réel.

## 17. Eval Lab

- Datasets, résultats, jobs, comparaisons, échecs et métriques sont représentés
  par des routes, services et migrations.
- L'annotation réelle des données, reproductibilité des runs et validité
  statistique n'ont pas été vérifiées à l'exécution.

## 18. Guardian

- Alerting et seuils qualité ont des modules dédiés.
- Le README limite explicitement l'automatisation : le cycle complet
  détection → explication → proposition → approbation → application →
  rollback n'est pas automatisé de bout en bout.

## 19. Autopsy

- Diagnostics de retrieval, traces et rapports d'échecs sont présents.
- Aucune réponse erronée instrumentée de bout en bout n'a été injectée; une
  cause racine fondée sur les traces n'est pas vérifiée.

## 20. Evolution

- Services d'expériences et d'évolution, contrôles de déploiement/canary,
  UI en cours et benchmark script présents dans le workspace.
- La comparaison reproductible avec un baseline réel et l'absence de
  régression ne sont pas prouvées par ce code statique.

## 21. Voice

- Routes et services de voice et UI dédiés présents.
- Formats, durée, latence, streaming et chaîne STT→RAG→TTS n'ont pas été
  validés avec de vrais fichiers audio et des identifiants fournisseur.

## 22. SDKs

- Répertoires et code de SDK Python, JavaScript, React et Vue présents.
- Des changements préexistants sont visibles dans les SDK Python/JS. Les
  compatibilités avec l'API déployée et les quatre SDK ne sont pas établies
  par la seule présence de tests.

## 23. Frontend

- Application Next.js sous `frontend/app`, composants, client API et pages
  dashboard présents; scripts déclarés pour lint, type-check, build et Vitest.
- Parcours signup → ingestion → agent → chat → citations → évaluation →
  facturation non exécuté dans un navigateur contre l'API.
- Le nombre de fichiers `page.*` ne correspond pas nécessairement au nombre
  de routes utilisables.

## 24. Redis

- Client, cache, rate limiter et compose self-hosted sont présents.
- Redis n'a pas été interrogé. Le comportement de panne et la persistance
  réelle ne sont pas vérifiés.

## 25. Celery

- Tâches et configuration Celery présentes; l'environnement self-hosted
  définit worker et beat.
- Le workflow GitHub planifié lance un worker, mais termine son étape avec
  `|| true`, ce qui neutralise son code de retour non nul et peut masquer une
  panne.
- Pas d'essai de traitement interrompu, de dead-letter ou de duplication.

## 26. LLM Providers

- LiteLLM/configuration providers et tests sont présents.
- Les clés ne sont pas lues ou affichées. Aucune validation réelle
  Anthropic/OpenAI/Mistral/Gemini/Ollama/watsonx; dépendances correspondantes
  classées `BLOCKED_EXTERNAL` jusqu'à test contrôlé avec credentials.

## 27. Observability

- Prometheus, correlation IDs, tracing, Sentry et handlers de logs apparaissent
  dans l'assemblage et les services.
- Aucun backend d'observabilité n'a été connecté; couverture, cardinalité,
  alertes et absence de PII dans les événements ne sont pas mesurées ici.

## 28. Security

- Modules dédiés à JWT, permissions, SSRF, rate limits, encryption, plugins,
  fichiers et journaux présents.
- Une revue spécialisée, statique et limitée au code à haut risque, a identifié
  un top-up gratuit conditionnel et un problème de débit A2A. Elle n'a pas
  validé une base, Redis, un fournisseur ou l'environnement déployé.
- La couverture RLS est défense en profondeur seulement pour les rôles
  non-bypass; le rôle applicatif contourne RLS et aucune policy n'est définie.

## 29. Performance

- Le README reconnaît une mesure portable à 100 et 1 000 documents seulement;
  pas de mesure PostgreSQL/pgvector, HTTP concurrente, p95/p99 ni volumétrie
  10k/50k démontrée.
- Aucune optimisation ni modification de seuil n'a été faite.

## 30. Deployment

- Dockerfiles API/prototype, compose self-hosted, Render, reverse proxy et
  workflows CI sont présents.
- Le compose racine lance le prototype Streamlit `nova`, pas l'API SaaS;
  utiliser le compose self-hosted dédié pour l'application API.
- Aucun build d'image, déploiement, redémarrage ou restauration n'a été fait.

## 31. Testing

- 386 fichiers `test*.py` recensés, plus des tests frontend et SDK.
- Les tests backend incluent des fixtures SQLite, mocks et tests d'intégration
  PostgreSQL séparés; les tests PostgreSQL sautent le module lorsque la base
  est injoignable.
- La présence d'une suite et les résultats anciens consignés dans
  `docs/audit/` ne constituent pas un résultat pour le workspace courant.
- Pas de tests, lint, build ou benchmark exécutés dans cette phase afin de
  rester en inventaire et de ne pas déclencher d'appels depuis les
  configurations locales.

## 32. Documentation

- Documentation abondante dans `docs/`, plus README et ROADMAP.
- Les nombres annoncés dans README (98 routes, 130 migrations, 376 tests)
  diffèrent de l'inventaire statique courant (101 modules de routes, 131
  migrations, 386 fichiers de tests).
- `docs/developer/DATABASE.md` s'arrête à 0108; les rapports existants datés
  ne certifient pas l'état du workspace courant.

## 33. Commercial Readiness

- Billing, crédits, pricing, white-label, domaines, SDKs et documentation
  utilisateur existent.
- Paiement réel, obligations légales, support, limites contractuelles,
  propriété des domaines et délivrance SSL ne sont pas prouvés par cette
  inspection. Intégrations de paiement : `BLOCKED_EXTERNAL`.

## 34. P0 Blockers

1. **Recharge gratuite conditionnelle** — `api/config.py` déclare
   `CREDITS_ALLOW_UNPAID_TOPUP=True`; le endpoint autorise le top-up si aucun
   fournisseur n'est configuré/résolu. Le code de production n'a pas été
   interrogé : traiter comme bloqueur de livraison jusqu'à confirmation que
   le fournisseur est obligatoire ou que la variable est explicitement
   désactivée en production.
2. **État réel de la base inconnu** — `alembic current` a échoué (code 1), sans
   révision exploitable; ne pas affirmer que les migrations sont appliquées ni
   déployer une migration à l'aveugle.

## 35. P1 Issues

1. **Débit A2A après consommation** — le handler exécute d'abord la tâche;
   une insuffisance de crédits au débit est interceptée. Cela rend possible
   une exécution LLM non facturée dans certaines conditions.
2. **Isolation RLS non effective pour le rôle API** — policies absentes et
   rôle applicatif BYPASSRLS selon les tests du dépôt; l'isolation repose sur
   les filtres et autorisations de l'application. La vérification complète
   des accès inter-tenant est en attente.
3. **Intégrité du worktree** — 270 changements préexistants sur `main` :
   établir leur provenance et leur destination avant tout commit ou
   comparaison à une baseline.

## 36. P2 Issues

1. Le workflow de worker Celery utilise `|| true` et peut masquer l'échec du
   worker.
2. Performance RAG non validée aux tailles et charges de production; BM25
   décrit comme rescannant les chunks de l'organisation.
3. Les 0132 sont sous `scripts/pending/`, hors du graphe Alembic.
4. Pas de validation de bout en bout documentée ici pour les flux
   document→embedding→retrieval, paiement/webhook, workflow ou SDK.

## 37. P3 Issues

1. Compteurs README et documentation de base de données en retard sur
   l'inventaire du workspace.
2. État local inclut caches, environnements, dump Redis et binaire ignorés;
   ils n'ont pas été inspectés et ne doivent pas être ajoutés à Git.

## 38. Recommended Execution Order

1. Sauvegarder et inventorier séparément les modifications déjà présentes;
   confirmer la cible de livraison sans nettoyer le worktree.
2. Vérifier les variables et le profil de billing production sans exposer
   leurs valeurs; sécuriser le réglage de top-up avant vente.
3. Obtenir une connexion de lecture à la base cible; enregistrer sa révision
   Alembic, catalogues, RLS et index; examiner 0131/0132 sans les appliquer.
4. Corriger et tester le débit A2A et le flux billing/webhook avec des
   fixtures de test isolées.
5. Établir l'isolation tenant par tenant (tests applicatifs puis rôle DB et
   policies), sans présumer qu'une migration suffit.
6. Exécuter les tests les plus sûrs et ciblés en environnement isolé; auditer
   les intégrations et parcours E2E ensuite.
7. Mesurer le retrieval/pgvector, les tâches, la charge, les déploiements et
   restaurations, puis actualiser les documents et la matrice avec les preuves.
