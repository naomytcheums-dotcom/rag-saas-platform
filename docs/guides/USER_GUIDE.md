# Guide utilisateur

Ce guide décrit les écrans et flux réellement présents dans le code du dépôt. Il ne prétend pas couvrir des fonctionnalités non implémentées ou des services qui n'ont pas été validés en production.

## 1. Créer un compte et rejoindre une organisation

La logique d'authentification est dans `api/routers/auth.py` et la sécurité associée dans `api/security/auth*`.

Étapes typiques :
- inscription avec email + mot de passe
- confirm création de compte
- génération de jeton d'accès
- adhésion à une organisation selon les permissions du système

Les permissions et le rôle de l'utilisateur sont ensuite vérifiés par les dépendances FastAPI et les helpers de sécurité présents dans `api/security/organizations.py`.

## 2. Gérer des documents

L'upload de documents passe par `POST /organizations/{org_id}/documents` et est accessible aux rôles autorisés. Le code valide le contenu avant stockage et stocke ensuite le document dans la base et le stockage objet associé.

Le document peut ensuite être :
- listé
- récupéré par ID
- tagué
- consulté en historique
- supprimé doucement
- supprimé définitivement par un administrateur/owner

Le code realiste est dans `api/routers/documents.py` et `api/security/documents.py`.

## 3. Rechercher dans la base documentaire

Les utilisateurs autorisés peuvent appeler :
- `POST /organizations/{org_id}/search`

Le backend exécute la recherche sur les chunks de l'organisation et retourne les résultats dans un format structuré (`SearchResponse`).

Les filtres et les stratégies peuvent être choisis par l'appelant dans le payload, selon les schémas de recherche exposés par `api/schemas/search.py`.

## 4. Explorer les tableaux de bord et métriques

Une série d'endpoints d'observabilité est disponible pour les administrateurs du système :
- `/monitoring/metrics`
- `/monitoring/tracing/status`
- `/alerting/rules`
- `/alerting/incidents`

Ces routes sont visibles dans `api/routers/observability.py`.

## 5. Personnaliser l'apparence de l'organisation

Les routes de white-label sont disponibles dans `api/routers/white_label.py`.

La configuration possible comprend :
- activation/désactivation du branding du produit
- domaine personnalisé
- vérification de domaine
- email personnalisé
- logo / favicon

Les endpoints sont exposés par la route `.../whitelabel/...` et par les anciennes routes `.../white-label`.

## 6. Sécurité et validation

Le dépôt applique des contrôles de sécurité sur les uploads et l'accès. Les éléments réellement présents incluent :
- validation du contenu uploadé
- validation des filtres / permissions d'organisation
- throttling par organisation pour les uploads/requêtes
- scan antivirus optionnel avec ClamAV
- X-Request-ID et logging structuré

## 7. Limites connues

Les éléments suivants sont signalés comme non vérifiés en conditions réelles à ce stade :
- stockage S3 / objet backend réel
- intégration de modèles de génération ou d'embedding externe
- export OTLP vers un collecteur réel
- flux de livraison e-mail en production

## 8. Questions fréquentes

### Puis-je importer des fichiers PDF, DOCX, TXT et Markdown ?
Oui, le code ajoute explicitement ces types dans la validation et le pipeline d'extraction.

### La recherche est-elle multi-tenant ?
Oui, la recherche est orbitée par `organization_id` et les permissions sont vérifiées dans le routeur.

### Y a-t-il un cache de recherche ?
Oui, `BM25_INDEX_CACHE_ENABLED` existe et est activé par défaut dans `api/config.py` pour les indexes BM25 par organisation.

### Est-ce que le système est prêt pour l'usage de production ?
Le dépôt contient de nombreuses fonctionnalités, mais certaines intégrations externes demandent encore une validation opérationnelle distincte dans un environnement réel.
