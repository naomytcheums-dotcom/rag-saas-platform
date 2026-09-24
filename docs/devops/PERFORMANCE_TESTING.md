# Performance Testing

Deux niveaux de mesure de performance, complementaires :

## 1. Metriques continues (Prometheus)

Le serveur expose deja, en continu, les metriques de latence et de
throughput reelles a `GET /metrics` (format Prometheus text).

Voir `api/monitoring.py` :

- `http_request_duration_seconds` -- histogramme des durees, par
  `method` et `path` (route template, pas le path litteral -- evite
  l'explosion de cardinalite).
- `http_requests_total` -- counter par `method`/`path`/`status_class`.
- `celery_tasks_total` -- counter par `task_name`/`outcome`.

**Buckets par defaut** : 5ms, 10ms, 25ms, 50ms, 75ms, 100ms, 250ms,
500ms, 750ms, 1s, 2.5s, 5s, 7.5s, 10s.

**En production multi-worker** (Gunicorn), le mode multiprocess
s'active automatiquement via `PROMETHEUS_MULTIPROC_DIR` -- voir
`gunicorn.conf.py`.

**Calculer p50/p95/p99** depuis Prometheus :
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

text

## 2. Load test a la demande (`scripts/loadtest.py`)

Script autonome, sans dependance externe (juste `httpx`).

### Usage

```bash
# 500 requetes, 20 clients concurrents
python scripts/loadtest.py --url http://localhost:8000/health --requests 500 --concurrency 20

# Mode JSON (pour CI / dashboards)
python scripts/loadtest.py --url http://localhost:8000/health --requests 200 --concurrency 10 --json

# Test d'un endpoint specifique
python scripts/loadtest.py --url http://localhost:8000/metrics --requests 100 --concurrency 5
Rapport
Le script affiche :

Throughput (req/s)

Latence : min, mean, p50, p95, p99, max, stdev (en ms)

Nombre de succes / echecs

Echantillon d'erreurs si echecs

Codes de sortie
0 -- tous les requetes ont reussi

1 -- au moins un echec (le rapport s'affiche quand meme)

2 -- erreur de setup (serveur injoignable, URL invalide)

3. Interpretations
En local (Windows + MSYS) : la latence est artificiellement
elevee (1-3s meme sur /health) a cause de la pile reseau Windows.
Ce n'est pas un probleme de code.

En production (Linux + Gunicorn) : /health repond en < 5ms.
Un p95 > 100ms sur un endpoint CRUD est un signal d'alerte.

4. CI
Pour ajouter un smoke test de perf en CI :

yaml
- name: Load test smoke (health only)
  run: |
    python scripts/loadtest.py --url http://localhost:8000/health \
      --requests 100 --concurrency 10 --json > loadtest.json
    cat loadtest.json
Le script n'echoue pas la CI sur une latence elevee (juste sur
les echecs reseau) -- l'objectif est de mesurer, pas de bloquer.

Voir aussi
api/monitoring.py -- implementation des metriques

gunicorn.conf.py -- config multi-worker

docs/install/OBSERVABILITY_STACK.md -- stack Grafana/Prometheus complete

docs/install/SCALING.md -- scaling horizontal
