# Rapport des limites — audit du 2026-09-16

Audit des limites déclarées ou codées en dur dans `api/` et `frontend/` : marqueurs
TODO/FIXME, constantes numériques sans surcharge de configuration, stubs
`NotImplementedError`, et écarts entre une limite documentée et la limite réellement
appliquée.

## 1. Marqueurs TODO/FIXME/XXX/HACK

**Aucun trouvé.** Recherche exhaustive dans `api/` et `frontend/` (hors `node_modules`,
`.git`, `api/alembic/versions` qui est un historique immuable) — zéro occurrence des deux
côtés.

## 2. Limites numériques codées en dur sans surcharge de configuration

### Corrigé dans cet audit — pagination non plafonnée

**Faille réelle trouvée** : plusieurs endpoints, y compris l'API publique externe
(`/v1/documents`, `/v1/agents`, `/v1/knowledge-bases`, `/v1/conversations`), acceptaient un
paramètre `limit` **sans aucune borne supérieure** (`limit: int = 20`, pas de `Query(...,
le=...)`). Un appelant pouvait demander `limit=999999999` et forcer une requête non bornée
— risque réel d'épuisement de ressources, plus critique encore sur l'API publique
partenaire que sur les endpoints internes.

**Corrigé** — 12 fichiers, 19 paramètres, passés à `Query(default=N, ge=1, le=200)`
(`le=100` pour l'API publique, plus restrictif car exposée à des tiers) :
`api/routers/public_api.py`, `api/routers/admin_organizations.py`,
`api/routers/admin_subscriptions.py`, `api/routers/admin_users_management.py`,
`api/routers/autonomous_agents.py`, `api/routers/billing.py`, `api/routers/compliance.py`,
`api/routers/documents.py`, `api/routers/fine_tuning.py`, `api/routers/media.py`,
`api/routers/notifications.py`, `api/routers/observability.py`, `api/routers/plugins.py`.
Vérifié : `tsc`/`py_compile` propres, import de `api.main` sans erreur, 264 tests
concernés tous verts après correction.

### Corrigé dans cet audit — duplication de constante

`api/routers/audit.py`, `api/routers/quality_dashboard.py`, `api/routers/usage.py`
redéfinissaient chacun indépendamment `_MAX_PAGE_SIZE = 200` — même valeur partout, mais
rien ne les reliait réellement ; un futur changement sur l'un aurait pu diverger
silencieusement des deux autres. **Corrigé** : constante unique `MAX_PAGE_SIZE` déplacée
dans `api/utils.py`, importée dans les 3 fichiers.

### Non corrigées — documentées comme limites restantes

Les limites suivantes existent, sont des constantes plausiblement raisonnables, mais
n'ont pas de justification écrite pour la valeur précise choisie (contrairement à
`MAX_LOGO_BYTES`/`MAX_LOGO_DIMENSION_PX` dans `api/services/storage.py`, qui ont un
commentaire explicite) :

| Fichier:ligne | Limite | Statut |
|---|---|---|
| `api/services/storage.py` | `MAX_AVATAR_BYTES = 5 MB` | Pas de justification pour 5 Mo vs les 2 Mo du logo |
| `api/security/plugin_manifest.py:22` | `MAX_PLUGIN_CODE_BYTES = 1 MB` | Pas de justification écrite |
| `api/services/airbyte_client.py:72,150` | timeouts HTTP 15s/90s | Codés en dur, pas de réglage par organisation/déploiement |
| `api/services/fine_tuning_providers.py` | timeouts 30s/60s (8 occurrences) | Codés en dur |
| `api/services/alerting.py:71`, `api/services/voice.py:182`, `api/routers/integrations_universal.py:51` | timeouts HTTP 10s/30s/3s | Codés en dur |
| `api/services/security_scan.py:70,98,178` | timeouts subprocess 300s/600s | Codés en dur (scans pip-audit/bandit/trivy) |
| `api/services/video_extraction.py:41,62,80` | timeouts 30s/300s | Codés en dur |
| `frontend/components/ConversationList.tsx:14` | `PAGE_SIZE = 20` | Pas relié au défaut backend correspondant |

**Décision** : ne pas toucher ces valeurs maintenant — ce sont des constantes de
comportement (timeouts réseau, tailles de fichier) sans preuve qu'elles causent un
problème réel aujourd'hui, contrairement à la pagination non bornée (qui était une vraie
surface d'attaque DoS). Les documenter ici suffit à les rendre visibles pour une décision
future ; les transformer en réglages `Settings` sans besoin concret ajouterait de la
complexité sans bénéfice mesurable, à l'inverse de la discipline "pas d'abstraction
prématurée" de ce projet.

## 3. Stubs `NotImplementedError` / no-ops

Les 3 occurrences de `NotImplementedError` trouvées sont des reports de travail
**délibérément documentés**, chacun derrière un indicateur de configuration explicite et
expliqué dans la docstring du module ET au point du `raise`, citant la contrainte "bloqué
sur crédit API" du cahier des charges :
- `api/services/claim_verification.py:106` (chemin `CLAIM_VERIFICATION_USE_LLM`)
- `api/services/context_relevance.py:72` (chemin `CONTEXT_RELEVANCE_USE_LLM`)
- `api/services/answer_quality_metrics.py:158` (chemin `ANSWER_RELEVANCE_USE_LLM`)

Tous les `pass` nus échantillonnés sont soit des corps de classes d'exception
(`class FooError(Exception): pass`), soit des no-ops délibérés avec justification en
commentaire inline (`api/tools/human_escalation.py:109`, `api/security/loki_handler.py:42`,
`api/services/agent_orchestrator.py:441`).

**Aucun stub oublié trouvé.**

## 4. Écarts entre limite documentée et limite appliquée

Vérifié sur plusieurs zones candidates (rate limiting d'authentification, timeouts sandbox
de plugins, retry/timeout LLM) — **aucun écart trouvé** : dans chaque cas vérifié, le
commentaire/docstring référence le même champ `settings.*` réellement utilisé au point
d'appel. Le texte frontend "jusqu'à 2 Mo" (`LogoUpload.tsx`) correspond exactement à
`MAX_LOGO_BYTES` backend.

**Non vérifié** : aucune validation côté client de la taille de fichier avant envoi
(`LogoUpload.tsx` affiche un texte statique "jusqu'à 2 Mo" sans vérifier `File.size` avant
l'upload) — un vrai dépassement échoue côté serveur, pas une faille, mais une occasion
manquée de feedback utilisateur immédiat.

## Bilan

1 faille réelle corrigée (pagination non plafonnée, 12 fichiers). 1 incohérence de
duplication corrigée (constante `MAX_PAGE_SIZE`). 8 catégories de limites documentées
mais volontairement non modifiées (constantes raisonnables sans preuve de problème réel).
Aucun TODO oublié, aucun stub non documenté.
