# Pools de connexions base de donnees

## Probleme trouve (audit, 2026-09-19)

18 fichiers `api/tasks/*.py` creaient chacun leur PROPRE moteur
SQLAlchemy synchrone (`create_engine(...)`), sans borne de pool
explicite -- le defaut SQLAlchemy est `pool_size=5, max_overflow=10`,
soit jusqu'a 15 connexions par moteur. Avec 18 moteurs, le pire cas
reel etait 18 x 15 = 270 connexions possibles, contre un pooler
Supabase en mode session plafonne a **15 connexions au total**, tous
processus confondus (y compris le moteur async principal de l'API web).

Reduire individuellement chaque pool (`pool_size=3` sur chacun des 18)
aurait laisse le meme probleme de fond : 18 pools separes se disputant
le meme budget, juste avec un plafond theorique plus bas (18 x 5 = 90,
toujours largement au-dessus de 15).

## Correction

Un seul moteur partage, `api/tasks/_sync_engine.py` :

```python
sync_engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", ""),
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
)
```

Les 18 fichiers de `api/tasks/` importent desormais
`from api.tasks._sync_engine import sync_engine as _sync_engine` au lieu
d'appeler `create_engine` eux-memes. Un seul pool reel, borne a 5
connexions maximum (3 + 2 overflow), partage par toute tache Celery
quel que soit son module.

Ce budget de 5 est coherent avec le worker Celery de production
actuel (`--pool=solo --concurrency=1`, voir
`docs/deployment/GITHUB_ACTIONS.md`) -- une seule tache s'execute a la
fois en pratique -- tout en laissant une vraie marge si la concurrence
augmente plus tard, sans reintroduire silencieusement le meme risque.

## Verification

- `python -m py_compile` sur les 18 fichiers modifies + le nouveau
  module partage : succes.
- Tests reels executes apres la modification (pas seulement une
  compilation) : `tests/test_ab_tests.py`, `tests/test_billing.py`
  (26 tests, tous passants), plus les suites des autres modules
  touches (`test_compliance.py`, `test_integrations.py`,
  `test_jwt_key_rotation_integration.py`, `test_plugins.py`,
  `test_sales_models.py`, `test_security_scan.py`, `test_webhooks.py`,
  `test_audit_log.py`).
- Plus aucun `create_engine(` en dehors de `api/tasks/_sync_engine.py`
  dans tout `api/tasks/` (`grep` de confirmation).
