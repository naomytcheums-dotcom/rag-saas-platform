# Design des policies RLS par classe

Date : 2026-10-03. Design conceptuel; ces extraits ne sont pas des migrations
exécutables et aucune policy n'est créée ici.

## État observé dans le dépôt

- 177 tables ORM : 79 directes `organization_id`, 63 avec un chemin FK
  candidat vers une table tenant directe, 24 personnelles/user-scoped, trois
  catalogues globaux candidats, six system/control-plane candidats et deux
  encore `UNKNOWN`. Voir la [matrice complète](./TENANT_ISOLATION_MATRIX.md).
- Les révisions historiques activent RLS (notamment 0002, 0032, 0037, 0087,
  0110, puis 0131 pour onze tables récentes), mais les sources locales ne
  déclarent aucune policy; les tests du dépôt attendent zéro policy.
- La migration 0131 active RLS sans policies sur onze tables et la désactive
  en downgrade. L'isolation utile dépend donc du rôle et des filtres applicatifs.
- `tests/test_postgres_integration.py` affirme qu'aucune policy n'existe et
  que le rôle de cette configuration bypass RLS; ces tests décrivent un
  contrat historique, pas l'observation de la base actuellement configurée.

## Fonction contexte — contrat, pas encore SQL de production

Une fonction privée telle que `app_private.current_organization_id()` devrait
lire `current_setting('app.organization_id', true)`, convertir une valeur
valide en UUID et retourner `NULL` si elle manque. Éviter les casts qui font
échouer des requêtes de manière incohérente; valider la valeur au point où
l'identité tenant est authentifiée. La variable est installée transaction
localement avec des requêtes paramétrées.

Une policy directe suit ce contrat logique (les noms/helpers sont illustratifs) :

```sql
USING (organization_id = app_private.current_organization_id())
WITH CHECK (organization_id = app_private.current_organization_id())
```

Les policies seraient séparées par action là où les règles diffèrent. Un
simple `USING` ne contrôle pas la nouvelle valeur d'un `INSERT` ou d'un
`UPDATE`; `WITH CHECK` est obligatoire pour ces chemins.

## Correspondance classe → conception

| Classe | Application actuelle | Policy cible | Précondition |
|---|---|---|---|
| `DIRECT_TENANT` (79) | Vérifier org, membership et permission à chaque opération | `organization_id` égal au contexte pour `USING` + `WITH CHECK` | Confirmer nullable, effets d'admin, clés composites et actions worker |
| `INDIRECT_TENANT` (63) | Charger le parent et vérifier que ce parent relève du tenant attendu | `EXISTS` sur parent tenant, ou future clé tenant directe avec FK composée | Cartographier parent réel, cycles, cascades, parent modifiable, accès sans parent |
| `USER_SCOPED` (24) | Comparer l'utilisateur authentifié et le propriétaire/ACL | `user_id` = user de contexte; si partage tenant, vérifier aussi l'adhésion/ACL | Ne pas confondre compte utilisateur et isolation organisationnelle |
| `GLOBAL` (3 candidats) | Catalogue/configuration explicite | Lecture minimale selon besoin; écriture réservée | Confirmer qu'aucune ligne ne contient données ou paramètres tenant |
| `SYSTEM` (6 candidats) | Service interne et contrôle opérateur | Policies étroites par rôle/action; pas de lecture public générique | Classifier données sensibles, webhooks, secrets, et opérations plateforme |
| `UNKNOWN` (2) | Aucun accès de sécurité ne peut être présumé | Aucune policy avant revue manuelle | Identifier propriétaire, tenant, cycle de vie et chemins worker |

## Tables indirectes et associations

- Exprimer la règle sur le chemin de propriété complet, par exemple ligne →
  document/agent/conversation → organisation. Vérifier que chaque maillon est
  immuable ou que son changement est protégé par `WITH CHECK`.
- Pour une table d'association à deux parents tenant-scoped, exiger que **les
  deux parents** appartiennent au contexte, sauf contrat explicite de partage
  cross-tenant approuvé/audité. Les identifiants de deux parents ne suffisent
  pas à autoriser la ligne.
- FK circulaires, relations polymorphes, propriétaire dans JSON, modèles
  mémoire/cache et objets supprimés nécessitent une règle dédiée; ne pas
  inférer automatiquement la policy depuis la première FK du graphe.
- Les tables temporaires/queue peuvent contenir une organisation via le
  payload plutôt qu'une FK. Le worker doit vérifier le payload contre l'objet
  chargé; si le payload est la seule source, le modèle est `UNKNOWN` jusqu'à
  migration vers un champ/parent vérifiable.

## Rôle, grants et bypass

- Le rôle d'exécution ne doit être ni propriétaire des tables ni doté de
  `BYPASSRLS`; vérifier ces propriétés par SQL catalogues staging.
- `FORCE ROW LEVEL SECURITY` est une seconde mesure pour les propriétaires,
  pas une solution contre `BYPASSRLS`.
- Garder DDL/migrations et opérations d'urgence hors des rôles runtime.
  Toute exception plateforme est explicitement nommée, limitée et auditée.
- Révoquer les grants inutiles aux rôles Supabase exposés; le mode « aucune
  policy » protège par défaut un rôle non-bypass, mais bloque aussi ses
  opérations métier légitimes.

## Tests PostgreSQL obligatoires avant activation

1. Créer deux tenants A/B, leurs utilisateurs et ressources parent/enfant.
2. Avec le rôle runtime, prouver que contexte A lit/écrit A et ne voit pas B;
   tester chaque table tenant directe et indirecte.
3. Sans contexte et avec un contexte invalide, prouver zéro lecture et zéro
   insertion/modification tenant.
4. Tester un `UPDATE` qui tente de déplacer un objet A vers B; il doit échouer.
5. Tester associations à parents de tenants différents, objets supprimés,
   accès user-scoped, opérations worker, streaming et API key.
6. Vérifier qu'un rollback/commit et une connexion réutilisée ne conservent pas
   le contexte du tenant précédent.
7. Tester le rôle de migration, PostgREST `anon`/`authenticated`, les accès
   plateforme audités et les plans de restauration.

Le suite SQLite ne valide ni les policies PostgreSQL, ni `BYPASSRLS`, ni
`FORCE RLS`, ni l'isolation de PgBouncer.
