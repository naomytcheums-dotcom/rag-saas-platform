# 12 — Dettes, risques et bloquants

Audit du 2026-10-10, HEAD `59d5ec9`. Chaque ligne indique si le constat est **confirmé** (preuve citée), **déduit du code** (risque) ou **une hypothèse**. Aucune note globale artificielle.

## A. Risques confirmés (par lecture du code et/ou exécution)
| # | Risque | Gravité | Preuve | Statut |
|---|---|---|---|---|
| R-01 | **Isolation multi-tenant sans barrière en base** : RLS activé sur les tables mais 0 `FORCE`, 0 `CREATE POLICY`, rôle applicatif documenté comme contournant. Un seul filtre `organization_id` oublié dans 101 routeurs / 284 services expose les données d'une autre organisation. | Haute | `api/alembic/versions/0098_rls_coverage_gap.py` (en-tête), recherche textuelle sur 136 migrations, `docs/CAHIER_DES_CHARGES.md` | CONFIRMÉ (schéma réel non inspecté) ; exploitation effective : aucune démontrée |
| R-02 | **Aucun worker Celery / beat dans l'image de production de l'API** : `Dockerfile.api` lance uniquement `gunicorn` (l'essai d'un worker dans le même conteneur gratuit de 512 Mo a rendu le service injoignable et a été annulé, commentaire du Dockerfile) ; `docker-entrypoint.sh` n'est « conservé que pour un hôte plus généreux » ; `render.yaml` ne déclare aucun worker ; le seul worker planifié est un workflow GitHub par rafales de 7 min. Concernés : ingestion de documents (sauf rattrapage), factures périodiques, allocation de crédits, purges RGPD, rappels. | Haute | `Dockerfile.api` (CMD et commentaire), `docker-entrypoint.sh:4-18`, `render.yaml`, `.github/workflows/celery-worker.yml` | CONFIGURATION CONFIRMÉE ; ce qui tourne réellement sur Render (service de worker créé à la main ?) NON VÉRIFIÉ |
| R-03 | **Migrations non automatisées et état de la base de production non prouvé** ; `0136` (table `notification_templates`) **pas encore appliquée** — tant qu'elle ne l'est pas, les routes de modèles de notification restent en erreur 500 (TEN-006, déduit : la table n'existe pas sans la migration). | Haute | absence de `alembic upgrade` dans les fichiers de déploiement ; message de l'utilisatrice ; `docs/audit/PRODUCTION_BLOCKERS.md` P0-2 | CONFIRMÉ (déploiement) / DÉDUIT (500) |
| R-04 | **Aucune preuve de sauvegarde ni de restauration** (RPO/RTO, rollback) | Haute | PROD-009 ; aucun runbook trouvé dans les fichiers examinés ; `docs/audit/BACKUP_AUDIT.md` non lu en détail | NON ÉTABLI = pas de preuve |
| R-05 | **Facturation jamais validée avec un vrai fournisseur** : tous les tests utilisent des événements synthétiques ; tests « live » ignorés ; concurrence PostgreSQL non exécutée en CI ; **remboursements non gérés** (BILL-016) ; plafonds de dépense non atomiques (BILL-012, non revérifié) ; preuve de paiement manuelle non confrontée à une banque. | Haute | `09_BILLING_PAYMENTS.md`, tests ignorés (8 live) | CONFIRMÉ |
| R-06 | **Qualité RAG non mesurée** : les métriques existent dans le code (Recall@K, MRR, NDCG) mais **aucune valeur réelle n'a été produite ou lue** ; chemin de recherche de production incertain (numpy vs HNSW) ; chunking avancé non câblé | Moyenne-haute | `06_RAG_PIPELINE.md` | CONFIRMÉ (absence de mesure) |
| R-07 | **Documentation contradictoire/obsolète** : `agents.md` (endpoints `/api/eval/*` et `/mcp/v1/servers…` inexistants, Python 3.11, dossier `api/eval/` absent) ; `render.yaml` ne décrit que le prototype Streamlit ; cahier des charges (515 non reproductible, texte d'origine perdu, Partie 15 tronquée, note « GitHub Actions désactivé » périmée). Les modes Bob (FACTORY/GUARDIAN/AUTOPSY/CHANGELAB) reposent sur ces chemins. | Moyenne | `06`, `01`, `15` | CONFIRMÉ |
| R-08 | **Couverture et fiabilité de la preuve** : tests principalement sur SQLite ; 183 des 943 opérations HTTP n'ont aucun test référençant leur chemin (heuristique) ; 84 opérations sans dépendance d'authentification détectée (à classer : publiques légitimes ou protégées autrement) | Moyenne | `04_API_ENDPOINTS.csv`, `08` | CONFIRMÉ (heuristique) |
| R-09 | **Rate limiting dégradé sans Redis** : repli sur un limiteur en mémoire de processus (non partagé entre workers, remis à zéro à chaque redémarrage) | Moyenne | journaux de tests (« degrading to the in-process limiter »), `api/security/rate_limit.py` | CONFIRMÉ |
| R-10 | **`/metrics` public si `METRICS_AUTH_TOKEN` est absent** | Moyenne | `api/main.py:426-444` | CONFIRMÉ (code) ; valeur en production NON VÉRIFIÉE |

## B. Risques déduits du code (non mesurés)
- Mémoire : torch + sentence-transformers + gunicorn (4 workers par défaut) + worker Celery dans 512 Mo ; démarrage à froid (PROD-004) ; plan gratuit Render.
- Chargement en mémoire de tous les chunks d'une organisation (BM25 / repli numpy) : dégradation avec la taille des organisations.
- Dispatch Celery en « best effort » : un document peut rester `pending` si le broker est indisponible (un rattrapage existe, RAG-003, à vérifier en production).
- Importeurs externes asynchrones (URL, GitHub, Drive, Notion…) appellent encore boto3 de façon synchrone (TEN-003 partiel).
- `api/tools/sql_tool.py` : SQL dynamique via `text()` ; `calculator.py` : `eval()` borné par AST.
- Clés Redis et caches : prise en compte du tenant non établie.
- 122 constats historiques sans trace de correction (voir `11`) : certains sont probablement déjà corrigés sans mention d'identifiant.

## C. Hypothèses nécessitant une mesure
Capacité (documents / utilisateurs / req/s) : **NON MESURÉ** ; latence du chat ; coût LLM par organisation ; comportement sous 8 inscriptions concurrentes réelles ; efficacité de la détection d'injection.

## D. Dettes techniques
- Deux pipelines RAG (`src/` Streamlit et `api/`), deux CI (GitHub, CircleCI) dont la durée approche la limite (CircleCI ≈ 55 min pour une limite de 60 ; GitHub ≈ 42-60 min pour 75) ; liste de fichiers de test CircleCI codée en dur (nouveaux tests non couverts).
- Fichiers volumineux : `ROADMAP.md` 300 Ko, cahier des charges 649 Ko ; `snyk.exe` (55 Mo) présent à la racine mais **ignoré par Git** (`.gitignore:25`, non suivi).
- Dépôt local encombré : 19 branches locales, 10 worktrees, répertoires de travail d'agents (`.claude/`).
- Cinq suites de test du prototype exclues de la CI.

## E. Bloquants avant mise en production commerciale
1. R-01 (décision : accepter l'isolation applicative documentée, ou introduire des politiques RLS + rôle non contournant).
2. R-02 / R-03 / R-04 (exploitation : worker, migrations, sauvegardes).
3. R-05 (validation sandbox Stripe/Paystack de bout en bout, politique de remboursement).
4. Une mesure de qualité RAG sur un jeu réel (R-06).

## F. Dépendances externes bloquantes (BLOQUÉ — SERVICE EXTERNE dans cet audit)
Stripe/Paystack (sandbox), Supabase (schéma réel), Render/Vercel (état réel), Redis réel, Resend, fournisseurs LLM, ClamAV. Aucun n'a été appelé.

## G. Décisions métier encore ouvertes (relevées pendant le travail du 2026-10-10)
Politique de remboursement (`refunded` non géré) ; effet d'une facture payée/annulée sur le statut d'abonnement (aujourd'hui aucun, documenté) ; achat de crédits via Paystack ; devise des packs (USD) vs plans (EUR) ; V6 (horodatage Paystack) et V10 (noms des clés de permission) : « ne rien changer » à ce jour ; rôle du viewer sur les workflows (décidé et corrigé le 2026-10-10).
