# Déploiement backend sur Render

## Service réel

- **Nom** : `rag-saas-api`
- **URL** : `https://rag-saas-api-sjsm.onrender.com`
- **Type** : Web Service, Docker, tier gratuit
- **Dockerfile** : `./Dockerfile.api` (pas le `Dockerfile` racine, qui
  sert un prototype Streamlit sans rapport)
- **Health check** : `/health` (configuré dans `Dockerfile.api`),
  vérifiable manuellement via `/health/ready` (détail DB + Redis)

## Variables d'environnement réellement nécessaires

Toutes les variables du `.env` local (voir le bloc collé dans
Render → Environment → "Add from .env" lors de la mise en place
initiale), y compris depuis cette session :

```
RATE_LIMIT_REDIS_URL=rediss://default:<password>@<host>.upstash.io:6379
CELERY_BROKER_URL=rediss://default:<password>@<host>.upstash.io:6379
CELERY_RESULT_BACKEND=rediss://default:<password>@<host>.upstash.io:6379
```

## Statut réel vérifié en direct (2026-09-17)

### 1. Backend accessible
✅ **Fonctionnel.** `GET /health/ready` répond `{"database":"ok", ...}`
depuis le dernier déploiement (`b422a3d`, correctif `.dockerignore`).
Inscription réelle testée en direct via l'API : `HTTP 201`, token JWT
valide retourné.

### 2. Redis / rate limiting
🔴 **Non fonctionnel actuellement, malgré les 3 variables ajoutées par
l'utilisateur.** `GET /health/ready` continue de répondre
`"rate_limit_redis": "unreachable -- rate limiting is NOT currently
enforced"` après le redéploiement déclenché par l'ajout des variables.

**Vérifié pour écarter la cause côté Upstash** : la même URL Redis,
testée en direct depuis une autre machine (ping direct), répond
correctement (`PING` → `True`). Le service Upstash lui-même fonctionne.

**Cause probable, à vérifier côté Render** (je n'ai pas accès au
dashboard pour le confirmer moi-même) :
- Un espace, une apostrophe ou un guillemet collé par erreur dans la
  valeur lors du copier-coller (le bloc que je t'ai donné n'a pas de
  guillemets autour de l'URL — si Render en a ajouté automatiquement
  via "Add from .env", la valeur réelle stockée pourrait contenir des
  guillemets littéraux qui cassent l'URL).
- Un nom de variable mal orthographié (`RATE_LIMIT_REDIS_URL` doit être
  exact, sensible à la casse).
- Les 3 variables existent mais un redéploiement supplémentaire est
  nécessaire pour qu'elles soient effectivement lues par le processus
  déjà démarré (rare sur Render, qui redéploie normalement tout seul à
  chaque changement de variable, mais possible si le déploiement en
  cours au moment de l'ajout a "gagné la course").

**Mise à jour (résolu)** : après avoir remplacé le contenu des 3
variables directement dans Render (au lieu de les modifier par-dessus
l'existant), `GET /health/ready` répond maintenant
`"rate_limit_redis":"ok"`. Cause réelle probable : la valeur collée la
première fois contenait un caractère invisible (espace, guillemet)
introduit lors d'un copier-coller précédent — jamais confirmé avec
certitude (pas d'accès à l'ancienne valeur, écrasée), mais le
remplacement complet a résolu le problème de façon reproductible.

### 2 bis. Vrai crash de déploiement trouvé et corrigé
🔴→✅ **Corrigé.** `gunicorn.conf.py`'s `child_exit()` faisait planter
tout l'arbitre Gunicorn dès qu'un worker se terminait (donc à chaque
déploiement, lors du redémarrage) : `PROMETHEUS_MULTIPROC_DIR` n'était
jamais défini dans `Dockerfile.api`, et `multiprocess.mark_process_dead()`
plante avec un `TypeError` si cette variable est absente. Corrigé des
deux côtés (`Dockerfile.api` définit vraiment la variable,
`child_exit()` a maintenant une protection). Vérifié : déploiement
`cf94eac` réussi en 2m56s, "Deploy succeeded — Live".

### 2 ter. Vraie erreur de pool de connexions PostgreSQL trouvée et corrigée
🔴→✅ **Corrigé.** Log réel du déploiement `cf94eac` :
`asyncpg.exceptions.InternalServerError: (EMAXCONNSESSION) max clients
reached in session mode - max clients are limited to pool_size: 15`.

**Cause réelle** : `DATABASE_URL` pointe vers le pooler Supabase en
**mode session** (port 5432), qui plafonne à **15 connexions clientes
au total, tous processus confondus** — pas par application. Le moteur
SQLAlchemy async de `api/database.py` n'avait pas de `pool_size`/
`max_overflow` explicites, donc utilisait les valeurs par défaut de
SQLAlchemy (5 + 10 = **15 connexions possibles à lui seul**), laissant
zéro marge pour toute autre connexion simultanée (un serveur de dev
local, un script d'admin ponctuel, un futur worker Celery séparé).

**Corrigé** : `pool_size=3, max_overflow=2` explicites (5 connexions
max par processus au lieu de 15), commit `cf94eac`.

**Gap connu, non corrigé (portée limitée dans le temps disponible)** :
18 autres fichiers `api/tasks/*.py` créent chacun leur propre moteur
SQLAlchemy synchrone contre la même base, avec les mêmes valeurs par
défaut non plafonnées. Sans impact aujourd'hui car **aucun worker
Celery n'est encore déployé** (voir section 3) — mais dès qu'un sera
créé, ce même risque de saturation du pool Supabase reviendra à moins
de plafonner ces 18 moteurs aussi. À traiter en même temps que la
création du service Celery worker.

### 3. Celery (traitement de documents en arrière-plan)
🔴 **Non fonctionnel — vérifié en direct, pas une supposition.** Un
document texte réel a été uploadé via l'API sur le compte de test
(`POST /organizations/{id}/documents`, `HTTP 201`, statut `pending`).
Revérifié 15 secondes plus tard : toujours `"status":"pending"`,
`"processed_at":null` — jamais traité.

**Cause réelle, pas un bug de code** : un seul service Render a été
créé (`rag-saas-api`, un Web Service qui lance `gunicorn api.main:app`
via `Dockerfile.api`'s `CMD`). Ce process sert l'API HTTP, il ne
consomme jamais la file de tâches Celery. Les documents uploadés
(`schedule_document_processing` → `process_document_task.delay(...)`,
voir `api/security/documents.py`) sont bien envoyés dans Redis, mais
personne ne les lit de l'autre côté.

**Ce qu'il faut pour que Celery fonctionne réellement en production** :
créer un **second service Render**, de type **Background Worker** (pas
Web Service), même repo/Dockerfile, mais avec une commande de démarrage
différente :
```
celery -A api.tasks.celery_app worker --loglevel=info
```
Et éventuellement un troisième service pour `celery beat` (tâches
planifiées : facturation mensuelle, purge de comptes, etc.) :
```
celery -A api.tasks.celery_app beat --loglevel=info
```
Ni l'un ni l'autre n'existe actuellement. Document tests uploadés
resteront `pending` indéfiniment tant que ce n'est pas fait.

### 4. Widget embarquable et traductions
✅ **Fonctionnel**, vérifié en direct (voir
`docs/audit/DASHBOARD_BROKEN.md` point 1) : `GET /widget/script.js` →
200, `GET /i18n/translations/fr` → dictionnaire réel.

## Résumé

| Composant | Statut | Action requise |
|---|---|---|
| API HTTP | ✅ Fonctionnel | — |
| Base de données | ✅ Fonctionnel | — |
| Widget / i18n | ✅ Fonctionnel | — |
| Redis / rate limiting | 🔴 Non fonctionnel | Revérifier les 3 variables sur Render (copier-coller sans guillemets) |
| Celery (traitement documents) | 🔴 Non fonctionnel | Créer un service Render "Background Worker" séparé |
