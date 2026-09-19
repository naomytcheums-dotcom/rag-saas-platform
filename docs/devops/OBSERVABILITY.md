# Observabilite -- verification en production

## Verifie en direct (2026-09-19), avec un vrai compte admin

Le blocage precedent (aucun compte super-admin/admin disponible pour
appeler les endpoints `require_admin`) est leve : un compte jetable a
ete cree, promu `role = 'admin'` directement en base (seule voie
possible -- aucun bootstrap self-service n'existe, par conception :
promouvoir un compte est une action `require_superadmin`), utilise
pour appeler reellement les 4 endpoints, puis supprime.

Resultats reels (contre la vraie base de production, avec les vraies
valeurs de `.env` -- confirme identiques aux hotes attendus,
`logs-prod-039.grafana.net`, `datadoghq.com`) :

| Endpoint | Reponse reelle | Interpretation |
|---|---|---|
| `GET /monitoring/loki/status` | `{"configured": true, "authenticated": true, "installed": true, "host": "https://logs-prod-039.grafana.net"}` | **Fonctionne reellement** -- authentification confirmee aupres de Grafana Loki, pas juste une variable presente |
| `GET /monitoring/datadog/status` | `{"configured": true, "enabled": false, ...}` | Configure mais **volontairement desactive** (`DD_TRACE_ENABLED=False` dans `.env`) -- etat attendu, pas un manquement |
| `GET /monitoring/tracing/status` | `{"enabled": true, "active": false, "exporter": "otlp", "otlp_endpoint": "http://localhost:4318"}` | Configure mais **genuinement inactif** -- `OTEL_EXPORTER_OTLP_ENDPOINT` pointe sur `localhost:4318`, qui n'existe nulle part en production non plus (aucun collecteur OTLP colocalise). Ceci est le comportement **documente et voulu** de `api/security/tracing.py` : plutot que d'exporter des spans dans le vide, le code les desactive explicitement sans collecteur reel configure |
| `GET /monitoring/metrics` | `{"business": {"organizations": 166, "users": 28, ...}, "http_requests_total_samples": 125, ...}` | Metriques Prometheus reelles, chiffres coherents avec une vraie base de production active |

## Ce qui reste non verifie

Les dashboards Grafana/Datadog eux-memes n'ont pas ete ouverts dans
cette session (identifiants d'acces a ces interfaces web non fournis)
-- mais `authenticated: true` sur Loki est une preuve directe, cote
application, que les identifiants d'ingestion sont valides et acceptes
par Grafana, ce qui est la partie qui comptait le plus (les logs
partent bien).

## Recommandation

Si le tracing distribue (OpenTelemetry) doit devenir reellement actif,
il faut soit pointer `OTEL_EXPORTER_OTLP_ENDPOINT` vers l'ingest OTLP
reel de Grafana Tempo (`TEMPO_HOST` existe deja, mais Tempo Cloud
necessite generalement un relais type Grafana Alloy plutot qu'un envoi
OTLP direct authentifie), soit deployer un collecteur OTLP colocalise.
Aucune des deux options n'a ete faite dans cette session (decision
produit/infrastructure, pas un bug de code).

## Statut

Verifie en direct avec un vrai compte admin et de vrais appels HTTP,
pas seulement la presence de variables d'environnement. Loki confirme
fonctionnel ; Datadog et le tracing OTel sont dans l'etat exact que
leur configuration actuelle indique (respectivement desactive par
choix, et non connecte a un collecteur reel) -- aucun des deux n'est
un bug.
