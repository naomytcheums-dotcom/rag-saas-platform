# 05 — Sauvegarde et restauration

**Statut global : BLOCKED_EXTERNAL.** Le dépôt ne contient aucune preuve de sauvegarde de la base hébergée (Supabase) ni du stockage objet ; aucun accès n'a été utilisé ni demandé. Ce document donne une procédure exécutable,
des objectifs proposés (≠ mesures) et le résultat d'un **test de restauration réellement exécuté sur une base jetable locale**.

## Preuve obtenue : restauration d'une base de test (local, jetable)
| Étape | Commande (conteneur `rag-pr1-disposable-pg`, PostgreSQL 17 + pgvector) | Résultat mesuré |
|---|---|---|
| Source | base `rag_remediation_scratch` : chaîne Alembic complète jusqu'à `0137`, 1 organisation de test | — |
| Sauvegarde | `pg_dump -Fc -d rag_remediation_scratch -f /tmp/rag_scratch.dump` | **1 s**, 545 Ko |
| Restauration | `CREATE DATABASE rag_restore_scratch` puis `pg_restore --no-owner -d rag_restore_scratch` | **2 s**, code 0 |
| Cohérence | requête de comparaison source/restaurée | identiques : version Alembic `0137`, 179 tables, 178 avec RLS, 6 politiques, extension `vector`, index HNSW présent, 1 organisation |
Les bases et le fichier de test ont été supprimés après la mesure. **Limites** : base minuscule (pas de volumétrie), pas de rôles/privilèges de production, pas de stockage objet, pas de test applicatif (démarrage de l'API) sur la base restaurée. Ces durées ne sont **pas** un RTO de production.

## Procédure proposée pour la production (à exécuter par la propriétaire, rien n'a été lancé)
1. **Inventaire** : activer/vérifier la sauvegarde gérée du fournisseur (quotidienne et point-in-time si le plan l'offre) ; noter plan, fenêtre de rétention, région. Noter aussi : bucket S3/R2 des documents (versioning, réplication), Redis (peut être reconstruit : files et limiteurs), secrets (gestionnaire de secrets, pas dans les sauvegardes).
2. **Sauvegarde logique complémentaire** (indépendante du fournisseur) : `pg_dump -Fc` depuis le pooler de session (port 5432) avec un rôle en lecture seule, chiffrée, stockée hors du fournisseur. Fréquence proposée : quotidienne ; rétention 30 jours (à valider).
3. **Test de restauration mensuel** dans une base **jetable** (jamais sur la production) : `createdb rag_restore_check` → `pg_restore --no-owner` → contrôles : `select version_num from alembic_version` = version attendue, `select count(*)` des tables clés (organizations, users, documents, document_chunks, credits, invoices), extension `vector`, index HNSW, politiques RLS, puis démarrage de l'API en mode `RAG_RUN_MODE=preview` (`scripts/run_local_preview.py`) et `GET /health/ready`.
4. **Documents** : les fichiers sont dans S3/R2 (clés `documents/{org}/{doc}/…`) ; une restauration de base sans les objets laisse des documents sans fichier : sauvegarder/versionner le bucket et tester la lecture d'un objet restauré.
5. **Après restauration** : régénérer les embeddings manqués (`reindex`), relancer les tâches `pending`, vérifier les factures (idempotence des tâches mensuelles) et réémettre les webhooks fournisseur manqués.

## Objectifs proposés (à valider ; ce sont des objectifs, pas des résultats)
RPO ≤ 24 h avec sauvegarde quotidienne seule (≤ 5 min si point-in-time disponible). RTO ≤ 4 h (restauration + migration + vérification). Mesurer le RTO réel au premier test mensuel.

## Checklist de reprise après incident
- [ ] Déclarer l'incident, geler les écritures (mode maintenance : suspendre l'API ou rendre la base en lecture seule).
- [ ] Identifier le dernier état sain (heure, version de schéma `alembic_version`).
- [ ] Restaurer dans une **nouvelle** base, valider avec la checklist de l'étape 3.
- [ ] Appliquer les migrations manquantes (`alembic upgrade head`) sur la base restaurée seulement.
- [ ] Basculer `DATABASE_URL` (et `DATABASE_URL_TRANSACTION`) vers la base restaurée ; redémarrer API, worker, beat (un seul beat).
- [ ] Vérifier : connexion, upload + ingestion, chat avec citations, facture/crédit, webhook de test.
- [ ] Comparer les paiements du fournisseur avec les factures/crédits de la période perdue ; corriger manuellement.
- [ ] Rédiger le post-mortem et mettre à jour ce document.

## Responsabilités (proposées)
Propriétaire : plan et rétention, accès aux sauvegardes, validation du RPO/RTO. Ingénierie : script de sauvegarde logique, test mensuel, runbook. Aucune de ces responsabilités n'est établie dans le dépôt.
