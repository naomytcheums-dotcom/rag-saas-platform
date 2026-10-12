# PHASE 5 — Corrections fonctionnelles et de sécurité (2026-10-12)

Suite de `../phase0-2026-10-12/` (SEC-009, TEN-005 et l'item « erreurs d'embeddings » annoncé). Tout est local et testé hors ligne ; rien n'est poussé ni fusionné ; aucune migration.
Commits locaux de la session, **6 non poussés** : `c8fb325` (ignore), `d219f48` (gardes), `b0c3339` (isolation), `6b855f9` (contrat de migrations), `57afc5d` (cette phase), `950bc1c` (runbook).
Correction d'un écart de ma part : le message de `6b855f9` annonçait la modification du runbook, mais elle avait été appliquée après ce commit ; elle est maintenant commitée séparément (`950bc1c`).

## 1. Corrigé et prouvé

| # | Défaut | Correction | Preuve |
|---|---|---|---|
| 1 | **SEC-009 — secrets dans les journaux.** Le masque ne couvrait que la forme `clé: "valeur"` entre guillemets, et seulement sur le formateur JSON et `system_logs`. Le gestionnaire **Loki** (Grafana Cloud, hébergé) envoyait la ligne telle quelle ; les en-têtes `Bearer`, les paires `password=…` / `token: …`, les URL `postgresql://utilisateur:mot-de-passe@hôte`, les clés de fournisseurs et le texte des exceptions passaient ; le worker Celery ne masquait rien | `mask_sensitive` couvre désormais ces formes ; le masquage s'exécute dans la **fabrique d'enregistrements de logs**, donc avant tout gestionnaire (console, `system_logs`, Loki, Sentry), sur le message et sur le texte de l'exception ; une ligne sans secret n'est pas touchée (gabarit, arguments et regroupement Sentry conservés) ; ne lève jamais d'exception ; installé aussi dans le worker (`worker_init`, `worker_process_init`) | `tests/test_log_secret_masking.py` (13 tests) : **échouent sans la correction** (8 échecs, 3 erreurs, vérifié en remettant les deux fichiers d'origine puis en restaurant les miens, empreintes identiques) ; passent avec ; 8 formes de secret testées, 4 lignes ordinaires inchangées |
| 2 | **Erreurs d'embeddings non converties** : les erreurs de connexion, 5xx, 404 et 400 de LiteLLM échappaient comme exceptions brutes, donc `get_embeddings_with_fallback` (qui n'attrape que `EmbeddingError`) ne passait jamais au fournisseur suivant quand le premier était en panne. Même défaut que celui corrigé pour les LLM (`95fc90f`) | `openai.APIError` est converti en `EmbeddingProviderError` | `tests/test_embedding_error_mapping.py` (6 tests) : 6 échecs avant, 6 réussites après |

Vérifications : `ruff` propre sur `api/`, `tests/`, `scripts/` ; 235 tests voisins passent (journalisation, Celery, embeddings, LLM, retrieval, mem0). 10 échecs de `tests/test_celery_worker_workflow.py` dus à l'environnement (`Bash is required to validate the Linux worker workflow` sous Windows) : ce fichier ne touche aucun module modifié.

## 2. Passe statique sur les motifs dangereux (positif)
Dans `api/` : aucun `verify=False`, `pickle`, `yaml.load` non sûr, `shell=True`, CORS `*`, `debug=True`, assertion servant d'autorisation ni générateur aléatoire pour un secret. Les occurrences restantes sont des expressions de détection (`plugin_manifest.py`), de la documentation, `hashlib.sha1/md5` avec `usedforsecurity=False` (test de mot de passe compromis, répartition A/B) et deux `text(f"…")` dont la valeur est convertie en entier. Limite : analyse textuelle, non exhaustive ; `bandit` en CI couvre aussi cela.

## 3. Volontairement non fait
| Élément | Raison |
|---|---|
| `organization_id` signé dans les messages Celery (TEN-005) | **Je ne le recommande pas tel que prévu.** Ajouter l'organisation dans le message ne protège pas contre un attaquant qui contrôle le courtier : il fabrique un message cohérent. La vraie protection est l'accès au courtier (Redis/Upstash : TLS, mot de passe, réseau). Les 45 sites de mise en file sont déjà atteints par des chemins gardés (phase 3). Si tu veux quand même une défense en profondeur, il faut signer le message (HMAC avec une clé de l'application), ce qui change tous les points d'envoi et les tâches en vol : à décider |
| 19 fonctions sans appelant (`delete_conversation` ×2, `get_chunk_content`, `message_actions`, etc.) | code mort ou dynamique : les supprimer exige ton accord et une analyse de dépendances ; les « sécuriser » sans appelant n'a pas de test significatif. Elles restent au registre des fonctionnalités à préserver |
| Ligne 38 du runbook (caractère de contrôle `0x08`) | mon outil d'édition ne peut pas cibler ce caractère invisible sans réécrire le fichier |
| Rotation des secrets, rôle sans `BYPASSRLS`, politiques RLS | décisions et accès de la propriétaire |

## 4. Limites
* Le masquage est textuel : un secret de forme inattendue (valeur sans mot-clé voisin, clé de fournisseur d'une autre forme) peut passer ; les journaux déjà envoyés à Loki ou stockés dans `system_logs` **ne sont pas nettoyés** (l'état actuel de ces données est inconnu).
* Quelques faux positifs possibles (par exemple « password: required » devient « password: *** »).
* Les lignes masquées changent de regroupement dans Sentry (gabarit remplacé par le message masqué) ; les autres lignes ne changent pas.

## 5. Décisions qui attendent la propriétaire
1. **Pousser les 6 commits** vers la PR #25 puis fusionner, pour que `main` reçoive les corrections d'isolation (phase 3), du masquage et des embeddings. Le push relance les deux CI (CircleCI xlarge coûteux).
2. Après la fusion, décider si l'historique de `system_logs` et de Loki doit être purgé (lecture seule d'abord : compter les lignes contenant des motifs de secret).
3. Signer ou non les messages Celery (voir §3).
4. Les décisions de la phase 4 : numéro du pilote RLS, `TO PUBLIC`, contention de `0133`.

## 6. Critères d'entrée de la phase 6 (tests d'intégration isolés)
* La CI (GitHub et CircleCI) verte ou ses échecs acceptés sur les commits poussés ;
* accord pour construire la pile locale jetable en script de référence (PostgreSQL + Redis + MinIO + ClamAV + Jaeger + Ollama) et pour mesurer la couverture réelle sans prétendre atteindre 90 %.
