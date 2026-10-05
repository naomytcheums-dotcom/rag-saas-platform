# Plan production — ne pas exécuter

Date : 2026-10-04. **NO-GO actuel. Aucune production connectée.**

## États et périmètre

- Production actuelle **0130 : déclarée par l'utilisateur**, non vérifiée.
- Nombre d'organisations/users/documents : déclarations utilisateur, pas
  inventaire live; aucune requête production dans cette mission.
- Cible locale : **0132**; migrations historiques inspectees sans modification.
- Staging : **0132**, 178 tables publiques, pgvector 0.8.2, HNSW.
  Revision verifiee visuellement dans Supabase Table Editor.
  Neuf IDOR et test DB sous role restreint passent; cela ne valide pas
  tous les parcours produit ni le role runtime PostgreSQL.
- Migrations prévues si production est bien à 0130 : 0131 puis 0132.
- 0131 : active RLS sur onze tables, ne crée pas de policy.
- 0132 : colonne nullable `workspaces.description`.
- Aucune migration historique 0001–0132 modifiée dans cette mission.
- Les policies expérimentales et le rôle `rag_staging_tenant` ne doivent
  jamais être copiés automatiquement en production.

## Préconditions bloquantes

1. Vérifier provenance Git et heads; revue des fichiers non suivis.
2. Staging joignable et migre : preuve acquise sur session pooler officiel.
   Repetition depuis clone et backup/restore restent a valider.
3. IDOR API et RLS documents sous role non-BYPASS passes; poursuivre
   couverture des tables indirectes et du role runtime, pas seulement le role lab.
4. Revue des rôles/grants et du plan RLS production; ne pas basculer le
   rôle runtime sans contexte transactionnel câblé.
5. Sauvegarde production réalisée par opérateur autorisé et restore validé
   sur une seconde DB jetable. Cela n'est pas effectué par cette mission.
6. Vérifier version `pg_dump`/serveur, accès stockage et rétention.
7. Tests backend/frontend et risques restants acceptés.
8. Autorisation de release séparée, maintenance et communication.

## Ordre de deploiement recommande

Les copies locales de la revision 0132 different seulement par leur
docstring et leurs annotations de types; revision, parent 0131 et operation
de schema sont identiques. La version de
`api/alembic/versions/0132_workspace_description.py` fait foi.
`scripts/pending/` est obsolete pour cette revision; ne pas executer
`scripts/pending/enable_kb_description.py`.

Si la production est effectivement en revision 0130, appliquer d'abord les
migrations 0131 puis 0132, verifier leur revision et les acces effectifs
des roles API/worker, puis deployer le code applicatif qui mappe
`workspaces.description`. Le code actuel emet des lectures ORM de
`Workspace` incluant cette colonne; avant 0132, ces requetes echoueraient
avec une erreur PostgreSQL de colonne inexistante. Ne pas appliquer 0131
tant que l'impact de RLS sans policy sur un role runtime non-BYPASS n'est
pas valide. La revision 0130 de production est une declaration utilisateur,
pas une observation live; confirmer l'etat reel avant toute operation.

## Fenêtre et déroulement proposé

Durée UNKNOWN jusqu'à mesure staging. Planifier une fenêtre hors pic avec
budget d'arrêt fixé par l'opérateur, pas une estimation inventée.
Geler les déploiements concurrents; conserver build précédemment validé.
L'opérateur vérifie host/project et révision 0130 sans afficher credentials.
Il applique uniquement la migration versionnée après sauvegarde/approbation.
Il vérifie head, colonne description, contraintes, index, rôle, refus A/B,
logs, ingestion, worker, retrieval, paiement sandbox et UI.

## Rollback

Privilégier rollback **applicatif** vers le build antérieur si la colonne
nullable additive reste compatible. Ne pas supprimer immédiatement les
descriptions écrites après migration.

Le downgrade 0132 supprime `workspaces.description` et ses données.
Le downgrade 0131 désactive RLS sur les onze tables; ce changement de
sécurité doit être explicitement revu. Les migrations ne constituent pas
une restauration de données perdues.

Si rollback schéma nécessaire : arrêter les écritures, exporter les
descriptions, confirmer backup restaurable, répéter le downgrade sur clone,
valider applications/rôles puis appliquer seulement avec approbation.
En incident de corruption : restauration sur DB distincte vérifiée et
bascule contrôlée; ni overwrite ni restore direct non testé.

## Checklist post-migration

- Révision et nombre de tables conformes.
- Description nullable et round-trip API correct.
- Index HNSW et extension vector présents.
- Jobs Celery et health checks corrects.
- Lecture/écriture tenant A et refus tenant B.
- Aucun provider/billing de production appelé par des tests de contrôle.
- Erreurs, latence, coûts et alertes observés.
- Sauvegarde et rollback prêts, rapport signé.

Ce fichier est un **plan**, pas une instruction d'exécuter la production.

## Comparaison et risques observes

| Point | Staging observe | Production |
|---|---|---|
| Alembic | 0132 | 0130 declare, non observe |
| Tables publiques | 178 | Non inventoriees |
| pgvector / HNSW | 0.8.2 / present | Non observes |
| Policies experimentales | 77, uniquement role lab | Ne pas recopier |
| Backup restaure | Non demontre sur dump Supabase | Prerequis operateur |

0131 active RLS sur onze tables sans policy : un role non-BYPASS peut
perdre ses acces (default deny). Confirmer les roles effectifs API,
worker et integrations avant release. 0132 ajoute une colonne texte
nullable, sans backfill; prevoir le verrou DDL et tester compatibility
ancien build. Son downgrade perd les descriptions. Le downgrade 0131
reouvre une frontiere de securite : ne pas l'utiliser comme rollback banal.

La duree mesuree du run backend complet est 49m08s, pas une estimation
de migration ni de restauration. Les lots staging ont contourne une
connexion coupee; reproduire cette procedure sur clone avant production.
