# 06 — Celery, Redis, scheduler

Inventaire complet par tâche : `celery-task-inventory.csv` (105 tâches ; colonnes : planification beat, file, retries, limites, acks_late, marqueurs d'idempotence et effets de bord détectés — **heuristiques de lecture du code**, à confirmer par relecture).
Guide opérationnel et options d'hébergement : `docs/devops/CELERY_WORKERS.md`. Exemple de blueprint (non appliqué) : `deploy/render.worker.example.yaml`.

## Faits (VERIFIED dans le code et par import de l'application Celery)
| Sujet | Constat |
|---|---|
| Tâches | 105 enregistrées ; **toutes dans une seule file** `celery` |
| Beat | 61 entrées planifiées, **toutes pointent vers des tâches enregistrées** (test de contrat) ; ordonnanceur `PersistentScheduler` par défaut dans la configuration (la persistance sur Redis, PROD-001, passe par la ligne de commande/déploiement, non vérifiée ici) |
| Retries | seulement la valeur par défaut de Celery (`max_retries=3`, effective si la tâche appelle `retry`) ; 2 tâches à 5 ; **aucun backoff configuré globalement** |
| Limites de temps | **aucune avant cette session** ; maintenant 3 300 s (soft) / 3 600 s (hard) pour toutes (`CELERY_TASK_SOFT_TIME_LIMIT_SECONDS`, `CELERY_TASK_TIME_LIMIT_SECONDS`, `0` désactive) |
| `acks_late` | désactivé (une tâche perdue avec son worker n'est pas relivrée) ; **volontairement conservé** : seules 25 tâches sur 105 portent un marqueur d'idempotence |
| Prefetch | 4 avant, **1 maintenant** (`CELERY_WORKER_PREFETCH_MULTIPLIER`) |
| Facturation | `generate_monthly_invoices` (marqueur « already »), `grant_monthly_plan_credits` (clé de période + verrou de ligne), `auto_refill_credits` (verrou de ligne), `mark_overdue_invoices` (UPDATE conditionnel), `send_invoice_reminders` (**aucun garde**) |
| Effets de bord détectés | suppression 16 tâches, e-mail 9, webhook sortant 5, stockage 5, LLM/embeddings 2, paiement 1 (heuristique, une tâche peut cumuler) |
| Image de production API | **gunicorn seul** ; le worker embarqué a été essayé et retiré (service injoignable sur 512 Mo) |
| Worker/beat en production | **NOT_VERIFIED / BLOCKED_EXTERNAL** : rien dans le dépôt ne montre un worker ou un beat déployé ; seul un workflow GitHub exécute un worker pendant 420 s par rafales |
| Santé et observabilité | compteur Prometheus `celery_tasks_total` ; pas de sonde de santé de worker versionnée : commande `celery inspect ping` documentée |

## Corrigé dans cette session
- Limites de temps et prefetch (commit `250c44e`), 5 tests de configuration, test de contrat beat ↔ tâches.
- Documentation : règle « exactement un beat », options A/B/C avec coûts signalés comme estimations, variables par nom.

## Non corrigé / décisions
| Point | Statut | Pourquoi / suite |
|---|---|---|
| Séparer API, worker, beat en production | BLOCKED_EXTERNAL | nécessite des services supplémentaires (coût) et l'accès à l'hébergeur ; exemple fourni |
| Un seul beat garanti | ACCEPTED_RISK documenté | règle opérationnelle ; verrou Redis `SET NX` par tâche périodique = durcissement suivant (sans lui, deux beats ⇒ rappels envoyés deux fois) |
| Retries bornés + backoff exponentiel par tâche | NOT_VERIFIED / à faire | nécessite de classer les 105 tâches (idempotentes ou non) ; `autoretry_for` + `retry_backoff` seulement pour les idempotentes |
| `acks_late` | refusé pour l'instant | activer seulement après avoir rendu idempotentes les 80 tâches sans marqueur |
| Tests d'intégration Celery | NOT_RUN | `tests/test_celery_integration.py` : 8 ignorés sans base joignable (exécutés en CI CircleCI) |
| Isolation des tâches entre tenants | NOT_VERIFIED | contexte tenant non propagé aux workers (voir `03-tenant-isolation.md`) |
| Concurrence entre tenants | partiellement traité | prefetch 1 ; pas de files par priorité/tenant |

## Coûts et limites (estimations, à vérifier chez le fournisseur)
Voir le tableau des options dans `docs/devops/CELERY_WORKERS.md`. Blocage explicite : un service web gratuit ne peut pas exécuter de worker persistant ; le plan actuellement souscrit n'est pas visible depuis le dépôt.
