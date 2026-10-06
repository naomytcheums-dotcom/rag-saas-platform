# Readiness production — 2026-10-06

## Décision : NON / NO-GO

Aucun déploiement ou contrôle production réalisé. Une suite frontend verte
et du code présent ne prouvent pas l'intégralité des parcours.

## Mise a jour operateur - observations limitees

Lecture seule de la base distante du dotenv general, observations fournies
par l'assistant, non repetees ici : revision 0130; role postgres avec
BYPASSRLS; 178 tables publiques, 12 sans RLS (onze de 0131 et
alembic_version); zero politique; workspaces.description absente;
pgvector 0.8.2. Le role API contourne RLS : 0131 sans politiques ne le
bloque pas, mais ne prouve aucune isolation runtime par RLS.

Operateur : `.venv\Scripts\python.exe -m alembic upgrade head`, 0131 puis
0132 AVANT le deploiement du code. L'outil de l'assistant a refuse
l'application des migrations au titre de la protection deploiement
production. Sauvegarde complete pg_dump custom (environ 25 Mo) prise avant
tout changement, locale et ignoree par Git; restauration NON VERIFIEE.
Donnees historiques : 63/71 utilisateurs @example.com, 1523/1576
organisations nommees "test", du 11 septembre au 2 octobre.
Nettoyage cible propose, NON effectue.

### Configuration et changements de contrat

- DISCORD_GATEWAY_SHARED_SECRET : X-Gateway-Secret obligatoire pour
  POST /integrations/discord/message; absence = refus de toute requete.
- TEAMS_BOT_ID : audience du jeton Microsoft Bot Framework; sinon 401.
- METRICS_AUTH_TOKEN : definir pour tout deploiement joignable par Internet.
- AGENT_MEMORY_AUTO_EXTRACT=false : activation ajoute un appel LLM par execution.
- PGVECTOR_ITERATIVE_SCAN=true, PGVECTOR_MAX_SCAN_TUPLES=20000 :
  balayage iteratif HNSW.
- LICENSE_VALIDATE_RATE_LIMIT_MAX_ATTEMPTS=20 et
  LICENSE_VALIDATE_RATE_LIMIT_WINDOW_SECONDS=60 : limite de validation licence.
- /partners/register exige accept_terms, controles du mot de passe et limite
  de debit; /integrations/n8n/status et /airbyte/status exigent une connexion.
- ANSWER_RELEVANCE_USE_LLM, CONTEXT_RELEVANCE_USE_LLM,
  CLAIM_VERIFICATION_USE_LLM : activation refusee au demarrage, non implementes.

### Dependances et performance

opa-python-client retire pour conflit aiofiles avec beeai-framework :
client HTTP interne. pyjwt 2.15.0; Next 16.3.8; npm audit fourni = zero.
WeasyPrint 65 : avis restants attenues par echappement HTML et url_fetcher
qui refuse tout, sans disparition de l'avis. diskcache via dspy :
aucun correctif indique. HNSW iteratif ajoute; mesure a 100/1000/10000
documents EN COURS, aucun chiffre de resultat. BM25 recharge tous les
textes de l'organisation a chaque requete (O(N)).

## Historique - gates du 2026-10-03

| Gate | État actuel | Condition de sortie |
|---|---|---|
| Identité production / revision | 0130 déclaré par utilisateur, non vérifié | Opérateur autorisé vérifie avant release séparée |
| Staging réseau | BLOCKED_EXTERNAL, IPv6 réseau inaccessible | Connexion sûre sur cible explicitement allowlistée |
| Credential staging | Placeholder local; secret chat non recopié | Rotation et provisioning local sûr |
| Migrations staging | Non exécutées, head live UNKNOWN | Rejouer 0001–0132 sur DB isolée, catalogue cohérent |
| Isolation API PostgreSQL | 11 tests live écrits mais skippés | Owner controls puis A/B et refus cross-tenant |
| RLS | Décision de labo; aucune policy live | Rôle non-BYPASS et contexte transactionnel, FK indirectes revues |
| Backend suite complète | 4 993 pass, 125 fail, 208 skips; 104 échecs passants au rejeu ciblé | Résoudre les cas restants puis nouveau run complet; ne pas additionner les runs |
| Backend Ruff | 3 253 diagnostics initiaux | Revue ciblée puis convergence, pas suppression de règles |
| Frontend | 112 pass, type-check vert, lint 0 erreur/32 warnings | Maintenir résultats et traiter warnings selon priorité |
| Backup/restore | Non exécuté; outils/daemon indisponibles | Dump et restauration sur DB distincte, RTO/RPO mesurés |
| Billing sandbox / providers | Non validés live | Tests sandbox, budgets et idempotence |
| Observabilité réelle | UNKNOWN | Réception d'un événement de test sans divulgation |
| Voix RTC | Plan uniquement | Intégration séparée après validation staging |

## Sources et portée

- [Rapport staging](./audit/STAGING_TEST_REPORT.md).
- [Plan production non exécuté](./audit/PRODUCTION_MIGRATION_PLAN.md).
- [Corrections](./AUTONOMOUS_AUDIT_05_FIXES.md).
- [Backup/restore](./operations/BACKUP_RESTORE.md).
- [Performance](./PERFORMANCE_REPORT.md).
- [Inventaire routes/tables](./AUTONOMOUS_AUDIT_03_SECURITY.md).

Ne pas présenter `postgres`/BYPASSRLS comme une preuve de sécurité RLS.
Ne pas recopier policies staging en production ni prétendre à une
validation basée sur les déclarations du message utilisateur.
