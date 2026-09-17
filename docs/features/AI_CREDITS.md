# Crédits IA

## Ce qui existait déjà (avant cette session)

- `Credit` / `CreditTransaction` (`api/models/billing.py`) -- un solde
  réel par organisation, avec un journal d'audit complet de chaque
  mouvement (achat, consommation, remboursement, don).
- `api/services/billing_credits.py` -- `get_or_create_credit`,
  `add_credits`, `deduct_credits`, `refund_credits`,
  `list_credit_transactions`. Un don initial de
  `settings.CREDITS_DEFAULT_AMOUNT` (1000) à la création du compte.
- `api/security/credit_packs.py` -- 4 packs achetables (Starter 10k,
  Pro 100k, Business 500k, Enterprise 1M crédits) et la table de
  conversion réelle : 1 crédit = 1 requête API, 100 tokens en entrée,
  50 tokens en sortie, ou 1 document traité.
- Endpoints déjà réels : `GET /organizations/{id}/billing/credits`
  (solde), `GET .../credits/transactions` (historique),
  `GET .../credits/packs` (catalogue), `POST .../credits/purchase`
  (achat).
- Frontend déjà réel : l'onglet "Crédits" de
  `/dashboard/billing` (solde, transactions, achat de pack).

**Ce qui manquait, et a été ajouté dans cette session** : rien de tout
cela n'était réellement débité par un appel LLM -- `deduct_credits`
n'était appelé nulle part avant ce travail.

## Ce qui a été ajouté

### 1. Débit réel à chaque appel LLM

`api/services/agent_orchestrator.py` (`AgentOrchestrator.run_agent`) :
- Passe de `chat_completion` à `chat_completion_with_usage`, qui
  renvoie le vrai nombre de tokens réellement consommés par le
  fournisseur (`prompt_tokens`/`completion_tokens`, litellm).
- Calcule le coût réel avec `credits_for_usage` (la table de conversion
  déjà existante, jamais utilisée avant) et appelle `deduct_credits`
  juste après un appel réussi.
- Un solde insuffisant est journalisé (`logger.warning`) mais ne fait
  jamais échouer la réponse déjà obtenue de l'utilisateur -- le coût
  réel a déjà été payé au fournisseur à ce stade ; faire échouer la
  comptabilité après coup serait pire que de la laisser en négatif.
- Le chemin de streaming (`stream_response`) reçoit la même résolution
  de clé BYOK (voir `docs/features/BYOK.md`) **et** débite maintenant
  aussi les crédits (ajouté en fin de session) : `chat_completion_stream`
  accepte un `usage_sink`, rempli avec le vrai usage renvoyé par
  litellm (`stream_options={"include_usage": True}`, normalisé sur tous
  les fournisseurs) sur le dernier chunk du flux -- jamais une
  estimation au nombre de caractères. Si un fournisseur ne renvoie
  jamais ce chunk d'usage, aucun débit n'est tenté plutôt que d'inventer
  un coût.

### 2. Pack de crédits mensuel inclus par forfait

- `Plan.monthly_credits_included` (nouvelle colonne, migration `0109`)
  -- `NULL` = ce forfait n'inclut aucun crédit récurrent, une valeur
  réelle (y compris `0`) est une vraie décision produit.
- Valeurs réelles seedées : Free 1000 (aligné sur le don de bienvenue
  existant), Starter 10 000, Pro 50 000, Enterprise 200 000.
- `api/tasks/billing.grant_monthly_plan_credits` -- tâche Celery,
  exécutée le 1er de chaque mois (`celery_app.py`'s beat schedule),
  idempotente (un tag `reason` par mois empêche un double don en cas de
  ré-exécution).

## Ce qui n'a pas changé (déjà réel, réutilisé tel quel)

Les 4 endpoints demandés (`GET /credits/balance`, `POST
/credits/purchase`, `GET /credits/usage`) existent déjà sous
`/organizations/{id}/billing/credits*` -- convention déjà établie dans
ce projet (voir `api/routers/billing.py`'s own docstring : "everything
that belongs to ONE organization... lives under
/organizations/{org_id}/billing/..."). Pas dupliqués sous un chemin
plat pour rester cohérent avec le reste de l'API.

## Test réalisé en direct

Compte de test créé, agent exécuté avec un vrai appel LLM, solde de
crédits vérifié avant/après -- voir le message de session pour le
résultat concret.
