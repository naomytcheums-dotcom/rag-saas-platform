# Redis en production (Upstash)

## Ce que Redis fait dans ce projet

- **Rate limiting** (`api/security/rate_limit.py`) -- compteurs glissants
  pour les 5 endpoints d'authentification les plus exposés au
  brute-force. Fail-open : une panne Redis dégrade la protection, elle
  ne bloque jamais les connexions.
- **Celery** (`api/tasks/celery_app.py`) -- broker (file de tâches) et
  result backend, pour tout le traitement en arrière-plan (documents,
  webhooks, facturation mensuelle, etc.).

## Configuration réelle utilisée (Upstash, tier gratuit)

```
RATE_LIMIT_REDIS_URL=rediss://default:<password>@<host>.upstash.io:6379
CELERY_BROKER_URL=rediss://default:<password>@<host>.upstash.io:6379
CELERY_RESULT_BACKEND=rediss://default:<password>@<host>.upstash.io:6379
```

**Point important, vérifié en direct** : le tier gratuit d'Upstash ne
supporte que la base Redis 0 (`SELECT 1` répond réellement
`"Only 0th database is supported!"`). Les 3 URLs ci-dessus utilisent
donc **toutes la même base 0** -- sûr en pratique, parce que les clés du
rate limiting sont toutes préfixées `ratelimit:*` et que les clés
internes de Celery (`celery-task-meta-*`, `_kombu.*`) ne rentrent jamais
en collision avec ce préfixe.

Le mot de passe TCP affiché sur le dashboard Upstash (`redis-cli --tls
-u redis://default:<password>@...`) **n'est pas le même** que le jeton
REST (`UPSTASH_REDIS_REST_TOKEN`) -- vérifié en direct, le jeton REST
échoue l'authentification TCP (`invalid username-password pair`). Il
faut bien récupérer le mot de passe TCP réel (icône œil à côté de
"JETON" dans la section TCP du dashboard), pas le jeton REST.

## Limites du tier gratuit

- 500 000 commandes/mois, 50 Go de bande passante, 256 Mo de stockage.
- Le rate limiting seul reste largement sous cette limite. Un worker
  Celery actif avec beaucoup de tâches peut s'en approcher sous forte
  charge -- à surveiller dans la console Upstash (onglet "Usage").

## Vérification

```
GET /health/ready
```
répond `{"rate_limit_redis": "ok"}` quand Redis est bien joignable, ou
`"unreachable -- rate limiting is NOT currently enforced"` sinon (fail
open honnête, jamais un faux "ok").
