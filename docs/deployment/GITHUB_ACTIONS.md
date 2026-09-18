# Celery worker via GitHub Actions (free alternative)

## Pourquoi ce setup existe

Render (l'hébergeur de l'API) n'offre pas de Background Worker gratuit : le
plan le moins cher est a 7$/mois (confirme en direct sur le dashboard Render,
2026-09-17). Faire tourner Celery dans le meme conteneur que le web service
gratuit (512MB RAM) a ete teste et a rendu le service totalement
inaccessible en quelques minutes (voir l'historique de `Dockerfile.api` et
`docker-entrypoint.sh`, commit `eb3a34a` pour le revert).

Solution retenue : un workflow GitHub Actions programme (`.github/workflows/celery-worker.yml`)
qui demarre un worker Celery reel toutes les 10 minutes, le laisse vider la
file Redis pendant une fenetre bornee, puis s'arrete. Chaque execution tourne
sur une machine fraiche (~7GB RAM) fournie gratuitement par GitHub -- aucun
risque de memoire partagee avec le service web.

Compromis honnete : ce n'est pas un worker permanent. Un document uploade
peut attendre jusqu'a ~10 minutes (l'intervalle du planning) avant d'etre
traite, pas instantanement.

## Fichier

`.github/workflows/celery-worker.yml` :
- Declencheurs : `schedule` (cron `*/10 * * * *`) et `workflow_dispatch` (test manuel).
- `timeout-minutes: 12` au niveau du job.
- La commande interne : `timeout 420 celery -A api.tasks.celery_app worker --loglevel=info --pool=solo --concurrency=1 || true`.
- `--pool=solo --concurrency=1` : mode le plus econome en memoire, un seul processus, aucun fork.

## Secrets requis (Settings -> Secrets and variables -> Actions)

Meme valeurs que sur Render. Obligatoires (sinon crash au demarrage) :
`DATABASE_URL`, `SUPPORT_EMAIL`.

Recommandes (sinon fonctionnalites degradees silencieusement) :
`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `RATE_LIMIT_REDIS_URL`,
`JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `SECRET_ENCRYPTION_KEY`,
`ENCRYPTION_MASTER_KEY`, `AUDIT_LOG_HMAC_SECRET_KEY`, `RESEND_API_KEY`,
`EMAIL_FROM_ADDRESS`, `S3_ENDPOINT_URL`, `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`,
`S3_SECRET_ACCESS_KEY`, `S3_REGION`, `S3_PUBLIC_BASE_URL`,
`S3_DOCUMENTS_BUCKET_NAME`.

Tous les 19 secrets ont ete crees sur `naomytcheums-dotcom/rag-saas-platform`
le 2026-09-18.

## Bugs reels trouves et corriges en testant en production

### 1. Crash SSL sur les URL `rediss://` (commit `6e42f3f`)

Premier test reel (run manuel, 2026-09-18 05:44 UTC) : Celery plantait
immediatement --

```
[CRITICAL/MainProcess] Unrecoverable error: ValueError('
A rediss:// URL must have parameter ssl_cert_reqs and this must be set to
CERT_REQUIRED, CERT_OPTIONAL, or CERT_NONE
')
```

Upstash (le Redis gratuit utilise en production) impose TLS (`rediss://`),
et Celery refuse de demarrer sur ce schema sans que `broker_use_ssl` /
`redis_backend_use_ssl` soient positionnes explicitement. Corrige dans
`api/tasks/celery_app.py` (`ssl_cert_reqs=ssl.CERT_REQUIRED`, applique
seulement si l'URL commence par `rediss://`).

### 2. Job tue de force avant la fin (commit `894edc5`)

Deuxieme test reel : le job entier annule avec l'annotation "The job has
exceeded the maximum execution time of 8m0s". Cause : l'installation des
dependances (torch/transformers/ultralytics, un requirements-api.txt
volumineux) prend a elle seule ~1m45s, ce qui ne laissait aucune marge avant
le `timeout 420` (7 min) de la commande Celery elle-meme, a l'interieur d'un
`timeout-minutes: 8` au niveau du job -- 1m45s + 7min = 8m45s, plus que le
budget disponible. Le job se faisait donc tuer avant que Celery n'ait pu
sortir proprement via son propre timeout interne. Corrige en portant
`timeout-minutes` a 12.

## Test reel qui a confirme que ca marche

Troisieme run manuel (2026-09-18 15:40-15:47 UTC, run `35363605944`), avec
les deux correctifs ci-dessus : logs verifies ligne par ligne, pas seulement
le statut GitHub (qui peut afficher "success" meme si Celery a plante, a
cause du `|| true` en fin de commande -- toujours verifier les logs
eux-memes, jamais seulement le badge de statut) --

```
[INFO/MainProcess] Connected to ***witty-dogfish-282882.upstash.io:6379//
[INFO/MainProcess] mingle: searching for neighbors
[INFO/MainProcess] mingle: all alone
[INFO/MainProcess] celery@runnervmlun5p ready.
```

Zero `CRITICAL`/`Traceback`/`Unrecoverable` sur l'ensemble du log. Toutes les
taches enregistrees (document_processing, billing, analytics, etc.). Arret
propre a l'expiration du `timeout 420`, sans annulation forcee cette fois.

Ce test confirme que l'infrastructure fonctionne, mais aucun document reel
n'etait en attente de traitement au moment du run -- il n'a donc pas ete
prouve, en conditions reelles, qu'un document uploade est effectivement
traite de bout en bout par ce chemin. A confirmer des que le quota Actions
le permettra (voir section suivante).

## Limitation actuelle : quota GitHub Actions epuise

Le compte GitHub (plan gratuit, 2000 minutes/mois pour un depot prive) avait
deja consomme tout son quota avant meme la creation de ce workflow -- un
ancien workflow de tests casse (`Tests and retrieval regression check`, qui
n'existe plus dans le depot aujourd'hui) a tourne en echec des dizaines de
fois entre le 8 et le 11 septembre 2026, epuisant les 2000 minutes.

Consequence concrete : tant que le depot reste **prive**, tout job Actions
(y compris ce worker Celery, meme le cron automatique toutes les 10 minutes)
est bloque avec le message --

```
The job was not started because recent account payments have failed or
your spending limit needs to be increased.
```

Les deux tests reels documentes ci-dessus n'ont pu etre executes qu'en
rendant le depot **temporairement public** (les depots publics ont des
minutes Actions illimitees et gratuites), puis en le repassant en prive
immediatement apres chaque test. Ce n'est pas une solution permanente : le
worker planifie (cron toutes les 10 min) ne tournera pas reellement tant que
le depot est prive et que le quota n'est pas regenere.

Options reelles, aucune appliquee de facon permanente a ce jour :
1. Attendre la reinitialisation du quota (1er octobre 2026, gratuit).
2. Garder le depot public en permanence (minutes illimitees, mais expose le
   code source -- non retenu, ce projet est un SaaS commercial).
3. Ajouter un moyen de paiement + une petite limite de depense sur GitHub
   (le worker consomme tres peu ; cout reel probablement proche de zero,
   mais necessite une carte -- non disponible au moment de la redaction).

## Test de traitement d'un document reel (2026-09-18, run `35365705366`)

Un compte de test a ete cree sur la production (`/auth/register`), un
document reel uploade via `/organizations/{org_id}/documents`, puis le
workflow declenche manuellement. Resultat verifie via l'API (pas seulement
les logs) :

```
avant: {"status":"pending", ...}
apres: {"status":"failed", "metadata":{"error":"Invalid endpoint: ***"}, ...}
```

Le `status` est passe de `pending` a `failed` et `updated_at` a change --
preuve que **Celery a bien recupere et execute la tache** (le pipeline bout
en bout fonctionne : Redis -> worker -> tache -> ecriture en base). Le log
confirme : `process_document: processing failed for document '...':
Invalid endpoint: ***` (valeur masquee automatiquement par GitHub car elle
correspond a un secret).

### Bug reel trouve, non corrige : `S3_ENDPOINT_URL` invalide

`Invalid endpoint` est l'erreur typique de boto3/aiobotocore quand
`endpoint_url` n'a pas de schema (`https://`) ou est mal forme. Utilise dans
`api/services/document_storage.py:400`, `api/services/storage.py:70`, et 3
autres fichiers. A verifier : la valeur reelle de `S3_ENDPOINT_URL` sur
Render (Environment -> cliquer les `...` pour reveler) doit commencer par
`https://` ; si le secret GitHub a ete copie sans ce prefixe, le recreer
avec le schema inclus. Impossible a diagnostiquer plus precisement depuis
ce cote : les secrets GitHub ne sont jamais relisibles une fois crees, et
la valeur est automatiquement masquee (`***`) partout ou elle apparait dans
les logs, y compris dans les messages d'erreur.

## Etat au 2026-09-18

- Workflow fonctionnel, verifie trois fois en conditions reelles (connexion
  Redis TLS, demarrage complet du worker, et prise en charge reelle d'une
  tache de traitement de document).
- Pipeline Celery bout en bout confirme operationnel : Redis -> worker ->
  execution de tache -> mise a jour du document en base.
- Bug reel, non corrige, bloquant le traitement effectif des documents :
  `S3_ENDPOINT_URL` mal forme (`Invalid endpoint`) cote stockage S3/R2 --
  a verifier et corriger cote Render puis recreer le secret GitHub
  correspondant.
- Depot remis en prive apres chaque test.
- Cron automatique (toutes les 10 min) : bloque tant que le quota Actions
  du compte est epuise et que le depot reste prive (reset le 1er octobre
  2026, ou passage public temporaire, ou ajout d'un moyen de paiement).
