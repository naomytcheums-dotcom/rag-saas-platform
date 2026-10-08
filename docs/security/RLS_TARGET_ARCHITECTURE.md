# Architecture cible RLS et isolation tenant

Date : 2026-10-03. Proposition statique seulement; aucune connexion, policy ou
migration DB n'a été appliquée.

## Décision d'architecture

Converger vers une défense en profondeur **application + PostgreSQL RLS**, avec
des identités DB séparées. Les filtres/RBAC applicatifs restent obligatoires;
RLS devient une seconde barrière pour que l'oubli d'un filtre, un nouveau
chemin SQL ou une exposition par API DB ne donne pas accès aux autres tenants.

Ne pas déployer une policy sur la cible actuelle : son environnement reste
inconnu et le code/documentation de test indique que le rôle applicatif actuel
peut contourner RLS.

## Rôles et frontières

1. **Rôle API tenant** : rôle SQL runtime non propriétaire des tables, sans
   `BYPASSRLS`, avec les seuls grants nécessaires. L'identité API publique
   dérive son tenant d'une clé vérifiée; l'API utilisateur dérive le tenant
   d'une adhésion vérifiée.
2. **Rôle worker** : rôle distinct, sans `BYPASSRLS`. Chaque tâche fournit un
   `organization_id` de confiance provenant d'un job signé/persisté; le worker
   vérifie que les ressources chargées appartiennent à ce tenant avant le
   traitement.
3. **Rôle migrations/provisionnement** : accès DDL séparé des processus web et
   Celery; aucun secret de ce rôle dans les services en ligne.
4. **Opérations plateforme** : accès cross-tenant exceptionnel isolé, limité,
   audité et non disponible aux requêtes tenant normales. Ne pas transformer
   les routes admin en un bypass général silencieux.
5. **Supabase/API REST** : grants et rôles `anon`/`authenticated` doivent être
   audités séparément. RLS ne remplace pas la révocation des grants publics;
   les clés privilégiées Supabase ne doivent jamais être exposées côté client.

## Propagation transactionnelle du tenant

- Après authentification et vérification de l'appartenance, établir le
  contexte du tenant **dans la transaction SQL courante** avec un paramètre
  bindé et l'équivalent de `set_config('app.organization_id', ..., true)`.
  Le troisième argument `true` rend la valeur locale à la transaction.
- La fonction SQL de lecture du contexte doit retourner `NULL` si la variable
  est absente/vide ou mal formée; aucune policy ne doit convertir l'absence en
  accès global.
- Réinstaller le contexte après chaque `COMMIT`/`ROLLBACK` avant la prochaine
  lecture protégée : SQLAlchemy peut ouvrir une nouvelle transaction au cours
  d'une même requête. Ne jamais employer une variable de session persistante
  avec PgBouncer transaction-mode, où une connexion peut être réutilisée par
  un autre tenant.
- Le même contrat s'applique aux endpoints API key, streaming, Celery,
  planification, tâches réessayées et traitements batch. Les opérations
  réellement globales doivent utiliser un chemin/rôle distinct et auditable.
- Le `organization_id` fourni par un client ne devient pas fiable simplement
  parce qu'il est placé dans le contexte. Il doit être lié à la clé ou à
  l'adhésion authentifiée avant `set_config`.

## Politique des classes de tables

La [matrice tenant](./TENANT_ISOLATION_MATRIX.md) classe les 177 tables du
worktree et fournit des chemins FK candidats. Chaque table doit obtenir une
classification validée par son domaine avant qu'une policy soit générée.

- **Tenant direct** : policy `USING` et `WITH CHECK` exigeant
  `organization_id = app_private.current_organization_id()`. Les deux clauses
  sont nécessaires pour bloquer lectures/modifications hors tenant et
  insertions/migrations de tenant.
- **Tenant indirect** : relier la ligne à son parent tenant dans la policy ou
  dans une fonction d'accès étroite, sans accepter un ID parent libre. Vérifier
  les cycles de FK et de policies; envisager de matérialiser `organization_id`
  sur les lignes chaudes/sensibles et de protéger la cohérence par FK composée.
- **User-scoped** : appliquer une policy par `user_id` seulement lorsque la
  propriété personnelle est le contrat réel. Si l'objet est partagé entre
  membres d'une organisation, résoudre explicitement le tenant via l'adhésion
  ou la relation propriétaire; ne pas assimiler utilisateur et tenant.
- **Global/catalogue** : accès `SELECT` minimal au rôle runtime, écriture
  réservée au rôle de gestion correspondant. Pas de policy `true` générique
  sur toutes les tables.
- **System/sécurité** : séparer événements d'infrastructure, racine
  `organizations`, secrets/rotation et données administratives. Garder les
  écritures disponibles aux seuls services qui en ont besoin; ne pas exposer
  les secrets même au sein d'un tenant.
- **Unknown** : pas de migration de policy avant décision explicite sur
  propriétaire, modèle de partage, opérations worker et exigences de rétention.

## Conception des helpers et policies

- Helpers dans un schéma privé non exposé par PostgREST, noms qualifiés,
  paramètres bindés, `search_path` fixé et privilèges `EXECUTE` retirés à
  `PUBLIC` si un helper `SECURITY DEFINER` est réellement nécessaire.
- Préférer des fonctions `SECURITY INVOKER` et des relations FK non cycliques.
  Un helper privilégié ne doit ni accepter SQL/dynamique client ni offrir un
  `is_admin = true` générique.
- Activer RLS sur les tables protégées et utiliser `FORCE ROW LEVEL SECURITY`
  lorsque le propriétaire/runtime le requiert. Cela ne neutralise pas
  `BYPASSRLS`; le rôle runtime doit aussi être contrôlé par catalogue.
- Définir séparément `SELECT`, `INSERT`, `UPDATE`, `DELETE` et les clauses
  `WITH CHECK`; les règles d'accès ne se déduisent pas du seul CRUD API.
- Aucun accès par défaut lorsqu'un contexte tenant manque. Utiliser des tests
  SQL réels qui vérifient aussi `current_user`, `rolbypassrls`, `relowner`,
  grants et visibilité, pas seulement la présence de `relrowsecurity`.

## Déploiement progressif requis

1. Identifier et autoriser explicitement une base de staging jetable; confirmer
   sauvegarde/restauration et version Alembic, sans s'appuyer sur la cible
   configurée aujourd'hui.
2. Comparer le schéma réel aux migrations/modèles et corriger les migrations
   additives sur une branche dédiée; aucun downgrade destructif improvisé.
3. Créer les rôles/grants et tests PostgreSQL pour deux organisations, accès
   manquant, accès cross-tenant, API keys, tâches Celery et opérations admin.
4. Déployer d'abord l'instrumentation et vérifier le contexte transactionnel
   en modes session/transaction pooling; confirmer qu'aucun contexte ne fuit
   après erreur, commit, rollback ou réutilisation de connexion.
5. Appliquer les policies staging; vérifier refus par SQL direct du rôle
   runtime et fonctionnement des opérations légitimes; comparer API/RLS.
6. Après revue et preuve de restauration, proposer un changement production
   séparé, avec fenêtre, métriques, plan d'arrêt et approbation explicite.

## Invariants non négociables

- Isolation application maintenue avant, pendant et après le déploiement RLS.
- Aucun rôle web/worker avec `BYPASSRLS` ni propriétaire des tables.
- Pas d'identifiant tenant pris seul dans le corps/chemin de requête.
- Le contexte RLS est lié à la transaction et effacé automatiquement par la
  fin de celle-ci.
- Aucun changement DB live tant que l'environnement n'est pas déterminé.
