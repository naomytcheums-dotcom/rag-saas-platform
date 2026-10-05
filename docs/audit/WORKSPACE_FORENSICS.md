# Workspace Forensics — Phase 1

Date : 2026-10-03. Inspection locale en lecture seule. Aucun fichier applicatif
n'a été modifié pendant cette phase forensics; les seuls nouveaux fichiers de
cette phase sont les cinq livrables de rapport.

## Répertoire et dépôt

- Workspace : `C:\Users\NITROV15\Downloads\rag-saas-platform`.
- HEAD : `2e7bfaa` (`2026-09-27`), branche `main`, configurée à égalité avec
  `origin/main` au point de départ de l'audit initial.
- Branche et commit inchangés dans cette phase; aucun commit, checkout,
  reset, stash, fetch/pull, push ou migration exécuté.
- État observé maintenant : **132 chemins suivis modifiés** et **145 chemins
  non suivis non ignorés** (`git status --porcelain`). Cela inclut les
  rapports et corrections consignés dans
  [CHANGE_LEDGER.md](./CHANGE_LEDGER.md). Au début de l'audit initial, avant
  les corrections autorisées, le dépôt contenait déjà 130 suivis modifiés
  et 140 non suivis; leurs auteurs/intention ne sont pas inférés.
- 1 883 chemins suivis au HEAD; 124 migrations Alembic suivies au HEAD et
  131 présentes localement.
- Plusieurs worktrees locaux d'agents sont enregistrés dans Git. Leur contenu
  n'a pas été inspecté ni modifié.

## Inventaire local observé

- Racine applicative : `api/`, `frontend/`, `sdks/`, `tests/`, `docs/`,
  `scripts/`, `observability/`, `locales/`, `nginx/`, ainsi que des
  répertoires `src/`, `dashboard/` et `tests_pipeline/`.
- Python : venvs `.venv` et `.venv-1`, caches et `.pytest_cache`.
- Frontend : `frontend/node_modules`, `.next`, fichiers de build/TypeScript.
- Fichiers locaux non suivis pertinents : `.env`, `frontend/.env.local`,
  `dump.rdb`, `snyk.exe`. Seuls leur existence et leur nom ont été observés;
  leur contenu n'a pas été lu. Git les ignore tous selon `git check-ignore`.
- Aucune clé, URL de connexion complète, valeur `.env`, donnée de dump ou
  credential n'est incluse dans ce rapport.

## Risque principal

Le worktree est déjà très chargé et comprend du code, tests et migrations
nouvellement ajoutés. Il ne constitue donc ni une baseline propre de `main`,
ni une preuve que l'état courant est commité/déployé. Ne pas faire de nettoyage
automatique, de checkout destructif, ni de commit groupant ce travail sans
inventaire/provenance préalable.

## Base de données : identification non sensible

La configuration est présente et utilise le driver `postgresql+asyncpg`;
le host est classé **Supabase/non-local géré**. Un endpoint transactionnel
optionnel est également configuré. Aucun URL, hostname complet, nom de base,
nom d'utilisateur ou secret n'a été affiché.

Cette classification n'identifie pas si la cible est dev, test, staging ou
production. En conséquence :

```
DATABASE_MUTATION = BLOCKED
DATABASE_CONNECTION_FOR_FORENSICS = BLOCKED
```

Aucune connexion DB n'a été tentée pour cette phase; aucun changement de données
ou de schéma n'a été effectué. L'échec antérieur de `alembic current` n'a fourni
aucune version réelle exploitable et ne permet pas de conclure à l'état DB.

## Actions sûres réalisées

- `git status`, historique/référence Git, `git ls-files`, `git check-ignore`,
  liste de worktrees : lecture seulement.
- Lecture locale de configuration Alembic et des modèles/migrations/tests.
- Analyse statique du graphe Alembic et recherche des opérations de migration;
  aucun `upgrade`, `downgrade` ni SQL n'a été exécuté.
- Lecture de configuration d'URL limitée à classifier le driver et la catégorie
  du host; aucune valeur confidentielle n'a été imprimée.
