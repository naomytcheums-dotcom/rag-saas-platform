# RLS Forensics — Phase 1

Date : 2026-10-03. Inspection statique uniquement; aucune stratégie RLS n'a
été modifiée et aucune requête à la base distante n'a été exécutée.

## Ce que déclarent le dépôt et les tests

- Les migrations 0002 et suivantes activent RLS à plusieurs endroits; les
  protections manquantes trouvées dans des migrations historiques sont
  ajoutées par des migrations ultérieures (p.ex. 0037, 0087, 0098, 0110,
  0131). Ne pas modifier les migrations historiques déjà existantes.
- La migration locale 0131 active RLS sur 11 tables (long-term agent memory,
  evaluation failures, flight recordings, MCP config/cache, notifications,
  preferences, RAG experiments, retrieval diagnostics, sandbox, workflow
  node executions). Son downgrade désactive RLS.
- Recherche textuelle dans `api/alembic/versions`, `api/models` et `tests` :
  aucune commande `CREATE POLICY`, `create_policy` ou `FORCE ROW LEVEL
  SECURITY` trouvée.
- `tests/test_postgres_integration.py` affirme qu'une intégration PostgreSQL
  accessible devrait avoir zéro policy sur `public` et un rôle applicatif
  `BYPASSRLS=True`. Ces tests n'ont pas été lancés à cette phase; il s'agit du
  contrat/assertion du test, pas d'une mesure actuelle de la DB configurée.
- Les migrations décrivent explicitement un modèle de défense en profondeur :
  RLS activé, sans policy, rôle applicatif privilégié/bypass, isolation assurée
  par l'application. L'absence de policy est donc attendue dans le code actuel,
  mais ne constitue pas une isolation DB effective pour le rôle bypass.

## Inventaire partiel des tenants

Les métadonnées SQLAlchemy déclarent 177 tables; 79 ont une colonne directe
`organization_id`. Les 98 tables sans cette colonne directe nécessitent une
classification par relations (user-owned, globales, liées à agent/document/
conversation, tenant via FK, etc.) avant d'affirmer qu'elles sont ou non
tenant-scoped. Aucun tableau table-par-table `ENABLE/FORCE/policy/role` pour
une DB réelle n'a été produit dans cette phase.

## Conclusion et risques

- **RLS application effective : `UNVERIFIED`.** La base est distante et son
  environnement n'a pas été identifié; le rôle réel et les flags de catalogues
  ne sont pas connus.
- **RLS comme isolation de tenant : non démontrée.** La conception du dépôt
  s'appuie sur RBAC/filtres applicatifs; les tests cités eux-mêmes disent que
  le rôle de l'application bypass RLS.
- Risque structurel : un nouveau chemin SQL/requête sans filtre tenant ne
  serait pas bloqué par une policy DB actuellement déclarée.
- Il n'est pas justifié d'ajouter ici une policy ni `FORCE RLS` : cela
  changerait l'accès de l'API/workers, nécessite une stratégie de rôles,
  compatibilité migrations, tests A/B cross-tenant et revue DB contrôlée.

## Blocage

```
DATABASE_MUTATION = BLOCKED
RLS_POLICY_CHANGE = NOT_STARTED
LIVE_RLS_CATALOG_VALIDATION = BLOCKED
```

La prochaine étape, si elle est autorisée, est une inspection read-only en
staging explicitement identifié : catalogues `pg_class`, `pg_policies`,
`pg_roles`, grants et test de visibilité avec deux organisations et rôles
distincts. Aucun `ALTER TABLE`, `CREATE POLICY` ni `SET ROLE` sur une cible
inconnue.

