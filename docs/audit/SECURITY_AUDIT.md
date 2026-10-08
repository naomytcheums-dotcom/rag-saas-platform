# Security Audit — Initial

Date : 2026-10-03. Revue statique spécialisée; aucun code corrigé dans cette
phase. Aucun secret n'a été lu ou reproduit. Aucune validation de production,
PostgreSQL, Redis, paiement ou provider externe n'a été faite.

## Findings

### S-01 — Top-up gratuit autorisé par défaut si aucun fournisseur n'est résolu

- **Priorité : P0 conditionnel / sévérité statique moyenne**
- **Fichier :** `api/config.py:2202`; chemin d'exécution
  `api/routers/billing.py:176-196`.
- **Preuve :** la valeur par défaut de `CREDITS_ALLOW_UNPAID_TOPUP` est
  `True`. Le endpoint refuse les top-ups directs si un fournisseur de
  paiement est résolu, mais, sans fournisseur, autorise le crédit lorsque ce
  paramètre est vrai. L'autorisation de route est `billing:manage`.
- **Impact :** si un déploiement SaaS de production n'a aucun fournisseur
  résolu et ne surcharge pas explicitement le défaut, des membres autorisés
  peuvent créer des crédits sans paiement et financer des appels coûteux.
- **Limite :** le fournisseur configuré et la valeur effective de production
  n'ont pas été vérifiés. Il s'agit d'une exposition conditionnelle du code,
  pas d'une exploitation de production confirmée.
- **Recommandation :** considérer comme blocage avant commercialisation tant
  que le fournisseur obligatoire ou le réglage explicite de production n'est
  pas établi; ensuite corriger par changement minimal et tests de non-régression.

### S-02 — Coût A2A débité après exécution, échec de débit avalé

- **Priorité : P1 / sévérité statique moyenne**
- **Fichier :** `api/routers/a2a.py:69-81` et `api/routers/a2a.py:116`.
  Route montée dans `api/main.py` (modification du workspace).
- **Preuve :** `_BilledRagAgentExecutor.execute` exécute d'abord le parent,
  puis tente `deduct_credits`; `InsufficientCreditsError` est capturée et
  seulement journalisée. Le contrôle préliminaire permet à une organisation
  ayant un solde positif inférieur au coût forfaitaire de commencer un appel.
- **Impact :** appels A2A potentiellement exécutés sans débit correspondant,
  avec risque de consommation fournisseur et de contournement des limites
  fondées sur les crédits.
- **Limite :** le scénario dépend du coût configuré, du solde et du provider;
  aucune requête réelle n'a été faite.
- **Recommandation :** réserver/débiter atomiquement avant exécution; refuser
  l'exécution si la réservation échoue et rendre la compensation explicite.

### S-03 — RLS activé sans policy pour le rôle application

- **Priorité : P1 (risque structurel, fuite non démontrée)**
- **Preuve :** `tests/test_postgres_integration.py` vérifie zéro policy RLS
  publique et que le rôle de l'application contourne RLS; la migration 0131
  active RLS mais n'ajoute aucune policy.
- **Impact :** PostgreSQL n'assure pas de filtre tenant de défense en
  profondeur contre une requête applicative sans filtre ou un nouveau chemin
  d'accès; la confidentialité dépend entièrement du code API/RBAC.
- **Limite :** aucune tentative A→B/B→A sur la base réelle n'a été exécutée.
- **Recommandation :** définir explicitement le modèle de rôle d'exécution,
  vérifier les grants et écrire des tests d'isolation. Ne pas activer FORCE
  RLS sans étudier les effets sur l'application et les tâches.

### S-04 — Workflow masque les erreurs du worker Celery

- **Priorité : P2**
- **Fichier :** `.github/workflows/celery-worker.yml`, commande de worker
  `timeout 420 ... || true`.
- **Preuve :** le code de retour non nul du worker/timeout est neutralisé.
- **Impact :** le workflow périodique peut sembler réussir alors qu'aucune
  tâche n'a été traitée ou qu'un worker a échoué; les traitements restent en
  attente sans signal CI fiable.
- **Limite :** le workflow n'a pas été lancé dans cette phase.
- **Recommandation :** ne masquer l'échec que pour des codes explicitement
  attendus et distincts; publier un état observable en cas d'échec réel.

## Garde-fous et limites de la revue

- Le dépôt contient des modules dédiés à JWT, RBAC, rate limiting, SSRF,
  chiffrement, plugins, sandbox et journaux d'audit; leur simple existence
  n'est pas une validation sécurité.
- Le reviewer spécialisé a priorisé les zones à haut risque et n'a pas
  exhaustivement revu CORS/sessions ou tous les chemins de traitement de
  fichiers. Les autres vecteurs et dépendances restent à auditer.
- Les chemins locaux `.env`, `frontend/.env.local` et `dump.rdb` existent et
  sont ignorés par Git; leur contenu n'a pas été lu. Les tests ne doivent pas
  être exécutés contre des services payants réels sans isolement.
- Statut : constats statiques ci-dessus, **aucune vulnérabilité exploitée ni
  intégration de production validée**.

## État après corrections locales autorisées

Les deux correctifs ci-dessous ont été appliqués au workspace après la
photographie initiale. Ils ne certifient pas le déploiement externe.

| Constat | Correction locale | Preuve de régression | Limite résiduelle |
|---|---|---|---|
| S-01 | Défaut passé à `False`; l'opt-in self-hosted reste disponible explicitement. | `tests/test_config.py` et `tests/test_billing.py`; inclus dans les 84 tests ciblés réussis. | La valeur effective des variables de production n'a pas été vérifiée. |
| S-02 | Préflight exige le coût A2A total; débit avec verrou de ligne avant l'appel agent et commit seulement si succès; BYOK reste exempt. | `tests/test_a2a_router.py`; test de solde insuffisant, débit préalable et rollback après échec; inclus dans les 84 tests ciblés réussis. | SQLite ne valide pas le verrou PostgreSQL; service/déploiement réel non testé. |

La validation a produit deux avertissements
`PytestUnraisableExceptionWarning` sur les coroutines `ActiveTask` du SDK A2A;
les 84 assertions passent néanmoins. Ils ne sont pas encore attribués à ces
correctifs et doivent être investigués avant de déclarer la suite sans
avertissement.

Lors d'une première tentative de test, le flux d'inscription a tenté d'appeler
le service externe Resend avec une adresse réservée `example.com`; le service
a rejeté l'adresse (HTTP 422), aucun email n'a été envoyé. Les helpers
d'inscription des tests billing/A2A modifiés stubent maintenant cet envoi;
les identifiants n'ont pas été affichés. Ce constat ne valide pas la
configuration email de production.
