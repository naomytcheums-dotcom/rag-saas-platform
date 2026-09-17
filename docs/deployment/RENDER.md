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

**Conséquence honnête** : le rate limiting est actuellement en mode
dégradé ("fail open", comportement voulu et documenté — voir
`api/security/rate_limit.py`) : les endpoints d'authentification ne
sont PAS protégés contre le brute-force en production tant que ce
n'est pas résolu. Pas un crash, mais une vraie protection manquante.

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
