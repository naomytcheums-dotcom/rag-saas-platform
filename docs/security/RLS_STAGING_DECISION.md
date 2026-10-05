# Décision RLS staging — 2026-10-03

**Décision préparée, pas appliquée.** Aucun catalogue DB consulté.
Source : [design existant](./RLS_POLICY_DESIGN.md).

## Cible et contexte

Seul host autorisé : `db.<STAGING_PROJECT_REF>.supabase.co`, port 5432,
database/user `postgres`. Un nom de projet Supabase affiché dans l'UI
n'apparaît pas dans son hostname : ne pas tester le substring « -STAGING ».
L'allowlist exacte est plus restrictive qu'un label libre.

La résolution OS a échoué; un resolver alternatif a fourni une IPv6,
mais le transport TCP a échoué `errno=10051` (réseau inaccessible).
Aucune authentification DB, SQL, extension, migration ou policy exécutée.
Le secret divulgué dans le chat n'est pas recopié dans les logs/rapports;
le fichier local contient un placeholder et aucun fallback production.
Sa rotation est un prérequis de provisioning sûr, pas une action réalisée.

## Modèle retenu pour le laboratoire staging

- Isolation API existante conservée, pas de changement de rôle runtime
  déployé ni de connexion production.
- Policies sur tables physiques `public` ayant `organization_id uuid`
  direct, découvertes dans le catalogue **après** migration.
- Exclusions explicites : `audit_logs`, `document_audit_logs`,
  `jwt_signing_keys`, `permissions`, `plans`, `billing_plans`.
- Pas de policy devinée sur FK indirectes, user-scoped ou tables UNKNOWN.
- Aucune désactivation des RLS historiques des tables globales/système :
  ce serait une ouverture d'accès, non nécessaire pour le test.
- Policies **TO rag_staging_tenant**, rôle NOLOGIN, NOSUPERUSER,
  NOBYPASSRLS, distinct du propriétaire; pas `TO PUBLIC`, `anon` ou
  `authenticated`. Les grants sont limités aux tables choisies.
- Contexte `app.current_organization_id` installé via `set_config` paramétré
  avec `is_local=true`, durée d'une transaction.
- `NULLIF(current_setting('app.current_organization_id', true), '')::uuid`
  : contexte absent/vide produit NULL et zéro ligne; UUID invalide produit
  erreur plutôt qu'une autorisation de secours.
- `USING` et `WITH CHECK` exigent tenant égal au contexte.
- Pas de `FORCE RLS` implicite : le propriétaire n'est pas le rôle de test,
  et FORCE ne résout pas `BYPASSRLS`.

## Limites essentielles

Les policies ne prouvent **rien** si testées uniquement comme `postgres`
superuser/BYPASSRLS. `test_staging_rls_under_nonbypass_role` vérifie les
flags du rôle restreint, l'absence de contexte, A/B et refus de déplacement.

Ce laboratoire n'est pas un câblage RLS complet de l'application :
les workers, API keys, objets user-scoped, tables indirectes et requêtes
multi-tenant nécessitent un design explicite. Le contexte org authentifié
doit être fixé dans chaque transaction avant un rôle runtime restreint.
Une GUC modifiable n'authentifie pas à elle seule l'utilisateur final.

Le test API utilise le rôle de migration pour tester les refus applicatifs;
le test RLS utilise `SET LOCAL ROLE` séparément. Les deux preuves sont
distinctes. Aucun PASS RLS ne sera déclaré sur un simple test HTTP SQLite.

## Exécution future, strictement staging

Script : `scripts/staging_validate.py policies --execute`, uniquement après
configuration locale non-placeholder et inspection du catalogue migré.
DDL identifiants issus du catalogue et quotés par SQLAlchemy; aucune valeur
utilisateur libre n'est concaténée comme identifiant.
Tous les DDL sont dans une transaction. Les sorties « prepared » ne sont
pas une preuve de commit si l'action termine en erreur.

Validation : `scripts/staging_validate.py tests --execute`.
Pas de mutation DB effectuée dans cette rédaction.
