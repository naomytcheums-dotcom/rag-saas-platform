# Bugs trouvés et corrigés — campagne de tests par personas IA

Chaque entrée : ce qui a été observé, comment ça a été confirmé (pas seulement supposé),
la cause réelle, et la correction appliquée et vérifiée.

---

## 1. [UX] Interface encore partiellement en anglais alors que l'app est francophone

**Trouvé par** : persona First-Timer (Crawlix), confirmé manuellement.

**Constat** : les pages `/login`, `/register`, `/forgot-password` et
`/dashboard/documents` contenaient des libellés, placeholders et messages d'erreur en
anglais, incohérents avec le reste de l'application déjà en français — source de confusion
réelle pour un nouvel utilisateur francophone (persona First-Timer/non-native-speaker).

**Correction** : traduction complète de ces 4 pages (titres, sous-titres, labels de champs,
placeholders, texte des boutons et états de chargement, liens, messages d'erreur).
- [frontend/app/login/page.tsx](../../frontend/app/login/page.tsx)
- [frontend/app/register/page.tsx](../../frontend/app/register/page.tsx)
- [frontend/app/forgot-password/page.tsx](../../frontend/app/forgot-password/page.tsx)
- [frontend/app/dashboard/documents/page.tsx](../../frontend/app/dashboard/documents/page.tsx)

**Statut** : corrigé, vérifié visuellement dans le navigateur.

---

## 2. [Accessibilité / QA] Case "Se souvenir de moi" sans nom accessible

**Trouvé par** : inspection de l'arbre d'accessibilité pendant la correction du bug n°1.

**Constat** : la case à cocher était enveloppée implicitement dans son `<label>`
(`<label>texte<input/></label>`), une association que l'arbre d'accessibilité ne résolvait
pas correctement dans ce cas précis — la case apparaissait comme `checkbox "on"` au lieu de
`checkbox "Se souvenir de moi"`. Un lecteur d'écran n'aurait annoncé aucune information utile.

**Correction** : association explicite `id`/`htmlFor` entre le `<label>` et l'`<input>`
dans [frontend/app/login/page.tsx](../../frontend/app/login/page.tsx). Vérifié : la case
expose désormais `checkbox "Se souvenir de moi"`.

**Statut** : corrigé, vérifié.

---

## 3. [Technique — critique] Inscription très lente (jusqu'à 59 secondes)

**Trouvé par** : persona First-Timer restait bloquée sur l'écran d'inscription sans
progresser ; investigation manuelle via `curl` chronométré a confirmé un temps de réponse
réel de 22 à 59 secondes sur `POST /auth/register`, deux causes réelles cumulées :

### 3a. Appels d'envoi d'email bloquants dans le code async

`api/services/email.py` utilise `httpx.post()` (synchrone) pour envoyer un email. Appelé
depuis une route `async def` sans l'entourer d'un thread, cet appel bloque **toute la boucle
d'événements** du worker Uvicorn — c'est-à-dire que pendant l'envoi de l'email, **aucune
autre requête concurrente sur tout le serveur** n'est traitée, pas seulement celle en cours.

Recherché systématiquement sur tout le projet (pas seulement le point d'entrée
inscription) : **31 appels** de ce type répartis dans **16 fichiers**. Tous corrigés en les
enveloppant dans `await asyncio.to_thread(...)` :
`api/services/verification.py`, `api/services/security_alerts.py`,
`api/security/sessions.py`, `api/routers/auth.py`, `api/dependencies.py`,
`api/routers/account.py`, `api/routers/enterprise_sso.py`, `api/routers/invitations.py`,
`api/routers/organization_members.py`, `api/routers/two_factor.py`,
`api/routers/webauthn.py`, `api/services/account_restore.py`, `api/services/alerting.py`,
`api/services/billing_invoices.py`, `api/services/consent_reactivation.py`,
`api/services/password_reset.py`, `api/services/two_factor_lockout_recovery.py`.

### 3b. Aucun timeout explicite sur les connexions Redis

`redis.asyncio.from_url()` sans `socket_connect_timeout`/`socket_timeout` explicite retombe
sur le timeout TCP par défaut du système (plusieurs secondes), payé **à chaque** connexion
Redis ratée — et une seule requête d'inscription touche Redis plusieurs fois (rate limiting
+ géolocalisation). Corrigé en ajoutant `socket_connect_timeout=3.0, socket_timeout=1.0` sur
les 4 clients Redis du projet :
[api/security/rate_limit.py](../../api/security/rate_limit.py),
[api/security/geoip.py](../../api/security/geoip.py),
[api/security/documents.py](../../api/security/documents.py),
[api/security/webauthn.py](../../api/security/webauthn.py).

**Résultat mesuré** : voir [RESULTS.md](RESULTS.md) — 49,5 s → 18,7 s (-62 %). Le reste du
temps est expliqué et n'est pas un bug de code (voir RESULTS.md).

**Statut** : corrigé, vérifié en conditions réelles (curl chronométré, avant/après).

---

## 4. [Infrastructure] Redis absent en environnement de développement local

**Constat** : cette machine ne peut lancer ni Docker Desktop ni WSL2 (les deux échouent avec
des erreurs de virtualisation imbriquée, confirmé directement, pas supposé), rendant
impossible de démarrer le vrai conteneur Redis du projet pour tester le rate limiting et le
géo-lookup en conditions réelles.

**Solution appliquée (pour cette machine, pas la production)** : `fakeredis.TcpFakeServer`
comme substitut TCP réel (voir [PERSONAS_TESTING.md](PERSONAS_TESTING.md) pour le détail).
Clairement documenté comme un contournement de sandbox, pas une recommandation pour un
déploiement réel.

**Statut** : contourné pour permettre les tests ; sans impact sur le code de production
(`docker-compose.selfhosted.yml` reste la référence pour un vrai déploiement).

---

## 5. [Technique — critique] Schéma de base de données réel désynchronisé du code (5 migrations manquantes)

**Trouvé par** : en relançant la suite de tests de régression complète après les
corrections ci-dessus, plusieurs tests d'intégration du pipeline de documents échouaient
avec une vraie erreur Postgres : `column "media_asset_id" of relation "document_chunks"
does not exist`.

**Cause réelle** : la base Postgres réelle (Supabase) utilisée par cet environnement de
développement était restée à la migration Alembic `0103`, alors que le code du dépôt
contient des migrations jusqu'à `0108` — les migrations `0104` (média multimodal),
`0105` (recherche visuelle CLIP), `0106` (agents autonomes), `0107` (suivi des coûts des
agents autonomes) et `0108` (fine-tuning) n'avaient jamais été appliquées à cette base.
Ce n'est pas un bug de code : c'est une base réelle restée en retard sur des fonctionnalités
déjà livrées dans le code.

**Correction** : `python -m alembic upgrade head` — les 5 migrations en attente ont été
appliquées avec succès (vérifié : `alembic current` reporte désormais `0108 (head)`).

**Statut** : corrigé, vérifié — la suite de tests concernée (`test_documents_integration.py`,
29 tests) passe intégralement après la migration (26 réussis, 3 ignorés
intentionnellement, 0 échec).

---

## 6. [Technique — critique, intermittent] "Event loop is closed" dans la suite de tests combinée

**Trouvé par** : suite de régression complète (CircleCI, lot 4/4) — le test
`test_geo_adaptive_rate_limit_integration.py::test_spoofing_x_forwarded_for_does_not_grant_the_trusted_ip_bypass`
échouait de façon intermittente uniquement quand il tournait dans le même processus pytest
que d'autres fichiers de test, jamais isolément.

**Cause réelle** : les 4 clients Redis du projet (`api/security/rate_limit.py`,
`api/security/geoip.py`, `api/security/documents.py`, `api/security/webauthn.py`) étaient
créés **une seule fois, au chargement du module**. Or la connexion réelle d'un client
`redis.asyncio` se lie à la boucle d'événements (event loop) **active au moment de sa
première utilisation**, pas à celle active au moment de sa création. Cette hypothèse tient
tant qu'il n'existe qu'une seule boucle d'événements pour toute la durée de vie du
processus — vrai en production (un seul worker Uvicorn), **faux dans la suite de tests** :
plusieurs modules de test déclenchent les tâches Celery réelles du projet
(`api/tasks/*.py`) via `asyncio.run()`, qui crée et referme sa **propre** boucle
d'événements à chaque appel. Si la connexion Redis s'établissait pendant qu'une de ces
boucles temporaires était active, elle restait liée à cette boucle — et dès que
`asyncio.run()` la refermait, **tout appel Redis suivant depuis la vraie boucle de session
pytest** levait "Event loop is closed", dans n'importe quel test qui touchait ensuite ce
même client, sans lien apparent avec la cause réelle.

**Correction réelle (pas un simple contournement du symptôme)** : chacun des 4 clients
Redis est désormais recréé automatiquement dès que la boucle d'événements active a changé
depuis sa dernière utilisation, via une fonction d'accès (`_get_redis()` /
`_get_progress_redis()`) qui compare la boucle courante (`asyncio.get_running_loop()`) à
celle enregistrée lors de la dernière connexion :
[api/security/rate_limit.py](../../api/security/rate_limit.py),
[api/security/geoip.py](../../api/security/geoip.py),
[api/security/documents.py](../../api/security/documents.py),
[api/security/webauthn.py](../../api/security/webauthn.py). Le comportement en production
est strictement identique (une seule boucle, donc jamais de recréation) ; seul le
comportement sous plusieurs boucles change, et c'est précisément le cas qui était cassé.

**Vérification** : relance complète du lot 4/4 (58 fichiers de tests, incluant les 5
fichiers qui utilisent `asyncio.run()` : `test_ssl_certificate_renewal_integration.py`,
`test_domain_verification_integration.py`, `test_sitemap_integration.py`,
`test_github_integration.py`, `test_enterprise_sso_integration.py`) — **858 réussis, 9
ignorés, 0 échec**, y compris le test précédemment intermittent. Voir
[RESULTS.md](RESULTS.md) pour le détail complet.

**Statut** : corrigé et vérifié dans le contexte exact qui le faisait échouer, pas
seulement en isolation.

**Effet de bord découvert et corrigé** : ce changement a cassé 4 tests existants de
[tests/test_document_progress.py](../../tests/test_document_progress.py) qui patchaient
directement l'ancien attribut statique `_progress_redis` — corrigé en les adaptant pour
patcher la nouvelle fonction d'accès `_get_progress_redis`. Vérifié isolément (9/9) puis
dans la suite complète (0 échec, voir [RESULTS.md](RESULTS.md)).
