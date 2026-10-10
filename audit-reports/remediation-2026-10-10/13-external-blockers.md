# 13 — Blocages externes (actions nécessitant votre intervention)

Aucun accès n'a été inventé ; rien n'a été appelé sur Supabase, Render, Vercel, Stripe, Paystack, Redis, S3 ou un fournisseur LLM.

| # | Blocage | Raison exacte | Action externe requise | Compte/service (sans secret) | Risque | Vérification / reprise | Si le blocage reste ouvert |
|---|---|---|---|---|---|---|---|
| B1 | Rôle d'exécution PostgreSQL | l'application utilise (selon `0098`) un rôle qui contourne RLS ; le rôle réel n'est pas inspecté | créer un rôle applicatif non propriétaire/non BYPASSRLS + un rôle de migration + un rôle « système » ; fournir une URL de **staging** | base Supabase (staging d'abord) | Élevé | `select rolname, rolsuper, rolbypassrls from pg_roles where rolname = current_user` ; test d'isolation avec le rôle non contournant | isolation = filtres applicatifs seulement |
| B2 | Migrations 0136/0137 en production | non appliquées / état non vérifié ; interdiction d'exécuter `alembic` à distance | sauvegarde → `alembic upgrade head` sur staging puis production par vous | base de production | Moyen | `alembic current` = `0137`, table `notification_templates`, `select count(*) from pg_policies` = 6 | routes de modèles de notification en erreur ; pas de politiques pilote |
| B3 | Sauvegarde/restauration réelles | aucun accès aux sauvegardes du fournisseur | activer/vérifier plan, rétention, point-in-time ; exécuter le test de `05-backup-restore.md` sur une base jetable | Supabase + S3/R2 | Élevé | restauration réussie datée, RPO/RTO mesurés | risque de perte de données non évalué |
| B4 | Worker et beat Celery | aucun service de worker/beat visible ; plan actuel inconnu | choisir l'option A/B/C de `docs/devops/CELERY_WORKERS.md` ; créer 2 services (coût) | hébergeur de l'API | Élevé | `celery inspect ping` répond ; une tâche planifiée s'exécute à l'heure | facturation périodique, purge RGPD, ingestion non garanties |
| B5 | Paiements de bout en bout | pas de clés de **test** fournies | fournir des clés sandbox Stripe/Paystack et un endpoint de webhook de staging | Stripe test mode, Paystack test | Élevé | scénarios de `07-billing-payments.md` | aucune preuve avec un vrai fournisseur |
| B6 | Politique de remboursement et devise de facturation | décisions commerciales | trancher (options A/B/C ; une devise ou prix par devise) | — | Moyen | décision écrite | pas de remboursement ; incohérence EUR/USD |
| B7 | Éligibilité Paystack/Stripe pour le pays du compte marchand (Cameroun cité) | dépend du compte | vérifier dans le tableau de bord fournisseur (devises, pays, moyens de paiement) | comptes marchands | Moyen | capture écran/export des capacités | achat de crédits Paystack impossible |
| B8 | Valeurs réelles des paramètres sensibles | non visibles depuis le dépôt | tableau « variable → définie ? → conforme ? » dans le tableau de bord Render/Vercel (jamais les valeurs) : `CREDITS_ALLOW_UNPAID_TOPUP`, `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS`, `COOKIE_SECURE`, `METRICS_AUTH_TOKEN`, `METRICS_REQUIRE_AUTH`, `MCP_STDIO_ENABLED`, `CLAMAV_ENABLED` | Render | Élevé | risque de crédits gratuits / métriques publiques |
| B9 | Incident des comptes de test (preview@, design@, client@, boss@ …) | création dans la base de production par un aperçu local ; **non inspecté, non nettoyé (non autorisé)** | exécuter la requête de lecture seule ci-dessous, puis décider du nettoyage | base de production | Moyen | résultat de la requête + dates + liens avec des données réelles | comptes parasites en production |
| B10 | CI GitHub du nouveau job PostgreSQL | rien n'a été poussé (interdit sans autorisation) | autoriser un push de la branche `bob/auto-fix-20261010-1555` | GitHub | Faible | job `backend-postgres-tests` vert | job non validé en CI |
| B11 | Benchmark RAG réel | choix du modèle/budget/ données | approuver modèle + budget ; télécharger SQuAD dev (~4 Mo) | fournisseur LLM éventuel | Faible | rapport de `RAG_EVALUATION.md` | pas de chiffre de qualité |
| B12 | Dépendances majeures | tests de régression nécessaires | traiter une par une | — | Moyen | CI verte par mise à jour | correctifs manqués |

### Requête de diagnostic en lecture seule pour B9 (à exécuter par vous, jamais en écriture)
```sql
-- Aucune modification. Adaptez la liste d'adresses ; ne copiez pas de données personnelles dans un rapport.
SELECT u.id, u.created_at, u.is_email_verified, u.role, u.deleted_at, u.deletion_scheduled_at,
       (SELECT count(*) FROM organization_members m WHERE m.user_id = u.id) AS orgs,
       (SELECT count(*) FROM sessions s WHERE s.user_id = u.id) AS sessions
FROM users u
WHERE lower(u.email) IN ('preview@example.com','design@example.com','client@example.com','boss@example.com')
ORDER BY u.created_at;
-- Puis, pour chaque organisation liée : documents, agents, conversations, factures, crédits (comptes seulement).
```
**Critères autorisant un nettoyage ultérieur** : adresses exactement celles du diagnostic ; créées pendant la fenêtre de l'incident ; aucune facture payée, aucun abonnement payant, aucun document ni conversation d'un vrai client ; sauvegarde récente ; suppression via la route RGPD de l'application (journalisée), jamais par `DELETE` direct ; décision écrite de la propriétaire.
