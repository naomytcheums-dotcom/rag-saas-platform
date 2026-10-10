# 15 — Préparation à la mise en production

## Décision : **NO-GO** (à ce jour)

Rien de ce qui est livré ne casse une fonctionnalité, mais plusieurs risques critiques ne sont **pas vérifiés** et dépendent d'accès que je n'ai pas.

## Bloquants avant production
| # | Condition | Statut |
|---|---|---|
| 1 | Sauvegarde/restauration de la base hébergée testée (REM-017) | BLOCKED_EXTERNAL |
| 2 | Rôle d'exécution de production : contourne-t-il RLS ? Les politiques `0137` sont inertes sinon | BLOCKED_EXTERNAL |
| 3 | Worker Celery + beat (instance unique) réellement déployés ; `render.yaml` ne décrit que le prototype | BLOCKED_EXTERNAL |
| 4 | Paiements Stripe/Paystack en sandbox ; politique de remboursement et de devise décidée (REM-018) | BLOCKED_EXTERNAL |
| 5 | CI GitHub (dont `backend-postgres-tests`) et CircleCI verts sur cette branche : nécessite un push autorisé | NOT_RUN |
| 6 | Suite backend complète locale terminée et analysée | en cours (voir `10-test-results.md`) |
| 7 | IDOR par identifiant de ressource non audité exhaustivement (REM-021) | NOT_VERIFIED |
| 8 | 125 constats historiques non vérifiés (`01-findings-register.csv`) | NOT_VERIFIED |
| 9 | Variables sensibles vérifiées par nom sur l'hébergeur (`SENSITIVE_SETTINGS.md`) | BLOCKED_EXTERNAL |

## Acquis
Aperçu local isolé, pilote RLS (6 tables) testé sur PostgreSQL jetable, chaîne Alembic sur base vide, limites de temps Celery, `/metrics` fail-closed en option, import d'évaluation SQuAD, devise des packs, docs et CI PostgreSQL ajoutés.

## Passage à CONDITIONAL GO
Conditions 1, 2, 3, 5, 6 remplies + déploiement staging réussi (`14-deployment-runbook.md`). Les points 4, 7, 8 peuvent être des réserves documentées si le lancement est restreint (pas de paiement Paystack, pas de crédit payant).

Aucune fusion ni déploiement n'a été fait ; décision à la propriétaire.
