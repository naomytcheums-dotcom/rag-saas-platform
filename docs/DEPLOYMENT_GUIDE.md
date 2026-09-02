# Guide de déploiement sécurisé -- api/ (audit Categorie 5, item 33)

Ce guide couvre le déploiement de `api/` (le backend d'authentification,
Partie 1.1) en production. Il complète `docs/AUTH_BACKEND_SETUP.md`
(configuration locale, architecture, exemples d'API) -- ce document-ci
se concentre sur ce qui change entre "ça marche sur ma machine" et "c'est
sûr d'exposer ça sur Internet".

## 1. Prérequis d'infrastructure

| Service | Rôle | Notes |
|---|---|---|
| **PostgreSQL** | Base de données principale | Supabase, RDS, ou tout Postgres géré. `DATABASE_URL` doit utiliser le driver asyncpg (`postgresql+asyncpg://...`). |
| **Redis** | Rate limiting, cache géo-IP, challenges WebAuthn, broker/backend Celery | Un seul serveur Redis suffit (bases logiques séparées par numéro, voir `.env.example`) ou plusieurs instances managées si vous préférez isoler chaque usage. |
| **Stockage S3-compatible** | Avatars utilisateur | AWS S3, Cloudflare R2, ou Supabase Storage. |
| **Resend** (ou un autre expéditeur transactionnel) | Emails (vérification, reset, alertes) | Domaine expéditeur vérifié -- indispensable, voir §4. |
| **Worker + Beat Celery** | Purge de comptes, purge de tokens, rotation automatique des clés JWT | Processus séparés du serveur API, voir §6. |
| **Reverse proxy** (nginx, Caddy, ou le load balancer du fournisseur cloud) | TLS/HTTPS, en-tête `X-Forwarded-For` fiable | Voir §3 -- **obligatoire**, pas optionnel. |

## 2. Variables d'environnement

Ne jamais committer de vraies valeurs -- `.env.example` documente
chaque variable avec son rôle. Checklist de ce qui **doit** être défini
(au-delà des valeurs par défaut) avant un déploiement réel :

- [ ] `DATABASE_URL` -- pointant vers la base de production, jamais celle de dev/CI.
- [ ] `JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `AUDIT_LOG_HMAC_SECRET_KEY` -- trois secrets **distincts**, générés avec `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Ne jamais réutiliser une valeur de dev.
- [ ] `COOKIE_SECURE=True` -- **obligatoire dès que le site est servi en HTTPS** (ce qui doit toujours être le cas en production). `False` désactive le flag `Secure` des cookies de session, acceptable seulement en dev HTTP local.
- [ ] `SUPPORT_EMAIL`, `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS` -- une adresse `EMAIL_FROM_ADDRESS` sur un domaine réellement vérifié dans Resend, sinon les emails partent en sandbox ou échouent silencieusement.
- [ ] `FRONTEND_URL`, `OAUTH_REDIRECT_BASE_URL` -- les vraies URLs publiques, pas `localhost`.
- [ ] `RATE_LIMIT_ENABLED=True` -- **ne jamais** mettre `False` en production (voir le rappel dans `api/security/rate_limit.py`).
- [ ] `TRUSTED_IPS`, `TRUSTED_COUNTRIES`/`SUSPICIOUS_COUNTRIES` (optionnels, audit Categorie 4) -- à revoir avec l'équipe sécurité si utilisés, ce ne sont pas des valeurs par défaut à copier sans réflexion.
- [ ] `SECRET_ENCRYPTION_KEY` -- requis dès que la rotation JWT automatique (`JWT_AUTO_ROTATION_INTERVAL_DAYS > 0`) ou une connexion SSO entreprise est utilisée. Généré une fois, jamais régénéré sans ré-chiffrer les lignes existantes.
- [ ] `WEBAUTHN_RP_ID` / `WEBAUTHN_RP_ORIGIN` -- le vrai domaine et la vraie origine du frontend, pas `localhost`. Un WebAuthn enregistré sous le mauvais `RP_ID` ne fonctionnera tout simplement pas -- à définir correctement **avant** que des utilisateurs enregistrent leurs clés.
- [ ] Toutes les variables `S3_*`, OAuth (`GOOGLE_OAUTH_*`/`GITHUB_OAUTH_*`), Celery (`CELERY_*`) -- pointant vers les vraies ressources de production.

## 3. Reverse proxy, HTTPS, et le piège `X-Forwarded-For`

**C'est le point le plus facile à mal configurer silencieusement.**

`api/utils.py`'s `client_ip()` fait confiance à l'en-tête
`X-Forwarded-For` tel quel -- c'est correct et nécessaire quand
l'application tourne derrière un vrai reverse proxy qui **définit ou
écrase** cet en-tête lui-même, mais si l'API est exposée directement sur
Internet sans un tel proxy devant elle, **n'importe quel client peut
fixer une valeur arbitraire de `X-Forwarded-For` et contourner
trivialement** :
- le rate limiting par IP (`/auth/login`, `/auth/register`, etc.),
- l'ajustement géo-adaptatif des limites (audit Categorie 4, item 29),
- et surtout **la liste `TRUSTED_IPS`** (item 30) -- c'est pour cette
  raison précise que l'exemption d'IP de confiance est vérifiée contre
  l'adresse TCP réelle (`api/security/trusted_ips.py`'s `direct_peer_ip`),
  jamais contre `client_ip()` -- mais cette protection ne couvre que
  CETTE fonctionnalité, pas le rate limiting ordinaire par IP ailleurs
  dans le code, qui dépend bien de la configuration correcte du proxy
  décrite ici.

**Ce qu'il faut vérifier avant d'aller en production :**

1. L'API ne doit **jamais** être directement joignable depuis Internet --
   seul le reverse proxy doit avoir une route réseau vers le port de
   l'API (firewall/security group, réseau privé du cloud).
2. Le reverse proxy doit **écraser** (pas seulement ajouter) tout
   `X-Forwarded-For` envoyé par le client, et le remplacer par la vraie
   adresse IP source qu'il observe :

   ```nginx
   # nginx -- exemple minimal
   server {
       listen 443 ssl http2;
       server_name api.votredomaine.com;

       ssl_certificate     /etc/letsencrypt/live/api.votredomaine.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/api.votredomaine.com/privkey.pem;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           # Écrase toute valeur envoyée par le client -- ne PAS utiliser
           # $proxy_add_x_forwarded_for ici, qui CONCATÈNE au lieu
           # d'écraser et laisserait passer une valeur falsifiée en
           # première position.
           proxy_set_header X-Forwarded-For $remote_addr;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. Si vous utilisez un load balancer managé (AWS ALB, Cloudflare, Fly.io,
   Render) -- vérifiez sa documentation : la plupart réécrivent déjà
   correctement `X-Forwarded-For`, mais ce n'est **pas universel**, et
   certains l'ajoutent en fin de liste plutôt qu'en le remplaçant (auquel
   cas `client_ip()`'s choix du **premier** élément serait le mauvais --
   revoir cette fonction si votre fournisseur a ce comportement).
4. `COOKIE_SECURE=True` et servir uniquement en HTTPS (redirection
   automatique HTTP -> HTTPS au niveau du proxy) -- sans quoi les cookies
   de session/CSRF ne sont jamais réellement protégés en transit.

## 4. Email transactionnel

- Domaine vérifié dans Resend (SPF/DKIM configurés) -- sans ça, Resend
  limite l'envoi à l'adresse du compte propriétaire uniquement (visible
  dans les tests locaux : `"You can only send testing emails to your own
  email address"`).
- `SUPPORT_EMAIL` doit être une boîte réellement surveillée -- elle est
  ajoutée en pied de page de chaque email (obligation RGPD Art. 12).

## 5. Base de données

- Exécuter les migrations Alembic avant le premier déploiement et à
  chaque mise à jour : `python -m alembic upgrade head`.
- Sauvegardes automatiques activées (géré par le fournisseur managé dans
  la plupart des cas -- Supabase/RDS le font par défaut, à vérifier).
- `AUDIT_LOG_HMAC_SECRET_KEY` et `SECRET_ENCRYPTION_KEY` : perdre l'un ou
  l'autre après coup casse respectivement la vérification d'intégrité des
  logs d'audit existants et le déchiffrement des secrets déjà stockés
  (clés JWT, secrets SSO) -- à sauvegarder dans un vrai gestionnaire de
  secrets (Vault, AWS Secrets Manager, etc.), jamais uniquement dans le
  `.env` d'une seule machine.

## 6. Processus applicatifs

**API (multi-worker, recommandé en production) :**

```bash
PROMETHEUS_MULTIPROC_DIR=/var/run/prometheus_multiproc \
WEB_CONCURRENCY=4 \
gunicorn -c gunicorn.conf.py api.main:app
```

Voir `gunicorn.conf.py` -- `PROMETHEUS_MULTIPROC_DIR` doit être un
répertoire partagé par tous les workers, vidé au démarrage (déjà géré par
`on_starting`). Un seul worker (`WEB_CONCURRENCY=1` ou `uvicorn` seul)
fonctionne aussi mais ne tire parti que d'un seul cœur CPU.

**Worker et Beat Celery** (obligatoires -- sans eux, la purge de comptes
différée, le nettoyage des tokens révoqués expirés, et la rotation
automatique de la clé JWT ne s'exécutent jamais) :

```bash
celery -A api.tasks.celery_app worker --loglevel=info
celery -A api.tasks.celery_app beat --loglevel=info
```

À faire tourner comme des services supervisés (systemd, Docker avec
`restart: always`, ou l'équivalent de votre PaaS) -- un crash silencieux
du worker ou de beat signifie que les tâches planifiées (purge RGPD,
rotation JWT) s'arrêtent sans avertissement visible autrement que
`GET /admin/jwt-keys` ne montrant plus de nouvelle rotation.

## 7. Checklist de sécurité pré-déploiement

- [ ] `COOKIE_SECURE=True` et HTTPS forcé de bout en bout.
- [ ] Reverse proxy en place, `X-Forwarded-For` écrasé (jamais concaténé) -- voir §3.
- [ ] `RATE_LIMIT_ENABLED=True`, Redis réellement accessible (vérifier `GET /health/ready`).
- [ ] Tous les secrets (`JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `AUDIT_LOG_HMAC_SECRET_KEY`, `SECRET_ENCRYPTION_KEY`) générés spécifiquement pour la production, jamais copiés depuis `.env` de dev/CI.
- [ ] Domaine Resend vérifié, `SUPPORT_EMAIL` surveillé.
- [ ] Migrations Alembic à jour (`alembic upgrade head` exécuté).
- [ ] Worker et Beat Celery tournent comme services supervisés (redémarrage automatique).
- [ ] `WEBAUTHN_RP_ID`/`WEBAUTHN_RP_ORIGIN` pointent sur le vrai domaine avant toute inscription WebAuthn réelle (changer après coup invalide les clés déjà enregistrées).
- [ ] Si SSO entreprise ou rotation JWT automatique sont utilisées : `SECRET_ENCRYPTION_KEY` sauvegardée dans un vrai gestionnaire de secrets, pas seulement dans le `.env` d'un serveur.
- [ ] `TRUSTED_IPS` (si utilisé) contient uniquement des IP/plages réellement de confiance -- une entrée trop large annule le rate limiting pour cette plage entière.
- [ ] `GET /health/ready` vérifié en conditions réelles (retourne `"database": "ok"` et `"rate_limit_redis": "ok"`) avant de considérer le déploiement terminé.
- [ ] Scan Snyk/OWASP ZAP de la CI (`.github/workflows/regression.yml`) vert sur le dernier commit déployé.
