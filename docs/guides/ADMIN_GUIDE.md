# Guide administrateur

Ce document décrit les fonctionnalités réellement présentes dans le code du dépôt et doit être interprété comme un guide de référence technique, pas comme une promesse d'un hébergement SaaS complet. Les points dépendant de services externes (S3, OTLP, modèles LLM/embedding, e-mail transactionnel) sont signalés comme non vérifiés en conditions réelles.

## 1. Accès et rôles

Le backend utilise des rôles d'organisation et des permissions de type `require_permission(...)` dans le code. Les routes de gestion d'organisation et de paramètres sont accessibles à partir des modules de `api/routers`.

Rôles observés dans le modèle et la logique de sécurité :
- Owner
- Admin
- Manager
- Member
- Viewer

Les permissions de lecture/écriture pour les documents, paramètres, recherche et observabilité sont vérifiées par `api/security/permissions.py` et par les dépendances des routeurs comme `require_org_member`, `require_org_owner` ou `require_permission("settings:manage")`.

## 2. Gestion des organisations

Les routes d'organisation se trouvent dans `api/routers/organizations.py` et les helpers de sécurité dans `api/security/organizations.py`.

Fonctions pratiques visibles dans le code :
- création d'une organisation
- ajout et suppression de membres
- gestion des rôles
- quotas et limites d'utilisation
- paramètres d'organisation
- vérification de l'appartenance d'un utilisateur à une organisation

Les limites par défaut sont définies dans `api/config.py` (quotas de documents, espaces de travail, utilisateurs, stockage, appels API, etc.).

## 3. Documents et ingestion

Les routes de documents sont dans `api/routers/documents.py`. Elles couvrent :
- upload simple de fichiers
- import depuis URL
- import depuis sitemap
- import depuis GitHub / issues / Google Drive / Google Docs / Notion / Confluence / OneDrive
- traitement de lot
- tags, versions et historique
- suppression douce et suppression permanente
- vérification de modification du document

Avant l'enregistrement d'un document, `api/security/documents.py` valide le type et la taille du fichier et, si `CLAMAV_ENABLED` est vrai, appelle `api/services/clamav.py` pour un scan antivirus.

Le traitement réel de l'extraction est orchestré par `process_document()` et la logique de chunking/embedding se trouve dans le pipeline de documents.

## 4. Recherche et RAG

L'endpoint de recherche multi-tenant est :
- `POST /organizations/{org_id}/search`

Le handler réel se trouve dans `api/routers/search.py` et appelle `search_with_context()` de `api/services/retrieval_pipeline.py`.

Les paramètres observés incluent :
- `query`
- `top_k`
- `strategy`
- `reranker`
- `score_threshold`
- `filters`

Le cache BM25 par organisation est contrôlé par `BM25_INDEX_CACHE_ENABLED` dans `api/config.py` et est désactivable si nécessaire.

## 5. Observabilité et dépannage

Les endpoints d'observabilité existent dans `api/routers/observability.py`.

Un sous-ensemble visible :
- `/monitoring/metrics`
- `/monitoring/tracing/status`
- `/monitoring/loki/status`
- `/alerting/channels`
- `/alerting/rules`
- `/alerting/incidents`

La corrélation de requêtes est gérée dans `api/security/logging_correlation.py` via `X-Request-ID` et un `LogRecord` factory. La propagation dans les logs et les réponses est réelle ; le support OpenTelemetry est présent et désactivé par défaut (`OTEL_ENABLED=False`) sauf configuration explicite.

## 6. Paramètres globaux 

Les réglages de runtime sont dans `api/config.py`.

Plusieurs variables concernent les intégrations externes et doivent être configurées selon l'environnement :
- `DATABASE_URL`
- `RATE_LIMIT_REDIS_URL`
- `CACHE_REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `S3_*` ou équivalents de stockage
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.
- `CLAMAV_*` si l'analyse antivirus est activée

Le fichier `.env` n'est pas stocké dans le dépôt ; le projet lit des variables d'environnement via Pydantic Settings.

## 7. Sécurité

Le dépôt contient des éléments de sécurité vérifiés dans le code, notamment :
- SSRF guards dans `api/security/ssrf*`
- middleware de corrélation de requêtes
- logging structuré
- protections de droits par organisation
- scan antivirus optionnel via clamav

Les points dépendant d'un service externe ou d'un environnement réel ne sont pas certifiés ici : S3, OTLP, modèles LLM, e-mail de production, certificats SSL / DNS, etc.

## 8. Commandes utiles

Les outils de validation visibles dans le dépôt sont principalement :
- `pytest ...`
- `ruff check api/`
- `bandit -r api -c pyproject.toml`
- `docker compose up`

Le dépôt n'implémente pas une automatisation de déploiement complète dans le code lui-même ; la mise en production reste un élément d'opérationnalisation externe.

## 9. Limites de validation

Les éléments suivants sont signalés comme non vérifiés en conditions réelles :
- stockage objet S3/Blob
- intégration externe de modèles LLM/embedding
- export OTLP vers un collecteur réel
- délivrabilité e-mail réelle
- opérations de production de secrets / clés cloud
