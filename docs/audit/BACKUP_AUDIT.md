# Audit des sauvegardes et de la restauration

Date: 2026-10-03. Cette analyse est limitée aux artefacts locaux et aux
références documentaires; aucune console cloud, base, bucket, snapshot ou
backup n'a été interrogé.

## Verdict

**État des sauvegardes distantes : BLOCKED_EXTERNAL / UNKNOWN.**
Le workspace ne permet pas de vérifier la politique réellement active,
l'âge/couverture des sauvegardes, la rétention, le chiffrement, le compte de
stockage, les droits, l'immuabilité, les snapshots PITR, la dernière
restauration ou son RTO/RPO. Aucune preuve d'un restore réussi n'a été
obtenue. Ne pas présenter une configuration fournisseur supposée comme
fonctionnelle.

## Fonctionnalités présentes dans les fichiers locaux

- `scripts/backup.sh` lance `pg_dump` dans le conteneur Compose
  `postgres`, compresse en gzip et écrit `./backups/backup_<timestamp>.sql.gz`
  par défaut. Le script prune les fichiers locaux de plus de 30 jours par
  défaut; `BACKUP_RETENTION_DAYS=0` désactive cette suppression.
- Le même script propose une copie S3/R2 opt-in (`BACKUP_S3_ENABLED`,
  bucket/prefix et AWS CLI). L'upload n'est pas tenté par défaut. Si la CLI
  manque ou l'upload échoue, le script affiche un warning; il ne prouve donc
  pas qu'une copie distante existe.
- La rétention distante parcourt la liste de tout l'objet sous le prefix et
  supprime les objets datés avant la coupure; elle ne filtre pas explicitement
  le nom `backup_*.sql.gz`. Un prefix partagé avec d'autres objets présente
  un risque de suppression hors backups.
- `scripts/restore.sh` vérifie l'existence du fichier, demande une
  confirmation interactive, puis envoie le SQL décompressé vers `psql` dans
  le conteneur PostgreSQL. Il écrase la base cible. Le code ne vérifie pas de
  checksum/signature et n'effectue pas de validation ou répétition automatique
  après restauration.
- `docs/install/BACKUP_AND_RESTORE.md` documente ces commandes, le caractère
  base-seulement du dump, la nécessité de sauvegarder séparément le stockage
  objet et l'absence de planification gérée par l'application; l'exemple est
  un cron local. La documentation affirme aussi que `update.sh` lance un
  backup avant upgrade; ceci décrit le flux self-hosted local, pas une
  exécution prouvée ici.
- Aucun secret ou fichier `.env` n'a été lu; les valeurs effectives de
  configuration, la présence de Docker/AWS CLI, les volumes et comptes cloud
  n'ont pas été inspectés.

## Inventaire de preuves

| Domaine | État | Ce qui est nécessaire |
|---|---|---|
| Politique de sauvegarde PostgreSQL hébergée | UNKNOWN | Export non secret des paramètres du fournisseur et validation de l'environnement |
| PITR / fréquence / fenêtre | UNKNOWN | Paramètres fournisseur et preuve du point de restauration |
| Sauvegarde des objets et médias | NON COUVERTE par le `pg_dump` local documenté; sauvegarde séparée inconnue | Inventaire des buckets, versioning/rétention et copie cohérente |
| Chiffrement en transit/au repos | UNKNOWN | Configuration et gestion de clés du fournisseur |
| Comptes/privilèges et séparation | UNKNOWN | Revue IAM sans divulguer de secret |
| Dernière exécution réussie | UNKNOWN; aucun journal d'exécution fourni | Journal fournisseur horodaté et vérifiable |
| Restauration complète | UNKNOWN / non prouvée; le script peut la lancer mais aucune exécution n'est prouvée | Restore vers environnement jetable indépendant |
| RTO / RPO mesurés | UNKNOWN | Exercice chronométré, perte de données mesurée |
| Cohérence PostgreSQL + stockage objets | UNKNOWN | Procédure de snapshot cohérente ou manifeste de versions |
| Réplication géographique / région secondaire | UNKNOWN | Configuration fournisseur et test d'accès/restauration |
| Protection contre suppression/ransomware | UNKNOWN | Rétention immuable/soft-delete et permissions séparées |
| Sauvegarde des configurations/clefs | UNKNOWN | Coffre de secrets et procédure documentée de récupération, sans exporter les secrets |

## Risques

- Une migration destructive ou une erreur opérateur peut dépasser la capacité
  de restauration si aucun point recoverable récent n'existe.
- Restaurer PostgreSQL sans les fichiers/object storage associés peut produire
  des références brisées; l'inverse peut exposer des fichiers orphelins.
- Une sauvegarde dans le même compte/région avec les mêmes permissions peut
  ne pas protéger d'une suppression ou compromission de compte.
- Un dump n'établit pas la restauration du WAL/PITR, des extensions pgvector,
  des policies, des rôles ou des grants.
- Le dump local ne contient pas l'object storage; un restore DB seul peut
  laisser documents/médias absents. Le `pg_dump` par défaut ne démontre pas la
  conservation des rôles globaux PostgreSQL.
- La purge S3/R2 basée sur un prefix partagé peut supprimer des objets qui ne
  sont pas des backups; configurer un prefix dédié avant d'activer la rétention.
- L'upload distant est optionnel et une erreur d'upload ne prouve pas le
  succès d'une copie hors site; l'utilisateur doit surveiller ses warnings.
- Une preuve de RLS/RBAC ne remplace pas la validation de sauvegarde; de même,
  une sauvegarde non testée n'est pas une preuve de recoverability.

## Plan de vérification futur

1. Identifier par écrit un environnement DEV/TEST/STAGING jetable; ne pas
   utiliser une cible inconnue ou la production.
2. Obtenir les paramètres de sauvegarde, rétention et PITR depuis la console
   autorisée, sans extraire de credentials.
3. Créer un point de restauration; consigner l'ID non sensible et l'heure.
4. Restaurer dans une instance isolée avec accès sortant désactivé; confirmer
   schéma, revision Alembic, extension, policies, rôles/grants et échantillons
   de cohérence selon une procédure approuvée.
5. Restaurer/associer le stockage objet correspondant; vérifier checksums et
   nombre de références sans exporter le contenu sensible.
6. Mesurer RTO/RPO, relever les écarts, puis répéter jusqu'à validation.
7. Ne tester aucune migration ni modifier les politiques avant preuve de
   restauration et autorisation explicite.

## Conclusion

Les scripts self-hosted de backup/restore existent, mais leur exécution,
planification effective, copie distante, sécurité opérationnelle et capacité
de reprise sont **UNKNOWN**. Aucune sauvegarde ni restauration n'a été créée,
lue ou testée dans la présente session. Le service de sauvegarde managée du
SaaS demeure **UNKNOWN**; la présence de ces scripts ne prouve que le chemin
self-hosted documenté.
