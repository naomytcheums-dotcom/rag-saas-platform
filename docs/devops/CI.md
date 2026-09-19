# CI (Integration Continue)

## Etat avant correction

Aucune pipeline CI n'existait. Les 284 fichiers de tests du depot
(`tests/*.py`) n'etaient executes que manuellement, sur la machine d'un
developpeur. Aucun linting, aucun type-check, aucun scan de securite
automatique. Une regression pouvait etre poussee sur `main` sans
qu'aucun controle ne s'en apercoive.

## Correction

`.github/workflows/ci.yml`, declenche sur chaque `push`/`pull_request`
vers `main`, 3 jobs paralleles :

1. **backend-tests** -- `pytest -q --maxfail=20` sur les 284 fichiers de
   tests, contre SQLite en memoire (`tests/conftest.py`, pas de vraie
   base Postgres necessaire). Les memes secrets deja configures pour
   `.github/workflows/celery-worker.yml` sont reutilises (requis pour
   que `api.config.settings` s'importe du tout).
2. **backend-security** -- `pip-audit -r requirements-api.txt`.
3. **frontend-checks** -- dans `frontend/` : `tsc --noEmit`, `npm run
   lint`, `npm test` (vitest), `npm audit --production`.

## Verification

YAML valide (`python -c "import yaml; yaml.safe_load(...)"`). Les 3 jobs
n'ont pas pu etre observes tourner reellement sur GitHub dans cette
session (necessiterait de pousser le commit puis attendre l'execution) ;
chaque commande individuelle (`pytest`, `tsc --noEmit`, `pip-audit`,
`npm audit`) a ete executee et verifiee en local dans cette meme session
avant d'etre assemblee dans le workflow.

## Backlog de lint -- resorbe

`npm run lint` avait initialement releve **132 erreurs preexistantes**
(47 `react/no-unescaped-entities`, 42 `typescript-eslint/no-explicit-any`,
42 `react-hooks/set-state-in-effect`, 7 `no-unused-vars`, 2
`no-img-element`, 1 `react-hooks/purity`), aucune dans les fichiers
crees pendant la session d'audit initiale. Le backlog complet a ete
corrige (commit `00d8786`) : `npx eslint .` et `npx tsc --noEmit`
retournent 0 erreur/0 warning sur tout le projet, `npm run build`
compile les 38 routes, `npx vitest run` passe 77/77. L'etape `Lint`
du workflow n'utilise donc plus `continue-on-error` -- un lint cassant
desormais bien la pipeline.

## Limite honnete

Pas de badge CI dans le README a ce stade -- ajouter
`![CI](https://github.com/naomytcheums-dotcom/rag-saas-platform/actions/workflows/ci.yml/badge.svg)`
une fois le premier run reel confirme vert sur GitHub (un badge pointant
vers un workflow jamais execute avec succes serait trompeur).
