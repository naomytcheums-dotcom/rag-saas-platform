# Résumé de l'audit Copilot (« radiographie » du 2026-10-10) — à donner à ChatGPT

Projet : plateforme RAG SaaS multi-tenant (FastAPI, Next.js 16, Supabase/pgvector, Render, Vercel, Celery/Redis, Stripe/Paystack).
Audit en lecture seule, HEAD `59d5ec9`. Aucun service distant appelé : rien n'est prouvé en production.

## Chiffres
943 opérations HTTP, 177 tables, 136 migrations (head 0136), 57 pages frontend, 6 130 tests backend, ~87 000 lignes Python d'API.
Prouvé le 2026-10-10 : ruff propre, tsc/eslint code 0, vitest 178 tests verts, GitHub Actions CI verte, CircleCI api-tests (couverture 77,41 %) et rag-pipeline-regression verts.

## Risques confirmés
1. **Isolation tenant sans barrière en base** : RLS activé mais 0 FORCE, 0 policy, rôle applicatif contournant. Tout repose sur les filtres `organization_id` (101 routeurs, 284 services).
2. **Aucun worker/beat Celery dans l'image de production** (Render gratuit 512 Mo) : factures périodiques, crédits, purge RGPD, ingestion non garanties.
3. **Migrations manuelles, état de prod non prouvé** ; 0136 (`notification_templates`) à appliquer, sinon routes de modèles de notification en 500.
4. **Aucune preuve de sauvegarde/restauration** (RPO/RTO).
5. **Facturation jamais testée avec un vrai fournisseur** ; pas de remboursement (BILL-016) ; pas d'achat de crédits Paystack ; devises incohérentes (BILL-018) ; plafonds non atomiques (BILL-012).
6. **Qualité RAG non mesurée** (Recall@K, MRR, NDCG existent dans le code, aucune valeur réelle) ; chemin de recherche numpy vs HNSW incertain ; chunking avancé non câblé.
7. **Documentation contradictoire** : `agents.md` (routes `/api/eval/*`, `/mcp/v1/servers*` inexistantes, Python 3.11), `render.yaml` (ancien prototype Streamlit), cahier des charges (515 fonctions non reproductible, Partie 15 tronquée).
8. 84 routes sans authentification détectée (à classer), 183 routes sans test, tests surtout sur SQLite.
9. Rate limiting en mémoire sans Redis ; `/metrics` public si `METRICS_AUTH_TOKEN` absent.
10. 122 constats historiques sur 173 sans trace de correction (non revérifiés).
Dettes : deux pipelines RAG, deux CI proches de leur limite de durée, importeurs avec boto3 synchrone restant, dépendances à mettre à jour (stripe 16, sqlalchemy 2.1, typescript 7).

## Plan proposé (ordre conseillé : P0-6 → P0-3 → P0-4 → P0-2 → P0-5 → P0-1 → P1-1 → P1-2 → reste)
- **P0** : décider isolation (documentée + test de contrat, ou rôle non contournant + FORCE RLS + policies, table par table) ; worker Celery + beat supervisés ; process de migration + appliquer 0136 avec sauvegarde ; sauvegarde restaurée et prouvée ; facturation validée en sandbox Stripe/Paystack + politique de remboursement ; vérifier la configuration prod (`CREDITS_ALLOW_UNPAID_TOPUP`, `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS`, `COOKIE_SECURE`, `METRICS_AUTH_TOKEN`, `MCP_STDIO_ENABLED`, `CLAMAV_ENABLED`).
- **P1** : mesurer la qualité RAG (Eval Lab, jeu réel type SQuAD 2.0) ; clarifier le chemin de recherche ; classer les 84 routes sans auth ; tests PostgreSQL en CI ; remboursements/crédits Paystack/devises ; finir TEN-003 ; pages de restauration/réactivation/2FA ; réexaminer les 122 constats.
- **P2** : aligner la documentation, réduire la durée des CI, benchmarks, observabilité, mise à jour des dépendances, couverture frontend/SDK, nettoyage des branches/worktrees.
- **P3** : onboarding, conditions/confidentialité/SLA, analyse concurrentielle, fonctions annoncées non câblées, Partie 15.

## Décisions ouvertes pour la propriétaire
Isolation (applicative documentée ou RLS contraignant) ; hébergement du worker ; politique de remboursement ; clés de **test** Stripe/Paystack ; document de référence pour le périmètre (Partie 15 perdue) ; devise des packs (USD) vs plans (EUR) ; crédits Paystack.

## Incident à traiter en parallèle
Des comptes de test (preview@, design@, client@, boss@example.com) ont été créés par erreur dans la base de production par l'aperçu local de l'assistant. Plan : requête d'inspection en lecture seule, suppression seulement si les organisations liées sont 100 % test, vérification des logs Supabase des 8 et 10 octobre, création d'un seul compte superadmin choisi par la propriétaire. Le serveur d'aperçu local est maintenant verrouillé (refuse de démarrer si une URL n'est pas locale).

## Questions à poser à ChatGPT
1. Dans quel ordre traiter ces points, et lesquels bloquent une mise en vente ?
2. Isolation : application seule ou RLS FORCE ? Quel coût de migration pour 80 tables ?
3. Hébergement du worker Celery sous budget (Render payant, Fly, Railway, VPS) ?
4. Protocole de test SQuAD 2.0 (Recall@k, exactitude des citations, questions sans réponse, séparation retrieval/génération).
5. Politique de remboursement et gestion des devises.
