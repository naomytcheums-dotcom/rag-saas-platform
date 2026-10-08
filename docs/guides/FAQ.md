# FAQ

## Cette plateforme utilise-t-elle vraiment le stockage S3 ?
Le dépôt contient des utilitaires de stockage et des points d'intégration pour le stockage objet, mais les opérations d'un backend S3 réel doivent être validées dans l'environnement d'exécution ciblé. Le code ne prétend donc pas avoir une vérification de production opérée ici.

## Est-ce que le dépôt tire réellement des modèles externes ?
Des variables comme `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` et d'autres clés de modèle existent dans `api/config.py`, et le code expose des intégrations de providers. Toutefois, le fonctionnement complet de ces intégrations dépend de la configuration du runtime réel et de la disponibilité des services externes.

## Le scan antivirus est-il activé par défaut ?
Non. `CLAMAV_ENABLED` est désactivé par défaut dans `api/config.py`. Le scan est appelé seulement si le flag est activé.

## Quelle est la bonne configuration pour ClamAV ?
Le code accepte :
- `CLAMAV_SOCKET_PATH`
- `CLAMAV_HOST` + `CLAMAV_PORT`
- `CLAMAV_TIMEOUT_SECONDS`
- `CLAMAV_REQUIRED`

Le service utitise `api/services/clamav.py` pour se connecter à clamd et la route `upload_document` appelle le scanner avant l'enregistrement du document.

## La recherche est-elle isolée par organisation ?
Oui. La recherche est appelée avec `organization_id` et les permissions/ownership sont vérifiés avant appel. Le cache BM25 est également par organisation, avec `BM25_INDEX_CACHE_ENABLED` exposé dans `api/config.py`.

## Les logs sont-ils corrélés aux requêtes ?
Oui. `api/security/logging_correlation.py` ajoute un `X-Request-ID` aux réponses et lie chaque log à cet identifiant via un `LogRecord` factory. La propagation a été conçue pour être observée dans le backend et les traces associées.

## Le support OpenTelemetry est-il actif ?
Le code contient `api/security/tracing.py` et des réglages `OTEL_*` dans `api/config.py`, mais il est désactivé par défaut (`OTEL_ENABLED=False`).

## Le dépôt contient-il des documents de marketing ?
Oui, mais ils sont documentés comme des supports de proposition et de comparaison, pas comme des affirmations de niveau production sans validation. Les documents commerciaux dans `docs/commercial/` doivent être lus comme des options de positionnement, pas comme un contrat de fonctionnalités.

## Qu'est-ce qui n'est pas vérifié ici ?
- intégration S3/Blob ou Cloud Storage réelle
- modèles LLM/embedding en production
- e-mail transactionnel/marketing réel
- OpenTelemetry vers un collecteur live
- validation DNS/certificats réaliste d'un domaine personnalisé
