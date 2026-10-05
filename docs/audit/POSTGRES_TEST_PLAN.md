# Plan de validation PostgreSQL en lecture seule

Date: 2026-10-03. Cette procédure prépare une inspection de métadonnées
PostgreSQL sans modifier les données ou le schéma. Elle n'autorise aucune
connexion au serveur inconnu dans cette session.

## Profil d'integration staging et controle de policies

Copier `.env.staging.example` vers `.env.staging` (ignore par Git), puis
configurer localement `ENVIRONMENT=staging`, `DATABASE_URL` et les trois
variables obligatoires `STAGING_ALLOWED_DIRECT_HOST`,
`STAGING_ALLOWED_POOLER_HOST`, `STAGING_ALLOWED_POOLER_USER`.
Les variables du processus ont priorite sur celles du fichier staging.
Une valeur absente ou vide refuse la cible en nommant uniquement la variable;
les espaces reserves et jokers sont refuses. La comparaison host/utilisateur
reste exacte, avec port 5432, base `postgres` et SSL requis.
Le loader ne consulte jamais `.env` et ne journalise aucune valeur.
Le processus enfant recoit aussi l'allowlist autorisee du runner.
Ne pas committer `.env.staging`, ni les valeurs reelles de ces variables.

Le test `test_rls_policies_exist_on_staging` est sélectionné seulement si
`RAG_EXPECT_STAGING_RLS_POLICIES=1`. Le runner autorisé pour staging,
`python -m scripts.staging_validate tests --execute`, définit cette variable
lui-même avant de lancer pytest. Pour cibler le module d'intégration
PostgreSQL par le même garde staging :

```powershell
.\.venv\Scripts\python.exe -m scripts.staging_validate tests --execute --postgres-integration
```

Le mode explicite de contrôle sans l'attente de policies ne doit être utilisé
que pour vérifier le profil PostgreSQL générique :

```powershell
.\.venv\Scripts\python.exe -m scripts.staging_validate tests --execute --postgres-integration --without-staging-policy-expectation
```

Ce second mode ignore le seul test du minimum de 77 policies; il ne constitue
pas une validation du catalogue staging. Le test distinct vérifiant RLS
activé sur toutes les tables reste actif dans les deux profils. Le pipeline
staging normal ne doit pas passer l'option d'exception.

### Tentatives d'execution — 2026-10-05

- Profil staging avec politiques :
  `.\.venv\Scripts\python.exe -m scripts.staging_validate tests --execute --postgres-integration`
  a repondu `BLOCKED: Staging credential is not provisioned locally; no connection attempted.`
- Profil PostgreSQL generique, sans attente des politiques :
  `.\.venv\Scripts\python.exe -m scripts.staging_validate tests --execute --postgres-integration --without-staging-policy-expectation`
  a repondu `BLOCKED: Staging credential is not provisioned locally; no connection attempted.`
- Les deux commandes ont ete refusees par le garde avant le lancement de
  pytest : aucun test de `test_postgres_integration.py` n'a demarre, aucune
  connexion ni requete staging n'a eu lieu. Statut : `BLOCKED_EXTERNAL_PROVIDER`.

## Blocage actuel

- Le type d'hôte vu dans l'historique d'audit local est Supabase/non-local;
  DEV, TEST, STAGING ou PRODUCTION n'est pas déterminé.
- Le nom de base, rôle, revision Alembic, droits, politique réseau, maintenance
  et possibilité de restauration ne sont pas vérifiés ici.
- Aucune connexion DB, requête catalogue, migration, création d'extension,
  modification de rôle/policy ou mutation de données n'a été lancée.
- En conséquence, toute validation PostgreSQL live demeure
  **BLOCKED_EXTERNAL** jusqu'à identification et approbation explicites d'une
  base jetable DEV/TEST/STAGING.

## Prérequis avant exécution future

1. Créer ou choisir une base jetable clairement désignée DEV/TEST/STAGING;
   ne jamais utiliser une cible de production ou une chaîne dont
   l'environnement n'est pas prouvé.
2. Obtenir une sauvegarde restaurable et prouver le restore isolé.
3. Fournir à l'exécution `POSTGRES_READONLY_AUDIT_URL` (jamais imprimée) avec
   un rôle de lecture de catalogues.
4. Définir `RAG_POSTGRES_READONLY_AUDIT_APPROVED=YES` après revue humaine et
   lancer avec `--execute --environment DEV|TEST|STAGING`.
5. Revoir les résultats avant toute décision; le script n'applique ni
   migration, ni RLS, ni index, ni correction.

## Contrôles exécutés par le script

- serveur/base/rôle/version et drapeaux de lecture seule/bypass/superuser;
- état RLS, FORCE RLS et propriétaire sur les tables `public`;
- policies déclarées dans `pg_policies`;
- présence/version de l'extension `vector`;
- révision Alembic si la table `alembic_version` est visible;
- privilèges accessibles au rôle courant dans le schéma public.

Le script n'inspecte aucun enregistrement applicatif, contenu documentaire,
embedding, credential ou secret. Il n'imprime pas l'URL.

## Exécution prévue — pas exécutée dans cette phase

```powershell
$env:RAG_POSTGRES_READONLY_AUDIT_APPROVED = "YES"
$env:POSTGRES_READONLY_AUDIT_URL = "<URL de staging fournie hors dépôt>"
.\.venv\Scripts\python.exe scripts\postgres_readonly_audit.py --execute --environment STAGING
```

Ne jamais enregistrer la valeur URL dans ce document, la ligne de commande,
un log, le dépôt ou une preuve.

## Résultats à capturer si une exécution est autorisée

- identité d'environnement non sensible et propriétaire du test;
- statut/codes de sortie et résumé des catalogues;
- nombre de tables RLS on/off, FORCE RLS on/off, nombre de policies;
- extensions et revision Alembic visibles;
- warnings/permissions et erreurs sans URL ni credential;
- preuve d'absence de DDL/DML et de rollback de la transaction read-only.

Les résultats doivent ensuite compléter le rapport et être revus avant
toute modification. Un audit read-only ne suffit pas à prouver l'isolation
tenant, la sécurité des rôles Supabase REST, les backups ou les performances.
