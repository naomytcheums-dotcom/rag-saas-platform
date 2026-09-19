# Observabilite -- verification en production

## Ce qui a ete verifie reellement (2026-09-19)

Toutes les variables d'environnement attendues par la stack
d'observabilite (`api/config.py`) sont bien **presentes par leur nom**
sur Render (extrait direct des champs du formulaire, pas une
supposition) : `DD_API_KEY`, `DD_APP_KEY`, `DD_SITE`, `DD_TRACE_ENABLED`,
`DD_LLMOBS_ML_APP` (Datadog) ; `LOKI_HOST`, `LOKI_USERNAME`,
`LOKI_PASSWORD` ; `PROMETHEUS_HOST`, `PROMETHEUS_USERNAME`,
`PROMETHEUS_PASSWORD` ; `TEMPO_HOST`, `TEMPO_USERNAME`,
`TEMPO_PASSWORD` ; `OTEL_ENABLED`.

## Ce qui n'a PAS pu etre verifie dans cette session, honnetement

Les **valeurs** de ces variables restent masquees sur Render (points
noirs), et 3 endpoints reels existent pour verifier leur etat cote
application (`api/routers/observability.py`) :

- `GET /monitoring/tracing/status`
- `GET /monitoring/loki/status`
- `GET /monitoring/datadog/status`

Les trois sont proteges par `require_admin` -- le compte de test utilise
dans cette session (`celery-test-...@example.com`) est proprietaire
d'une organisation, pas super-administrateur de la plateforme, et
recoit donc un refus d'acces (comportement RBAC correct, deja verifie
plus tot dans l'audit -- voir Securite). Aucun compte super-admin n'a
ete cree ou fourni dans cette session.

`GET /metrics` (Prometheus, public par conception) et les 3 endpoints
`/monitoring/*/status` ci-dessus n'ont pas pu etre appeles avec succes
dans le temps imparti de cette session (l'instance Render, sur le tier
gratuit, se met en veille apres inactivite et le reveil a pris plus de
temps que le budget restant de cette verification).

Aucun acces aux dashboards Grafana/Datadog eux-memes (identifiants non
fournis dans cette session) -- impossible de confirmer que des logs/
metriques/traces reels y arrivent, meme si les variables sont bien
configurees cote Render.

## Ce qu'il faut faire pour verifier completement

1. Se connecter avec un compte super-admin (ou en creer un) et appeler
   les 3 endpoints `/monitoring/*/status` ci-dessus -- chacun renvoie un
   etat reel ("configured"/"reachable" ou une erreur precise), pas
   juste "la variable existe".
2. Ouvrir les dashboards Grafana/Datadog reels correspondant a ces
   identifiants et confirmer qu'un evenement recent (ex. le deploiement
   de cette session) y apparait.

## Statut

Partiellement verifie : configuration presente (noms de variables),
fonctionnement reel non confirme faute d'acces admin/dashboards dans
cette session.
